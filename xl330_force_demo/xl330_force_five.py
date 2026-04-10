#!/usr/bin/env python3
"""
五个 Dynamixel XL330-M288T 舵机的力反馈控制
支持通过 WiFi 接收传感器数据并控制 5 个舵机
"""
import os
import sys
import time
import threading
import socket
import json
from dynamixel_sdk import *

# ===== 硬件串口 & 舵机参数 =====
DEVICENAME          = '/dev/ttyAMA0'    # 树莓派串口端口
BAUDRATE            = 57600
PROTOCOL_VERSION    = 2.0
DXL_IDS             = [1, 2, 3, 4, 5]   # 五个舵机的ID

# XL330 Control Table Addresses
ADDR_OPERATING_MODE = 11
ADDR_CURRENT_LIMIT  = 38
ADDR_TORQUE_ENABLE  = 64
ADDR_GOAL_POSITION  = 116
ADDR_PRESENT_CURRENT= 126
ADDR_PRESENT_POSITION= 132
ADDR_PROFILE_VELOCITY = 112
ADDR_PROFILE_ACCELERATION = 108

# Operating Modes
OP_CURRENT_BASED_POSITION = 5

# ===== 每个舵机的控制参数 =====
class ServoController:
    """单个舵机的控制器"""
    def __init__(self, servo_id):
        self.servo_id = servo_id
        self.targetForceN = 0.0
        self.kN_per_mA = 0.8        # 力换算系数 (根据实测 10N=12mA 调整)
        self.hysteresisN = 1.5      # 力迟滞带 (放大)
        self.currentLimit_mA = 450  # 电流上限
        self.touchMode = False
        self.holdMode = False
        self.freeModeActive = False
        self.goal_pos = 0
        self.home_pos = 0
        
        # 导纳控制参数
        self.admittance_gain = 15.0 # 增加增益 (1.5 -> 15.0)
        self.max_step_per_loop = 25 # 放宽步进限制 (15 -> 25)
        
        # 运行配置
        self.calMin_mA = 5  # 最小标定电流 (40->5)
        
        # 软件滤波
        self.mA_window = []
        self.window_size = 10

# 全局变量
servo_controllers = [ServoController(id) for id in DXL_IDS]
portHandler = PortHandler(DEVICENAME)
packetHandler = PacketHandler(PROTOCOL_VERSION)
dxl_lock = threading.Lock()
running = True

# ===== 辅助函数：读取/写入 =====
def read2ByteSigned(servo_id, addr):
    """读取2字节有符号数"""
    with dxl_lock:
        val, res, err = packetHandler.read2ByteTxRx(portHandler, servo_id, addr)
    if res != COMM_SUCCESS:
        print(f"[舵机{servo_id}] 读取错误: {packetHandler.getTxRxResult(res)}")
    elif err != 0:
        print(f"[舵机{servo_id}] 硬件错误: {packetHandler.getRxPacketError(err)}")
    # Convert unsigned to signed 16-bit
    if val > 32767:
        val -= 65536
    return val

def read4ByteSigned(servo_id, addr):
    """读取4字节有符号数"""
    with dxl_lock:
        val, res, err = packetHandler.read4ByteTxRx(portHandler, servo_id, addr)
    if res != COMM_SUCCESS:
        print(f"[舵机{servo_id}] 读取错误: {packetHandler.getTxRxResult(res)}")
    elif err != 0:
        print(f"[舵机{servo_id}] 硬件错误: {packetHandler.getRxPacketError(err)}")
    # Convert unsigned to signed 32-bit
    if val > 2147483647:
        val -= 4294967296
    return val

def write1Byte(servo_id, addr, val):
    """写入1字节"""
    with dxl_lock:
        res, err = packetHandler.write1ByteTxRx(portHandler, servo_id, addr, val)
    if res != COMM_SUCCESS:
        print(f"[舵机{servo_id}] 写入错误: {packetHandler.getTxRxResult(res)}")

def write2Byte(servo_id, addr, val):
    """写入2字节"""
    with dxl_lock:
        res, err = packetHandler.write2ByteTxRx(portHandler, servo_id, addr, val)
    if res != COMM_SUCCESS:
        print(f"[舵机{servo_id}] 写入错误: {packetHandler.getTxRxResult(res)}")

def write4Byte(servo_id, addr, val):
    """写入4字节"""
    with dxl_lock:
        res, err = packetHandler.write4ByteTxRx(portHandler, servo_id, addr, int(val))
    if res != COMM_SUCCESS:
        print(f"[舵机{servo_id}] 写入错误: {packetHandler.getTxRxResult(res)}")

