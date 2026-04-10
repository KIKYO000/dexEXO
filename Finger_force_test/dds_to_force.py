#!/usr/bin/env python3
"""
DDS 触觉数据转力值桥接程序
接收灵巧手通过 DDS 发送的触觉数据，转换为力值后发送给 finger_force.py

功能:
1. 订阅 DDS 话题 rt/inspire_hand/touch/r
2. 使用标定公式将触觉原始值转换为力 (N)
3. 通过 TCP 发送 N:2:力值 命令给 finger_force.py

用法:
1. 先启动 finger_force.py
2. 再启动本程序: python3 dds_to_force.py
"""
import sys
import time
import socket
import signal
import threading

# ===== DDS SDK 路径 =====
SDK_PATH = "/home/pi/dexEXO/ftp/inspire_hand_ws/inspire_hand_sdk/inspire_sdkpy"
sys.path.insert(0, SDK_PATH)

try:
    from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelFactoryInitialize
    from inspire_sdkpy import inspire_dds
    DDS_AVAILABLE = True
except ImportError as e:
    print(f"[警告] DDS SDK 导入失败: {e}")
    print("[提示] 请确保路径正确且已安装 unitree_sdk2py 和 cyclonedds")
    DDS_AVAILABLE = False

# ===== 标定参数 (来自 touch_calibration.json) =====
# F(N) = k * raw_max + b
CALIBRATION_K = 0.00292650244415058227
CALIBRATION_B = -0.6037947156125716

# ===== 力值阈值 =====
FORCE_MIN = 0.0      # 最小力值 (N)
FORCE_MAX = 10.0     # 最大力值 (N)
FORCE_THRESHOLD = 0.1  # 低于此值视为无接触

# ===== TCP 连接参数 =====
TCP_HOST = "127.0.0.1"  # finger_force.py 地址
TCP_PORT = 8888         # finger_force.py 端口

# ===== 目标舵机 =====
TARGET_SERVO_ID = 2  # 当前只控制舵机2

# ===== DDS 话题 =====
# 左手: rt/inspire_hand/touch/r
# 右手: rt/inspire_hand_right/touch/r (或 rt/inspire_hand_r/touch/r，具体取决于灵巧手配置)
DDS_TOPIC = "rt/inspire_hand/touch/r"  # TODO: 根据实际配置修改

# ===== 更新频率控制 =====
UPDATE_INTERVAL = 0.02  # 50Hz 更新频率
PRINT_INTERVAL = 1.0    # 1Hz 打印状态

# ===== 零力持续发送 =====
ZERO_FORCE_SEND_COUNT = 10   # 力降为0时持续发送的次数，确保finger_force收到
ZERO_FORCE_SEND_INTERVAL = 0.05  # 零力命令发送间隔

# ===== 全局变量 =====
running = True
last_force_sent = 0.0
last_raw_value = 0
tcp_socket = None
tcp_lock = threading.Lock()
zero_force_remaining = 0      # 剩余需要发送的零力命令次数
last_zero_send_time = 0.0     # 上次发送零力命令的时间


def raw_to_force(raw_value: int) -> float:
    """
    将触觉原始值转换为力值 (N)
    使用标定公式: F(N) = k * raw_max + b
    如果计算结果为负，则取0
    """
    force = CALIBRATION_K * raw_value + CALIBRATION_B
    # 负值取0，正值限制最大值
    if force < 0:
        force = 0.0
    elif force > FORCE_MAX:
        force = FORCE_MAX
    return force


def connect_tcp() -> bool:
    """连接到 finger_force.py 的 TCP 服务器"""
    global tcp_socket
    
    try:
        with tcp_lock:
            if tcp_socket:
                try:
                    tcp_socket.close()
                except:
                    pass
            
            tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_socket.settimeout(5.0)
            tcp_socket.connect((TCP_HOST, TCP_PORT))
            print(f"[TCP] 已连接到 {TCP_HOST}:{TCP_PORT}")
            return True
    except Exception as e:
        print(f"[TCP] 连接失败: {e}")
        tcp_socket = None
        return False


def send_force_command(servo_id: int, force_n: float) -> bool:
    """
    发送力值命令给 finger_force.py
    命令格式: N:舵机ID:力值
    """
    global tcp_socket
    
    cmd = f"N:{servo_id}:{force_n:.2f}\n"
    
    try:
        with tcp_lock:
            if tcp_socket is None:
                return False
            tcp_socket.sendall(cmd.encode('utf-8'))
            # 接收确认
            response = tcp_socket.recv(64).decode('utf-8', errors='ignore')
            if "CMD_RECEIVED" in response:
                return True
    except Exception as e:
        print(f"[TCP] 发送失败: {e}")
        tcp_socket = None
        return False
    
    return False


