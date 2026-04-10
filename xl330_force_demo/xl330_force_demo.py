import os
import sys
import time
import threading
import termios
import tty
import socket
from dynamixel_sdk import * # Uses Dynamixel SDK library

# ===== 硬件串口 & 舵机参数 =====
DEVICENAME          = '/dev/ttyAMA0'    # 树莓派串口端口，如果是GPIO可能是 /dev/ttyAMA0
BAUDRATE            = 57600
PROTOCOL_VERSION    = 2.0
DXL_ID              = 1

# XL330 Control Table Addresses
ADDR_OPERATING_MODE = 11
ADDR_CURRENT_LIMIT  = 38
ADDR_GOAL_CURRENT   = 102  # 目标电流（Current Control Mode 专用）
ADDR_TORQUE_ENABLE  = 64
ADDR_GOAL_POSITION  = 116
ADDR_PRESENT_CURRENT= 126
ADDR_PRESENT_POSITION= 132
ADDR_PROFILE_VELOCITY = 112
ADDR_PROFILE_ACCELERATION = 108

# Data Byte Lengths
LEN_OPERATING_MODE  = 1
LEN_CURRENT_LIMIT   = 2
LEN_TORQUE_ENABLE   = 1
LEN_GOAL_POSITION   = 4
LEN_PRESENT_CURRENT = 2
LEN_PRESENT_POSITION= 4

# Operating Modes
OP_CURRENT_CONTROL = 0  # 纯电流模式：直接控制输出电流，不锁定位置
OP_CURRENT_BASED_POSITION = 5  # 电流限制位置模式：会锁定位置

# ===== 目标 & 控制参数 =====
targetForceN = 0.0        # 目标力(N)
# 力换算系数：根据实测标定
# 标定方法：挂已知重物（如 500g=4.9N），读取稳定电流，计算 kN_per_mA = 力/电流
# 注意：XL330 测量的是输入电流，包含摩擦损耗，所以这个系数是"等效力"
kN_per_mA    = 0.04       # 力换算系数 (需根据实际标定调整)
forceDeadzone = 1.5       # 力控制死区 (N)，在目标力±死区内保持静止 - 增大以避免振荡
stepPulse    = 5          # 每次位置调整步长（pulse），越大响应越快但越容易抖动 - 减小以提高精度
currentLimit_mA = 700     # 电流上限 (mA)，对应最大输出力的安全保护
posThreshold = 100        # 位置偏差阈值（pulse），超过才认为是外力拉动（不是舵机自身跟随误差）
overloadCounter = 0       # 超载计数器，避免瞬时误触发

# ===== 触摸(touch)模式相关 =====
touchMode = False
touchGain_N_per_tick = 0.05
touchMaxN = 5.0
touchStartPos = 0
touchBaseN = 0.0
touchDirSign = 0
lastNonZeroSign = 0
touchStartMs = 0
touchRampMode = True
touchRampRateNPerSec = 0.5

# ===== 运行配置 =====
calMin_mA = 20      # 最小标定电流
freeModeActive = False
base_current_mA = 0 # 零点/底噪电流
do_tare = False     # 去皮标志位
use_hw_force_mode = False # 暂时关闭硬件模式，回归软件模式调试
use_current_mode = False  # 是否使用纯电流模式（不锁定位置，超载自然顺从）
# 硬件模式虽然稳定，但会失去位置控制能力，且无法处理摩擦力死区
# 我们需要用软件算法来补偿减速箱摩擦力
noLoadThreshN = 0.08
seekMode = False
seekMaxSteps = 30
seekStepCounter = 0
autoFree = True
holdMode = False
controlDir = 1 # 修改默认方向为 1 (正向)

home_pos = 0
goal_pos = 0

# 电流模式位置追踪
last_pos_imode = None  # 用于检测位置变化

# SDK Handlers
portHandler = PortHandler(DEVICENAME)
packetHandler = PacketHandler(PROTOCOL_VERSION)
dxl_lock = threading.Lock()