def torqueOn(servo_id):
    """开启扭矩"""
    write1Byte(servo_id, ADDR_TORQUE_ENABLE, 1)

def torqueOff(servo_id):
    """关闭扭矩"""
    write1Byte(servo_id, ADDR_TORQUE_ENABLE, 0)

def enterFreeMode(controller):
    """进入自由模式"""
    torqueOff(controller.servo_id)
    controller.freeModeActive = True
    print(f"[舵机{controller.servo_id}] 自由模式")

def exitFreeMode(controller):
    """退出自由模式"""
    ppos = read4ByteSigned(controller.servo_id, ADDR_PRESENT_POSITION)
    torqueOn(controller.servo_id)
    controller.goal_pos = ppos
    write4Byte(controller.servo_id, ADDR_GOAL_POSITION, controller.goal_pos)
    controller.freeModeActive = False
    print(f"[舵机{controller.servo_id}] 退出自由模式")

# ===== 命令解析 =====
def parse_command(buf):
    """解析控制指令"""
    global servo_controllers, running
    
    try:
        buf = buf.replace("：", ":").strip().upper()
        
        # 格式: N:舵机ID:力值  例如: N:1:5 (舵机1设定目标力5N)
        if buf.startswith("N:"):
            parts = buf.split(":")
            if len(parts) >= 3:
                try:
                    servo_idx = int(parts[1]) - 1  # 转换为索引 (0-4)
                    force_val = float(parts[2])
                    
                    if 0 <= servo_idx < len(servo_controllers):
                        controller = servo_controllers[servo_idx]
                        
                        if force_val == 0:
                            controller.targetForceN = 0
                            controller.touchMode = False
                            print(f"[舵机{controller.servo_id}] 目标力=0，进入自由模式")
                        else:
                            if controller.freeModeActive:
                                exitFreeMode(controller)
                            
                            controller.targetForceN = abs(force_val)
                            controller.touchMode = True
                            print(f"[舵机{controller.servo_id}] 目标力={controller.targetForceN}N")
                    else:
                        print(f"[错误] 舵机索引超出范围: {servo_idx+1}")
                except ValueError:
                    print("[错误] 无效的数值格式")
            else:
                print("[错误] 格式: N:舵机ID:力值  例如: N:1:5")
        
        # 全部舵机设定相同目标力: NALL:5
        elif buf.startswith("NALL:"):
            try:
                force_val = float(buf[5:])
                for controller in servo_controllers:
                    if force_val == 0:
                        controller.targetForceN = 0
                        controller.touchMode = False
                    else:
                        if controller.freeModeActive:
                            exitFreeMode(controller)
                        controller.targetForceN = abs(force_val)
                        controller.touchMode = True
                print(f"[全部] 目标力={force_val}N")
            except ValueError:
                print("[错误] 无效的数值格式")
        
        # 保持模式: HOLD:舵机ID
        elif buf.startswith("HOLD:"):
            try:
                servo_idx = int(buf[5:]) - 1
                if 0 <= servo_idx < len(servo_controllers):
                    servo_controllers[servo_idx].holdMode = True
                    print(f"[舵机{servo_idx+1}] 保持模式")
            except ValueError:
                print("[错误] 无效的舵机ID")
        
        # 自由模式: FREE:舵机ID
        elif buf.startswith("FREE:"):
            try:
                servo_idx = int(buf[5:]) - 1
                if 0 <= servo_idx < len(servo_controllers):
                    controller = servo_controllers[servo_idx]
                    controller.targetForceN = 0
                    controller.touchMode = False
                    controller.holdMode = False
                    enterFreeMode(controller)
            except ValueError:
                print("[错误] 无效的舵机ID")
        
        # 状态查询
        elif buf == "STATUS":
            print("\n=== 五舵机状态 ===")
            for controller in servo_controllers:
                ppos = read4ByteSigned(controller.servo_id, ADDR_PRESENT_POSITION)
                pcur = read2ByteSigned(controller.servo_id, ADDR_PRESENT_CURRENT)
                estN = pcur * controller.kN_per_mA
                print(f"舵机{controller.servo_id}: 位置={ppos}, 电流={pcur}mA, "
                      f"估算力={estN:.2f}N, 目标力={controller.targetForceN:.2f}N")
        
        # 标定: CAL:舵机ID:实际力值
        elif buf.startswith("CAL:"):
            parts = buf.split(":")
            if len(parts) >= 3:
                try:
                    servo_idx = int(parts[1]) - 1
                    real_force = float(parts[2])
                    
                    if 0 <= servo_idx < len(servo_controllers):
                        controller = servo_controllers[servo_idx]
                        pcur = read2ByteSigned(controller.servo_id, ADDR_PRESENT_CURRENT)
                        
                        if abs(pcur) >= controller.calMin_mA:
                            new_k = abs(real_force / float(pcur))
                            
                            if new_k > 0.1:
                                print(f"[错误] 舵机{controller.servo_id} 标定系数过大 ({new_k:.6f})! 忽略。")
                                print("       原因: 电流相对于力太小。请确保舵机真的在用力。")
                            else:
                                old_k = controller.kN_per_mA
                                controller.kN_per_mA = new_k
                                print(f"[舵机{controller.servo_id}] kN_per_mA: {old_k:.6f} -> {new_k:.6f}")
                        else:
                            print(f"[舵机{controller.servo_id}] 电流太小(<{controller.calMin_mA}mA)，请加大外力")
                except ValueError:
                    print("[错误] 无效的数值格式")
        
        # 手动设定系数: KN:ID:系数
        elif buf.startswith("KN:"):
            parts = buf.split(":")
            if len(parts) >= 3:
                try:
                    servo_idx = int(parts[1]) - 1
                    new_k = float(parts[2])
                    if 0 <= servo_idx < len(servo_controllers):
                        servo_controllers[servo_idx].kN_per_mA = new_k
                        print(f"[舵机{servo_idx+1}] kN_per_mA set to {new_k:.6f}")
                except: print("Invalid Value")

        # 帮助
        elif buf == "HELP":
            print("\n=== 五舵机控制指令 ===")
            print("N:ID:力值    - 设定单个舵机目标力 (例: N:1:5)")
            print("NALL:力值    - 设定所有舵机目标力 (例: NALL:5)")
            print("KN:ID:系数   - 手动设定力系数 (例: KN:1:0.025)")
            print("HOLD:ID      - 保持舵机当前位置 (例: HOLD:1)")
            print("FREE:ID      - 舵机进入自由模式 (例: FREE:1)")
            print("CAL:ID:力值  - 标定舵机力系数 (例: CAL:1:3)")
            print("STATUS       - 查看所有舵机状态")
            print("EXIT         - 退出程序")
        
        # 退出
        elif buf == "EXIT":
            running = False
            print("正在退出...")
        
        else:
            print(f"[未知指令] {buf}")
    
    except Exception as e:
        print(f"[命令错误] {e}")