class DDSTouchHandler:
    """DDS 触觉数据处理器"""
    
    def __init__(self):
        self.last_update = 0.0
        self.last_print = 0.0
        self.message_count = 0
        self.last_raw = 0
        self.last_force = 0.0
    
    def touch_callback(self, msg) -> None:
        """DDS 消息回调"""
        global last_force_sent, last_raw_value, zero_force_remaining, last_zero_send_time
        
        current_time = time.time()
        self.message_count += 1
        
        # 获取食指触觉数据
        # 注意: 标定时使用的是 fingerfour_top_touch (96个值)
        # 而不是 fingerfour_tip_touch (9个值)
        try:
            # 使用 top_touch 的最大值 (与标定工具一致)
            fingerfour_top = msg.fingerfour_top_touch
            if fingerfour_top and len(fingerfour_top) > 0:
                raw_value = max(fingerfour_top)
            else:
                raw_value = 0
            
            self.last_raw = raw_value
            last_raw_value = raw_value
            
            # 转换为力值
            force_n = raw_to_force(raw_value)
            self.last_force = force_n
            
            # 频率限制
            if current_time - self.last_update < UPDATE_INTERVAL:
                return
            self.last_update = current_time
            
            # === 力值发送逻辑 ===
            force_changed = abs(force_n - last_force_sent) > 0.05
            
            if force_n >= FORCE_THRESHOLD:
                # 有力时正常发送
                if force_changed:
                    if send_force_command(TARGET_SERVO_ID, force_n):
                        last_force_sent = force_n
                        zero_force_remaining = 0  # 有力时重置零力计数
                    else:
                        if connect_tcp():
                            if send_force_command(TARGET_SERVO_ID, force_n):
                                last_force_sent = force_n
                                zero_force_remaining = 0
            
            elif last_force_sent >= FORCE_THRESHOLD and force_n < FORCE_THRESHOLD:
                # 力刚降为0：触发持续零力发送
                zero_force_remaining = ZERO_FORCE_SEND_COUNT
                last_zero_send_time = 0.0  # 立即发送第一次
                print(f"[DDS] 力值降为0，启动持续零力发送 ({ZERO_FORCE_SEND_COUNT}次)")
            
            # 持续发送零力命令 (确保 finger_force 可靠收到)
            if zero_force_remaining > 0 and current_time - last_zero_send_time >= ZERO_FORCE_SEND_INTERVAL:
                if send_force_command(TARGET_SERVO_ID, 0.0):
                    last_force_sent = 0.0
                    zero_force_remaining -= 1
                    last_zero_send_time = current_time
                else:
                    if connect_tcp():
                        if send_force_command(TARGET_SERVO_ID, 0.0):
                            last_force_sent = 0.0
                            zero_force_remaining -= 1
                            last_zero_send_time = current_time
            
            # 定期打印状态
            if current_time - self.last_print >= PRINT_INTERVAL:
                # 显示 top_touch 的最大值
                zero_info = f" | zero_remaining={zero_force_remaining}" if zero_force_remaining > 0 else ""
                print(f"[DDS] top_max={raw_value:4d} -> force={force_n:.3f}N | "
                      f"sent={last_force_sent:.2f}N | msgs={self.message_count}{zero_info}")
                self.last_print = current_time
                self.message_count = 0
                
        except Exception as e:
            print(f"[DDS] 处理错误: {e}")


def signal_handler(signum, frame):
    """信号处理"""
    global running
    print("\n[信号] 正在停止...")
    running = False


def main():
    global running, tcp_socket
    
    print("=" * 50)
    print("DDS 触觉数据转力值桥接程序")
    print("=" * 50)
    print(f"标定参数: k={CALIBRATION_K:.8f}, b={CALIBRATION_B:.8f}")
    print(f"目标舵机: ID={TARGET_SERVO_ID}")
    print(f"TCP 目标: {TCP_HOST}:{TCP_PORT}")
    print(f"DDS 话题: {DDS_TOPIC}")
    print("=" * 50)
    
    if not DDS_AVAILABLE:
        print("[错误] DDS SDK 不可用，程序退出")
        return 1
    
    # 设置信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 连接 TCP
    print("[TCP] 正在连接 finger_force.py...")
    retry_count = 0
    while not connect_tcp() and running:
        retry_count += 1
        print(f"[TCP] 重试连接 ({retry_count})...")
        time.sleep(2.0)
        if retry_count >= 5:
            print("[错误] 无法连接到 finger_force.py，请确保它已启动")
            return 1
    
    if not running:
        return 0
    
    # 初始化 DDS
    print("[DDS] 正在初始化...")
    try:
        ChannelFactoryInitialize()
    except Exception as e:
        print(f"[DDS] 初始化失败: {e}")
        return 1
    
    # 创建订阅者
    handler = DDSTouchHandler()
    
    print(f"[DDS] 订阅话题: {DDS_TOPIC}")
    try:
        subscriber = ChannelSubscriber(DDS_TOPIC, inspire_dds.inspire_hand_touch)
        subscriber.Init(handler.touch_callback, 10)
    except Exception as e:
        print(f"[DDS] 订阅失败: {e}")
        return 1
    
    print("\n[就绪] 开始接收 DDS 触觉数据...")
    print("[提示] 按 Ctrl+C 退出\n")
    
    # 主循环
    try:
        while running:
            time.sleep(0.1)
            
            # 检查 TCP 连接
            with tcp_lock:
                if tcp_socket is None:
                    print("[TCP] 连接断开，尝试重连...")
                    connect_tcp()
                    
    except KeyboardInterrupt:
        pass
    
    # 清理
    print("\n[清理] 正在关闭...")
    
    # 发送零力命令
    try:
        if tcp_socket:
            send_force_command(TARGET_SERVO_ID, 0.0)
    except:
        pass
    
    # 关闭 TCP
    with tcp_lock:
        if tcp_socket:
            try:
                tcp_socket.close()
            except:
                pass
            tcp_socket = None
    
    print("[完成] 程序已退出")
    return 0


if __name__ == "__main__":
    sys.exit(main())