# 辅助函数：读取/写入
def read1Byte(addr):
    with dxl_lock:
        val, res, err = packetHandler.read1ByteTxRx(portHandler, DXL_ID, addr)
    if res != COMM_SUCCESS: print(packetHandler.getTxRxResult(res))
    elif err != 0: print(packetHandler.getRxPacketError(err))
    return val

def read2ByteSigned(addr):
    with dxl_lock:
        val, res, err = packetHandler.read2ByteTxRx(portHandler, DXL_ID, addr)
    if res != COMM_SUCCESS: print(packetHandler.getTxRxResult(res))
    elif err != 0: print(packetHandler.getRxPacketError(err))
    # Convert unsigned to signed 16-bit
    if val > 32767: val -= 65536
    return val

def read4ByteSigned(addr):
    with dxl_lock:
        val, res, err = packetHandler.read4ByteTxRx(portHandler, DXL_ID, addr)
    if res != COMM_SUCCESS: print(packetHandler.getTxRxResult(res))
    elif err != 0: print(packetHandler.getRxPacketError(err))
    # Convert unsigned to signed 32-bit
    if val > 2147483647: val -= 4294967296
    return val

def write1Byte(addr, val):
    with dxl_lock:
        packetHandler.write1ByteTxRx(portHandler, DXL_ID, addr, val)

def write2Byte(addr, val):
    with dxl_lock:
        packetHandler.write2ByteTxRx(portHandler, DXL_ID, addr, val)

def write2ByteSigned(addr, val):
    """写入有符号2字节值（用于目标电流等）"""
    with dxl_lock:
        # 将有符号值转换为无符号表示
        if val < 0:
            val = 65536 + val  # 补码转换
        packetHandler.write2ByteTxRx(portHandler, DXL_ID, addr, val)

def write4Byte(addr, val):
    with dxl_lock:
        packetHandler.write4ByteTxRx(portHandler, DXL_ID, addr, int(val))

def torqueOn():
    write1Byte(ADDR_TORQUE_ENABLE, 1)

def torqueOff():
    write1Byte(ADDR_TORQUE_ENABLE, 0)

def enterFreeMode():
    global freeModeActive
    torqueOff()
    freeModeActive = True
    print("[FREE] 扭矩关闭，自由跟随(完全无电)")

def exitFreeMode():
    global freeModeActive, goal_pos
    ppos = read4ByteSigned(ADDR_PRESENT_POSITION)
    torqueOn()
    goal_pos = ppos
    write4Byte(ADDR_GOAL_POSITION, goal_pos)
    freeModeActive = False
    print("[FREE] 扭矩开启，恢复控制")