# ===== WiFi 服务器线程 =====
def wifi_server_thread():
    """WiFi 命令服务器"""
    HOST = '0.0.0.0'
    PORT = 8888
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server_socket.bind((HOST, PORT))
        server_socket.listen(1)
        print(f"=== WiFi Server Listening on {HOST}:{PORT} ===")
        
        while running:
            try:
                server_socket.settimeout(1.0)  # 设置超时以便检查 running 状态
                conn, addr = server_socket.accept()
                print(f"[WiFi] Connected by {addr}")
                
                try:
                    while running:
                        data = conn.recv(1024)
                        if not data:
                            break
                        cmd = data.decode('utf-8').strip()
                        if cmd:
                            print(f"[WiFi] Recv: {cmd}")
                            parse_command(cmd)
                            conn.sendall(b"CMD_RECEIVED\n")
                except Exception as e:
                    print(f"[WiFi] Connection Error: {e}")
                finally:
                    conn.close()
                    print(f"[WiFi] Disconnected {addr}")
            except socket.timeout:
                continue
            except Exception as e:
                if running:
                    print(f"[WiFi] Server Error: {e}")
                
    except Exception as e:
        print(f"[WiFi] Fatal Error: {e}")
    finally:
        server_socket.close()

# ===== 键盘输入线程 =====
def input_thread():
    """键盘命令输入"""
    print("=== 命令输入就绪 (输入 HELP 查看指令) ===")
    while running:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            buf = line.strip()
            if not buf:
                continue
            parse_command(buf)
        except Exception as e:
            print(f"[输入错误] {e}")