# 键盘输入处理线程
def parse_command(buf):
    global targetForceN, touchMode, touchStartPos, touchBaseN, touchDirSign, touchStartMs, seekMode, seekStepCounter, holdMode, touchGain_N_per_tick, touchMaxN, touchRampMode, touchRampRateNPerSec, seekMaxSteps, calMin_mA, home_pos, goal_pos, kN_per_mA, stepPulse, hysteresisN, currentLimit_mA, noLoadThreshN, controlDir, autoFree, freeModeActive, lastNonZeroSign, do_tare, base_current_mA, use_hw_force_mode, use_current_mode

    try:
        buf = buf.replace("：", ":") 
        buf = buf.upper()
        
        if buf == "ZERO":
            do_tare = True
            print("[CMD] 请求去皮/归零... (将在下一次循环中执行)")

        elif buf.startswith("N:"):
            try:
                # N:5 -> 设定目标力为 5N
                val = float(buf[2:])
                print(f"[OK] 收到目标力指令: {val}N")
                
                if val == 0:
                    targetForceN = 0
                    touchMode = False
                    seekMode = False
                    # 恢复最大电流限制，保持当前位置
                    write2Byte(ADDR_CURRENT_LIMIT, currentLimit_mA)
                    ppos = read4ByteSigned(ADDR_PRESENT_POSITION)
                    write4Byte(ADDR_GOAL_POSITION, ppos)
                    print("[INFO] 目标力为0，保持当前位置")
                else:
                    if freeModeActive: exitFreeMode()
                    
                    targetForceN = abs(val)
                    touchMode = True
                    
                    # 根据目标力设置电流限制（安全保护）
                    # 电流模式：不设置电流限制（由目标电流控制）
                    # 位置模式：设置电流限制为目标力对应值（极低，便于被拉动）
                    if use_current_mode:
                        # 电流模式：电流限制不起作用，使用最大值
                        required_mA = currentLimit_mA
                        print(f"[CURRENT-MODE] 目标力={targetForceN}N | 目标电流={int(targetForceN/kN_per_mA)}mA")
                    else:
                        # 位置模式：电流限制 = 目标力 × 1.05（只留5%裕量，让舵机易被拉动）
                        required_mA = int(targetForceN / kN_per_mA * 1.05)
                        if required_mA > currentLimit_mA:
                            required_mA = currentLimit_mA
                        if required_mA < 100:
                            required_mA = 100  # 最小电流保证能动
                        
                        write2Byte(ADDR_CURRENT_LIMIT, required_mA)
                        print(f"[FORCE-CTRL] 目标力={targetForceN}N | 电流限制={required_mA}mA (1.05x裕量，易拉动) | 死区=±{forceDeadzone}N")

            except: print("Invalid Number")

        elif buf.startswith("TOUCH"):
            # 兼容旧指令，默认执行 N:3 的效果
            print("[INFO] TOUCH 指令兼容模式 -> 执行 N:3")
            parse_command("N:3")

        elif buf == "HOLD":
            holdMode = True
            print("[HOLD] ON - 固定当前位置，关闭自动自由/跟随/寻触")

        elif buf == "FREE":
            targetForceN = 0
            touchMode = False
            seekMode = False
            holdMode = False
            enterFreeMode()

        elif buf.startswith("CAL:"):
            try:
                real_force = float(buf[4:])
                pcur = read2ByteSigned(ADDR_PRESENT_CURRENT)
                print(f"[CAL] 检测到电流: {pcur} mA")
                
                if abs(pcur) < calMin_mA:
                    print(f"[WARN] 电流太小(<{calMin_mA}mA)! 请加大外力后再次标定。")
                    print("       提示: 用手用力推(正力)或拉(负力)舵机")
                    print("             然后立即发送 CAL:1 或 CAL:-1")
                else:
                    # 强制系数为正数，确保力与电流同号 (负电流=负力)
                    new_k = abs(real_force / float(pcur))
                    
                    # 安全检查：防止系数过大
                    if new_k > 0.1:
                        print(f"[ERROR] 标定系数过大 ({new_k:.6f})! 忽略此次标定。")
                        print("        原因: 电流相对于力太小。请确保舵机真的在用力。")
                    else:
                        old_kN = kN_per_mA
                        kN_per_mA = new_k
                        print(f"[OK] kN_per_mA: {old_kN:.6f} -> {kN_per_mA:.6f}")
                        print(f"     即: {pcur} mA = {real_force:.2f} N (方向已自动匹配)")
            except: print("Invalid Value")

        elif buf == "DIRREV" or buf == "DIRREV:ON":
            controlDir = -1
            print("[OK] DIRREV=ON (控制方向反转)")

        elif buf == "DIRREV:OFF":
            controlDir = +1
            print("[OK] DIRREV=OFF (控制方向默认)")

        elif buf.startswith("DIR:"):
            try:
                v = int(buf[4:])
                controlDir = +1 if v >= 0 else -1
                print(f"[OK] controlDir={controlDir}")
            except: print("Invalid Value")

        elif buf.startswith("KN:"):
            try:
                kN_per_mA = float(buf[3:])
                print(f"[OK] kN_per_mA={kN_per_mA:.6f} N/mA")
            except: print("Invalid Value")

        elif buf.startswith("STEP:"):
            try:
                stepPulse = int(buf[5:])
                print(f"[OK] stepPulse={stepPulse} pulse/cycle")
            except: print("Invalid Value")

        elif buf.startswith("DEADZONE:"):
            try:
                forceDeadzone = float(buf[9:])
                print(f"[OK] forceDeadzone={forceDeadzone:.2f} N")
            except: print("Invalid Value")

        elif buf.startswith("POS:"):
            try:
                target_pos = int(buf[4:])
                write4Byte(ADDR_GOAL_POSITION, target_pos)
                goal_pos = target_pos
                print(f"[OK] Moving to position: {target_pos}")
            except: print("Invalid Value")
        
        elif buf == "STATUS":
            ppos = read4ByteSigned(ADDR_PRESENT_POSITION)
            pcur = read2ByteSigned(ADDR_PRESENT_CURRENT)
            estN = pcur * kN_per_mA
            print("=== 实时状态 ===")
            print(f"位置: {ppos}")
            print(f"电流: {pcur} mA")
            dir_str = "(CCW/推)" if estN > 0 else ("(CW/拉)" if estN < 0 else "(无力)")
            print(f"估算力: {estN:.2f} N {dir_str}")
            print("提示: 顺时针(CW)用力通常对应负电流，逆时针(CCW)对应正电流")

        elif buf == "INFO":
            print("=== 当前参数 ===")
            print(f"targetForceN = {targetForceN:.3f} N")
            print(f"kN_per_mA = {kN_per_mA:.6f} N/mA")
            print(f"forceDeadzone = {forceDeadzone:.2f} N")
            print(f"stepPulse = {stepPulse} pulse/cycle")
            print(f"currentLimit_mA = {currentLimit_mA} mA")
            print(f"base_current_mA = {base_current_mA:.1f} mA (ZERO offset)")
            print(f"freeMode = {'ON' if freeModeActive else 'OFF'}")
            print(f"autoFree = {'ON' if autoFree else 'OFF'}")
            print(f"holdMode = {'ON' if holdMode else 'OFF'}")
            print(f"touchMode = {'ON' if touchMode else 'OFF'}")
            ppos = read4ByteSigned(ADDR_PRESENT_POSITION)
            pcur = read2ByteSigned(ADDR_PRESENT_CURRENT)
            print(f"present_pos = {ppos}")
            print(f"present_cur = {pcur} mA")
            print(f"present_force = {pcur * kN_per_mA:.2f} N (estimated)")

        elif buf == "TEST":
            print("[TEST] 移动测试开始...")
            # 暂停 Loop 线程的干扰
            wasHold = holdMode
            holdMode = True
            
            try:
                test_home = read4ByteSigned(ADDR_PRESENT_POSITION)
                print(f"  起始位置: {test_home}")
                
                print("  -> 向CCW(正)方向移动 500 脉冲")
                write4Byte(ADDR_GOAL_POSITION, test_home + 500)
                time.sleep(1.5)
                pos1 = read4ByteSigned(ADDR_PRESENT_POSITION)
                print(f"  当前位置: {pos1}")
                
                print("  -> 向CW(负)方向移动 500 脉冲")
                write4Byte(ADDR_GOAL_POSITION, test_home - 500)
                time.sleep(1.5)
                pos2 = read4ByteSigned(ADDR_PRESENT_POSITION)
                print(f"  当前位置: {pos2}")
                
                print("  -> 回到起始位置")
                write4Byte(ADDR_GOAL_POSITION, test_home)
                time.sleep(1.0)
                pos3 = read4ByteSigned(ADDR_PRESENT_POSITION)
                print(f"  最终位置: {pos3}")
            except Exception as e:
                print(f"Test Error: {e}")
            finally:
                holdMode = wasHold
                print("[TEST] 测试结束")

        elif buf.startswith("CL:"):
            # 动态调整电流上限: CL:700 表示 700mA
            try:
                new_limit = int(buf[3:])
                if new_limit <= 0:
                    print("[CL] 数值必须为正")
                else:
                    old = currentLimit_mA
                    currentLimit_mA = new_limit
                    write2Byte(ADDR_CURRENT_LIMIT, currentLimit_mA)
                    print(f"[CL] currentLimit_mA: {old} -> {currentLimit_mA} mA")
            except Exception as e:
                print(f"[CL] 无效数值: {e}")

        elif buf == "IMODE":
            # 切换到纯电流模式（不锁定位置）
            global last_pos_imode
            use_current_mode = not use_current_mode
            if use_current_mode:
                torqueOff()
                write1Byte(ADDR_OPERATING_MODE, OP_CURRENT_CONTROL)
                torqueOn()
                last_pos_imode = None  # 重置位置追踪
                print("[IMODE] ✅ 已切换到纯电流模式")
                print("[INFO] 舵机将只输出目标电流，不锁定位置")
                print("[INFO] 当外力 > 目标力时，舵机会自然顺从")
            else:
                torqueOff()
                write1Byte(ADDR_OPERATING_MODE, OP_CURRENT_BASED_POSITION)
                torqueOn()
                last_pos_imode = None  # 重置位置追踪
                print("[IMODE] ✅ 已切换回位置模式")
                print("[INFO] 舵机将锁定位置（使用电流限制）")

        elif buf == "HELP":
            print("=== 指令列表 ===")
            print("N:5       - 设定目标力为5N (力不够→卷绳, 力过大→放绳, 力平衡→静止)")
            print("ZERO      - 归零/去皮 (消除空载时的底噪电流)")
            print("CL:700    - 设置电流上限为700mA (安全保护)")
            print("IMODE     - 切换纯电流模式 (不锁定位置，超载自然顺从)")
            print("FREE      - 自由模式(扭矩关闭)")
            print("HOLD      - 保持当前位置(暂停力控)")
            print("CAL:3     - 标定: 当前负载为3N (用于校准kN_per_mA)")
            print("STATUS    - 查看当前状态(位置/电流/力)")
            print("INFO      - 查看所有参数")
            print("TEST      - 简单运动测试")
            print("KN:0.04   - 手动设定力系数 (N/mA)")
            print("STEP:10   - 设定位置步长 (pulse/cycle, 影响响应速度)")
            print("DEADZONE:0.3 - 设定力控死区 (N, 影响稳定性)")

        else:
            print("Unknown Command")

    except Exception as e:
        print(f"Command Error: {e}")

def input_thread():
    print("=== 命令输入就绪 (输入 HELP 查看指令) ===")
    while True:
        try:
            line = sys.stdin.readline()
            if not line: break
            buf = line.strip()
            if not buf: continue
            parse_command(buf)
        except Exception as e:
            print(f"Stdin Error: {e}")

def wifi_server_thread():
    HOST = '0.0.0.0'
    PORT = 8888
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server_socket.bind((HOST, PORT))
        server_socket.listen(1)
        print(f"=== WiFi Server Listening on {HOST}:{PORT} ===")
        
        while True:
            conn, addr = server_socket.accept()
            print(f"[WiFi] Connected by {addr}")
            try:
                while True:
                    data = conn.recv(1024)
                    if not data: break
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
                
    except Exception as e:
        print(f"[WiFi] Server Error: {e}")

def setup():
    global home_pos, goal_pos, freeModeActive

    # Open port
    if portHandler.openPort():
        print("Succeeded to open the port")
    else:
        print("Failed to open the port")
        sys.exit(0)

    # Set port baudrate
    if portHandler.setBaudRate(BAUDRATE):
        print("Succeeded to change the baudrate")
    else:
        print("Failed to change the baudrate")
        sys.exit(0)

    # Ping
    model_number, res, err = packetHandler.ping(portHandler, DXL_ID)
    if res != COMM_SUCCESS:
        print(f"Ping Failed: {packetHandler.getTxRxResult(res)}")
        sys.exit(0)
    else:
        print(f"Ping Succeeded. ID: {DXL_ID}, Model: {model_number}")

    # Initialization
    torqueOff()
    write1Byte(ADDR_OPERATING_MODE, OP_CURRENT_BASED_POSITION)
    write2Byte(ADDR_CURRENT_LIMIT, currentLimit_mA)
    write4Byte(ADDR_PROFILE_VELOCITY, 200)
    write4Byte(ADDR_PROFILE_ACCELERATION, 100)
    torqueOn()
    time.sleep(0.1)
    freeModeActive = False

    home_pos = read4ByteSigned(ADDR_PRESENT_POSITION)
    goal_pos = home_pos
    write4Byte(ADDR_GOAL_POSITION, goal_pos)
    
    print("DexEXO XL330 Demo Ready (Python Version)")