# ===== 初始化 =====
def setup():
    """初始化所有舵机"""
    global servo_controllers
    
    # 打开串口
    if portHandler.openPort():
        print("串口打开成功")
    else:
        print("串口打开失败")
        sys.exit(1)
    
    # 设置波特率
    if portHandler.setBaudRate(BAUDRATE):
        print("波特率设置成功")
    else:
        print("波特率设置失败")
        sys.exit(1)
    
    # 初始化每个舵机
    for controller in servo_controllers:
        servo_id = controller.servo_id
        
        # Ping 测试
        model_number, res, err = packetHandler.ping(portHandler, servo_id)
        if res != COMM_SUCCESS:
            print(f"[舵机{servo_id}] Ping 失败: {packetHandler.getTxRxResult(res)}")
            continue
        else:
            print(f"[舵机{servo_id}] Ping 成功, Model: {model_number}")
        
        # 配置舵机
        torqueOff(servo_id)
        write1Byte(servo_id, ADDR_OPERATING_MODE, OP_CURRENT_BASED_POSITION)
        write2Byte(servo_id, ADDR_CURRENT_LIMIT, controller.currentLimit_mA)
        write4Byte(servo_id, ADDR_PROFILE_VELOCITY, 200)
        write4Byte(servo_id, ADDR_PROFILE_ACCELERATION, 100)
        torqueOn(servo_id)
        
        # 读取初始位置
        controller.home_pos = read4ByteSigned(servo_id, ADDR_PRESENT_POSITION)
        controller.goal_pos = controller.home_pos
        write4Byte(servo_id, ADDR_GOAL_POSITION, controller.goal_pos)
        
        time.sleep(0.05)
    
    print("\n五舵机力反馈系统就绪")

# ===== 主控制循环 =====
def loop():
    """主控制循环，处理所有舵机的力反馈"""
    global servo_controllers, running
    
    last_print = time.time()
    
    while running:
        try:
            current_time = time.time()
            
            # 遍历每个舵机进行控制
            for controller in servo_controllers:
                if controller.holdMode or controller.freeModeActive:
                    continue
                
                if not controller.touchMode:
                    continue
                
                # 读取当前状态
                present_pos = read4ByteSigned(controller.servo_id, ADDR_PRESENT_POSITION)
                present_mA = read2ByteSigned(controller.servo_id, ADDR_PRESENT_CURRENT)
                
                # 软件滤波
                controller.mA_window.append(present_mA)
                if len(controller.mA_window) > controller.window_size:
                    controller.mA_window.pop(0)
                filt_mA = sum(controller.mA_window) / len(controller.mA_window)
                
                # 计算当前力
                estN = filt_mA * controller.kN_per_mA
                
                # 导纳控制
                error = estN - controller.targetForceN
                delta_pos = -controller.admittance_gain * error
                
                # 死区处理
                if abs(error) < controller.hysteresisN:
                    delta_pos = 0
                
                # 限幅处理
                if delta_pos > controller.max_step_per_loop:
                    delta_pos = controller.max_step_per_loop
                if delta_pos < -controller.max_step_per_loop:
                    delta_pos = -controller.max_step_per_loop
                
                # 更新目标位置
                if delta_pos != 0:
                    controller.goal_pos += delta_pos
                    write4Byte(controller.servo_id, ADDR_GOAL_POSITION, int(controller.goal_pos))
            
            # 定期打印状态
            if current_time - last_print > 1.0:
                active_servos = [c for c in servo_controllers if c.touchMode]
                if active_servos:
                    print(f"\n[状态] 活动舵机: {len(active_servos)}")
                    for c in active_servos:
                        ppos = read4ByteSigned(c.servo_id, ADDR_PRESENT_POSITION)
                        pcur = read2ByteSigned(c.servo_id, ADDR_PRESENT_CURRENT)
                        estN = pcur * c.kN_per_mA
                        err = estN - c.targetForceN
                        print(f"  舵机{c.servo_id}: POS={ppos}, CUR={pcur}mA, "
                              f"estN={estN:.2f}N, target={c.targetForceN:.1f}N, err={err:.2f}N")
                last_print = current_time
            
            time.sleep(0.005)  # 5ms 循环
            
        except KeyboardInterrupt:
            print("\n接收到中断信号...")
            running = False
            break
        except Exception as e:
            print(f"[循环错误] {e}")

# ===== 主函数 =====
if __name__ == '__main__':
    try:
        # 初始化
        setup()
        
        # 启动输入线程
        t_input = threading.Thread(target=input_thread, daemon=True)
        t_input.start()
        
        # 启动 WiFi 服务线程
        t_wifi = threading.Thread(target=wifi_server_thread, daemon=True)
        t_wifi.start()
        
        # 运行主循环
        loop()
        
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"[致命错误] {e}")
    finally:
        # 关闭所有舵机扭矩
        print("\n正在关闭舵机...")
        for controller in servo_controllers:
            torqueOff(controller.servo_id)
        
        # 关闭串口
        portHandler.closePort()
        print("程序已退出")