def loop():
    global goal_pos, lastNonZeroSign, targetForceN, touchDirSign, seekStepCounter, freeModeActive, touchBaseN, do_tare, base_current_mA

    lastPrint = 0
    stalled_counter = 0  # 卡住计数器
    # --- 软件滤波缓存 ---
    mA_window = []  # 电流滑动窗口
    window_size = 15 # 滤波窗口大小 - 减小以加快响应（避免滞后导致振荡）
    
    while True:
        # 读取状态
        present_pos = read4ByteSigned(ADDR_PRESENT_POSITION)
        present_mA = read2ByteSigned(ADDR_PRESENT_CURRENT)
        
        # --- 软件滤波 ---
        mA_window.append(present_mA)
        if len(mA_window) > window_size:
            mA_window.pop(0)
        filt_mA = sum(mA_window) / len(mA_window)
        
        # --- 去皮/归零逻辑 ---
        if do_tare:
            base_current_mA = filt_mA
            do_tare = False
            print(f"[ZERO] 已归零，当前底噪电流: {base_current_mA:.1f} mA")

        # 计算当前力 (N)
        # 扣除底噪电流
        estN = (filt_mA - base_current_mA) * kN_per_mA

        # 自动自由模式逻辑 (保持原有)
        if autoFree:
            if holdMode:
                if freeModeActive: exitFreeMode()
            elif not touchMode and targetForceN == 0:
                if not freeModeActive: enterFreeMode()
            else:
                if freeModeActive: exitFreeMode()

        # --- 核心力控逻辑 ---
        if touchMode and not holdMode and not freeModeActive:
            if use_current_mode:
                # === 纯电流模式 + 位置反馈检测 (改进版) ===
                # 
                # 问题诊断：齿轮箱自锁太强，即使20N外力也拉不动位置
                # 根本原因：电流模式下静止时，齿轮箱自锁能抵抗远超目标力的外力
                # 
                # 新策略：不依赖位置变化检测，而是切换回位置模式但降低电流限制
                # → 这样可以保持柔顺性，超载时自然被拉动
                
                global last_pos_imode
                
                # 计算目标电流幅度（绝对值）
                target_current_abs = int(abs(targetForceN) / kN_per_mA)
                
                # 保存上一次位置（用于检测运动方向）
                if last_pos_imode is None:
                    last_pos_imode = present_pos
                
                # 计算位置变化（正值=卷绳方向，负值=放绳方向）
                pos_delta = present_pos - last_pos_imode
                last_pos_imode = present_pos
                
                # 策略：检测是否被外力拉动（位置往放绳方向变化）
                # 降低阈值到 3（因为观察到 ±1-2 是噪声）
                if pos_delta < -3:
                    # 位置减小（往放绳方向） → 被外力拉动（超载）
                    # 立即降低电流到 0，完全释放
                    goal_current = 0
                    action = "⚡CURRENT_RELEASE"
                    
                elif pos_delta > 5:
                    # 位置增大（往卷绳方向） → 正常卷绳中
                    goal_current = target_current_abs
                    action = "↑CURRENT_REEL"
                    
                else:
                    # 位置变化小（-3 到 +5） → 可能卡住或平衡
                    # 关键：持续输出目标电流，不要停止
                    # 如果真的平衡，外力会推动舵机；如果卡住，需要维持力
                    goal_current = target_current_abs
                    action = "●CURRENT_HOLD"
                
                # 写入目标电流
                write2ByteSigned(ADDR_GOAL_CURRENT, goal_current)
                
            elif use_hw_force_mode:
                pass
            else:
                global overloadCounter
                
                # 计算力误差：目标力 - 当前力
                force_error = targetForceN - estN
                
                # 计算位置偏差（舵机被外力"拉偏"的程度）
                pos_error = present_pos - goal_pos
                
                # === 动态位置偏差阈值（根据目标力计算）===
                # 原理：当舵机用 targetForceN 的力锁定时，如果外力 > targetForceN，
                # 舵机会被拉偏。我们设定：允许的位置偏差 = 目标力对应的"容忍度"
                # 计算公式：允许被拉偏的距离 ∝ (外力 - 目标力) / 舵机刚度
                # 简化：每 1N 的超载允许 20 步的偏差（可调）
                dynamic_posThreshold = max(50, min(200, targetForceN * 15))
                # 解释：目标力越大，允许的位置偏差越大
                # N:1 → 阈值 15 步（但最小 50）
                # N:5 → 阈值 75 步
                # N:7 → 阈值 105 步
                # N:10 → 阈值 150 步
                # N:15+ → 阈值 200 步（封顶）
                
                # === 混合判断逻辑（改进：动态阈值 + 持续性检测）===
                # 优先级1：如果位置被明显拉偏（舵机被外力拉动），说明外部负载 > 目标力
                if abs(pos_error) > dynamic_posThreshold:
                    # 增加计数器，避免瞬时误触发
                    overloadCounter += 1
                    
                    # 只有连续 3 次以上检测到超载，才真正触发顺从动作
                    if overloadCounter >= 3:
                        # 外力方向判断：
                        # - 如果 pos_error > 0（实际位置 > 目标），说明被往"卷绳"方向拉
                        #   → 舵机已经被拉到"卷过头"，应该继续卷绳（顺从外力）
                        # - 如果 pos_error < 0（实际位置 < 目标），说明被往"放绳"方向拉
                        #   → 舵机已经被拉到"放过头"，应该继续放绳（顺从外力）
                        if pos_error > 0:
                            # 被拉向卷绳方向（位置变大）→ 顺从外力，继续卷绳
                            goal_pos += stepPulse * 2  # 用更大步长快速顺从
                            action = "OVERLOAD_REEL"
                        else:
                            # 被拉向放绳方向（位置变小）→ 顺从外力，继续放绳
                            goal_pos -= stepPulse * 2
                            action = "OVERLOAD_RELEASE"
                    else:
                        # 还在确认中：
                        # 关键修正：重新同步 goal_pos，避免偏差累积导致卡死
                        goal_pos = present_pos
                        action = "CHECKING"
                        # 然后按正常力控小步调整
                        if force_error > forceDeadzone:
                            goal_pos += stepPulse
                        elif force_error < -forceDeadzone:
                            goal_pos -= stepPulse
                else:
                    # 位置偏差不大，重置计数器
                    overloadCounter = 0
                
                # 优先级2：如果位置偏差不大，按电流估算的力误差控制
                # 关键改进：即使位置偏差不大，也要检查是否被"拉住不动"
                if abs(pos_error) <= dynamic_posThreshold:
                    # 检测是否被外力卡住（位置不变 + 电流接近目标）
                    # 计算目标电流（1.05倍裕量）
                    target_mA = int(targetForceN / kN_per_mA * 1.05)
                    # 如果电流接近目标电流（说明达到限制），且还想继续卷绳
                    # 这意味着：要么到达机械极限，要么外力 > 目标力
                    is_stalled = (present_mA > target_mA * 0.80) and (action == "REEL_IN")
                    
                    if is_stalled:
                        # 被卡住：停止卷绳，保持当前位置
                        stalled_counter += 1
                        
                        if stalled_counter > 10:
                            # 卡住超过10次（约1秒）→ 主动放松一点
                            goal_pos = present_pos - stepPulse * 3  # 往回退3步
                            action = "⚠️STALLED_RELEASE"
                            stalled_counter = 0  # 重置计数器
                        else:
                            action = "⚠️STALLED"
                            goal_pos = present_pos  # 同步位置，不要继续卷
                        
                    elif force_error > forceDeadzone:
                        stalled_counter = 0  # 重置卡住计数
                        # 情况1：当前力 < 目标力 - 死区 → 需要卷绳（增加张力）
                        goal_pos += stepPulse
                        action = "REEL_IN"
                        
                    elif force_error < -forceDeadzone:
                        stalled_counter = 0  # 重置卡住计数
                        # 情况2：当前力 > 目标力 + 死区 → 需要放绳（减小张力）
                        goal_pos -= stepPulse
                        action = "RELEASE"
                        
                    else:
                        stalled_counter = 0  # 重置卡住计数
                        # 情况3：力在目标 ± 死区内 → 保持当前位置
                        action = "HOLD"
                
                # 写入目标位置（CHECKING 状态也要写入，否则会卡住）
                if action != "HOLD":
                    write4Byte(ADDR_GOAL_POSITION, int(goal_pos))

        # 打印状态
        if targetForceN != 0 and (time.time() * 1000 - lastPrint > 500):
            force_err = targetForceN - estN
            
            if use_current_mode:
                # 电流模式状态显示
                # action 已在电流模式逻辑中设置
                if 'action' in locals():
                    if action == "CURRENT_REEL":
                        status = "⚡CURRENT_REEL (卷绳)"
                    elif action == "CURRENT_RELEASE":
                        status = "⚡CURRENT_RELEASE (放绳/顺从)"
                    elif action == "CURRENT_HOLD":
                        status = "⚡CURRENT_HOLD (维持)"
                    else:
                        status = "⚡CURRENT_MODE"
                else:
                    status = "⚡CURRENT_MODE"
                
                # 添加 pos_delta 调试信息
                if 'action' in locals():
                    print(f"POS={present_pos} (Δ={pos_delta:+4d}) | CUR={present_mA:3d}mA | estN={estN:4.1f}N | target={targetForceN:.1f}N | err={force_err:+5.2f}N | {status}")
                else:
                    print(f"POS={present_pos} | CUR={present_mA:3d}mA | estN={estN:4.1f}N | target={targetForceN:.1f}N | err={force_err:+5.2f}N | {status}")
            else:
                # 位置模式状态显示
                pos_err = present_pos - goal_pos
                # 计算动态阈值（用于显示）
                dynamic_threshold = max(50, min(200, targetForceN * 15))
                
                # 判断当前动作状态（加入位置偏差信息 + 计数器）
                if abs(pos_err) > dynamic_threshold and overloadCounter >= 3:
                    if pos_err > 0:
                        status = f"🔴OVERLOAD[{overloadCounter}](+{pos_err}>{dynamic_threshold:.0f}) ↓REEL"
                    else:
                        status = f"🔴OVERLOAD[{overloadCounter}]({pos_err}<-{dynamic_threshold:.0f}) ↑RELEASE"
                elif abs(pos_err) > dynamic_threshold:
                    status = f"⚠️CHECKING[{overloadCounter}]({pos_err:+d}>{dynamic_threshold:.0f})"
                elif force_err > forceDeadzone:
                    status = "↓REEL_IN"
                elif force_err < -forceDeadzone:
                    status = "↑RELEASE"
                else:
                    status = "●HOLD"
                
                print(f"POS={present_pos} | CUR={present_mA:3d}mA | estN={estN:4.1f}N | target={targetForceN:.1f}N | err={force_err:+5.2f}N | {status}")
            
            lastPrint = time.time() * 1000

        # 保持模式
        if holdMode:
            pass # 保持不动
        
        time.sleep(0.005) # 5ms delay

if __name__ == '__main__':
    setup()
    
    # 启动输入线程
    t = threading.Thread(target=input_thread)
    t.daemon = True
    t.start()
    
    # 启动WiFi服务线程
    t_wifi = threading.Thread(target=wifi_server_thread)
    t_wifi.daemon = True
    t_wifi.start()
    
    try:
        loop()
    except KeyboardInterrupt:
        print("Shutting down...")
        torqueOff()
        portHandler.closePort()
