#!/usr/bin/env python3
"""
五指 DDS 触觉数据转力值桥接程序
接收灵巧手五根手指通过 DDS 发送的触觉数据，转换为力值后发送给 finger_force.py

DDS 字段 → 手指 → 舵机 映射:
  fingerfive_top_touch  (96值) → 大拇指 → 舵机1
  fingerfour_top_touch  (96值) → 食指   → 舵机2
  fingerthree_top_touch (96值) → 中指   → 舵机3
  fingertwo_top_touch   (96值) → 无名指 → 舵机4
  fingerone_top_touch   (96值) → 小指   → 舵机5

用法:
1. 先启动 Headless_driver_r.py (终端1)
2. 启动 finger_force.py (终端2)
3. 启动本程序: python3 dds_to_force.py (终端3)
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

# ===== 标定参数 =====
# F(N) = k * raw_max + b
# 默认标定参数 (食指/中指/无名指/小指共用)
CALIBRATION_K = 0.00292650244415058227
CALIBRATION_B = -0.6037947156125716

# 大拇指单独标定参数 (标定后填入实际值)
# TODO: 在树莓派上运行 python touch_calibration.py 1 标定后替换
THUMB_CALIBRATION_K = 0.004420145759358057  # ← 标定后替换
THUMB_CALIBRATION_B = -1.0701492398616255     # ← 标定后替换

# ===== 力值阈值 =====
FORCE_MIN = 0.0
FORCE_MAX = 10.0
FORCE_THRESHOLD = 0.3       # 低于此值视为无接触 (提高避免边缘跳变)
FORCE_THRESHOLD_OFF = 0.15  # 降到此值以下才认为真正松手 (迟滞)

# ===== TCP 连接参数 =====
TCP_HOST = "127.0.0.1"
TCP_PORT = 8888

# ===== DDS 话题 =====
DDS_TOPIC = "rt/inspire_hand/touch/r"

# ===== 更新频率控制 =====
UPDATE_INTERVAL = 0.02   # 50Hz
PRINT_INTERVAL = 1.0     # 1Hz 打印

# ===== 零力持续发送 =====
ZERO_FORCE_SEND_COUNT = 10
ZERO_FORCE_SEND_INTERVAL = 0.05

# ===== 五指映射 =====
# DDS 字段名 → (舵机ID, 手指名)
FINGER_MAP = [
    # (DDS 字段名,              舵机ID, 手指名)
    ("fingerfive_top_touch",     1,     "大拇指"),
    ("fingerfour_top_touch",     2,     "食指"),
    ("fingerthree_top_touch",    3,     "中指"),
    ("fingertwo_top_touch",      4,     "无名指"),
    ("fingerone_top_touch",      5,     "小指"),
]

# ===== 全局变量 =====
running = True
tcp_socket = None
tcp_lock = threading.Lock()

# 每根手指的状态
class FingerState:
    def __init__(self, servo_id: int, name: str):
        self.servo_id = servo_id
        self.name = name
        self.last_force_sent = 0.0
        self.last_raw = 0
        self.last_force = 0.0
        self.zero_force_remaining = 0
        self.last_zero_send_time = 0.0
        self.is_active = False  # 迟滞：当前是否处于有力状态

finger_states = [FingerState(servo_id, name) for _, servo_id, name in FINGER_MAP]


def raw_to_force(raw_value: int, servo_id: int = 0) -> float:
    """将触觉原始值转换为力值 (N)，大拇指(servo_id=1)使用独立标定参数"""
    if servo_id == 1:
        force = THUMB_CALIBRATION_K * raw_value + THUMB_CALIBRATION_B
    else:
        force = CALIBRATION_K * raw_value + CALIBRATION_B
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
    """发送力值命令: N:舵机ID:力值"""
    global tcp_socket

    cmd = f"N:{servo_id}:{force_n:.2f}\n"

    try:
        with tcp_lock:
            if tcp_socket is None:
                return False
            tcp_socket.sendall(cmd.encode('utf-8'))
            # 接收确认
            tcp_socket.settimeout(0.5)
            try:
                response = tcp_socket.recv(64).decode('utf-8', errors='ignore')
                if "CMD_RECEIVED" in response:
                    return True
            except socket.timeout:
                return True  # 超时但不一定失败
    except Exception as e:
        print(f"[TCP] 发送失败: {e}")
        tcp_socket = None
        return False

    return False


def send_batch_commands(commands: list) -> bool:
    """批量发送多条命令 (减少TCP往返)"""
    global tcp_socket

    if not commands:
        return True

    batch = "".join(f"N:{sid}:{frc:.2f}\n" for sid, frc in commands)

    try:
        with tcp_lock:
            if tcp_socket is None:
                return False
            tcp_socket.sendall(batch.encode('utf-8'))
            tcp_socket.settimeout(0.5)
            try:
                tcp_socket.recv(256)
            except socket.timeout:
                pass
            return True
    except Exception as e:
        print(f"[TCP] 批量发送失败: {e}")
        tcp_socket = None
        return False


class DDSTouchHandler:
    """DDS 五指触觉数据处理器"""

    def __init__(self):
        self.last_update = 0.0
        self.last_print = 0.0
        self.message_count = 0

    def touch_callback(self, msg) -> None:
        """DDS 消息回调 — 处理所有五根手指"""
        current_time = time.time()
        self.message_count += 1

        try:
            # 频率限制
            if current_time - self.last_update < UPDATE_INTERVAL:
                return
            self.last_update = current_time

            # 使用字典收集命令: servo_id → force_n (同一舵机只保留最终值)
            cmd_dict = {}

            for i, (field_name, servo_id, finger_name) in enumerate(FINGER_MAP):
                fs = finger_states[i]

                # 获取该手指的触觉数据
                touch_data = getattr(msg, field_name, None)
                if touch_data and len(touch_data) > 0:
                    raw_value = max(touch_data)
                else:
                    raw_value = 0

                fs.last_raw = raw_value
                force_n = raw_to_force(raw_value, servo_id)
                fs.last_force = force_n

                # === 力值发送逻辑 (带迟滞) ===
                force_changed = abs(force_n - fs.last_force_sent) > 0.05

                # 迟滞判断: 上升用 FORCE_THRESHOLD, 下降用 FORCE_THRESHOLD_OFF
                if fs.is_active:
                    has_force = (force_n >= FORCE_THRESHOLD_OFF)
                else:
                    has_force = (force_n >= FORCE_THRESHOLD)

                if has_force:
                    fs.is_active = True
                    # 有力时发送 (正力优先级最高)
                    if force_changed:
                        cmd_dict[servo_id] = force_n
                        fs.last_force_sent = force_n
                        fs.zero_force_remaining = 0  # 取消零力发送

                elif fs.is_active and not has_force:
                    # 力降到迟滞下限以下：触发持续零力发送
                    fs.is_active = False
                    fs.zero_force_remaining = ZERO_FORCE_SEND_COUNT
                    fs.last_zero_send_time = current_time
                    if servo_id not in cmd_dict:  # 不覆盖正力命令
                        cmd_dict[servo_id] = 0.0
                    fs.last_force_sent = 0.0

                elif fs.zero_force_remaining > 0 and current_time - fs.last_zero_send_time >= ZERO_FORCE_SEND_INTERVAL:
                    # 持续零力发送 (仅当该舵机没有正力时)
                    if servo_id not in cmd_dict:
                        cmd_dict[servo_id] = 0.0
                    fs.last_force_sent = 0.0
                    fs.zero_force_remaining -= 1
                    fs.last_zero_send_time = current_time

            # 转为列表批量发送
            batch_cmds = list(cmd_dict.items())
            if batch_cmds:
                if not send_batch_commands(batch_cmds):
                    if connect_tcp():
                        send_batch_commands(batch_cmds)

            # 定期打印状态
            if current_time - self.last_print >= PRINT_INTERVAL:
                lines = []
                for i, fs in enumerate(finger_states):
                    lines.append(f"{fs.name}={fs.last_force:.2f}N(raw={fs.last_raw})")
                zero_info = sum(1 for fs in finger_states if fs.zero_force_remaining > 0)
                zero_str = f" | zero_pending={zero_info}" if zero_info > 0 else ""
                print(f"[DDS] {' | '.join(lines)} | msgs={self.message_count}{zero_str}")
                self.last_print = current_time
                self.message_count = 0

        except Exception as e:
            print(f"[DDS] 处理错误: {e}")


def signal_handler(signum, frame):
    global running
    print("\n[信号] 正在停止...")
    running = False


def main():
    global running, tcp_socket

    print("=" * 60)
    print("五指 DDS 触觉数据 → 力值桥接程序")
    print("=" * 60)
    print(f"默认标定: k={CALIBRATION_K:.8f}, b={CALIBRATION_B:.8f}")
    print(f"大拇指标定: k={THUMB_CALIBRATION_K:.8f}, b={THUMB_CALIBRATION_B:.8f}")
    print(f"TCP 目标: {TCP_HOST}:{TCP_PORT}")
    print(f"DDS 话题: {DDS_TOPIC}")
    print("\n手指映射:")
    for field, sid, name in FINGER_MAP:
        cal = "大拇指独立标定" if sid == 1 else "默认标定"
        print(f"  {name} (舵机{sid}) ← DDS.{field}  [{cal}]")
    print("=" * 60)

    if not DDS_AVAILABLE:
        print("[错误] DDS SDK 不可用，程序退出")
        return 1

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

    handler = DDSTouchHandler()

    print(f"[DDS] 订阅话题: {DDS_TOPIC}")
    try:
        subscriber = ChannelSubscriber(DDS_TOPIC, inspire_dds.inspire_hand_touch)
        subscriber.Init(handler.touch_callback, 10)
    except Exception as e:
        print(f"[DDS] 订阅失败: {e}")
        return 1

    print("\n[就绪] 开始接收五指 DDS 触觉数据...")
    print("[提示] 按 Ctrl+C 退出\n")

    try:
        while running:
            time.sleep(0.1)
            with tcp_lock:
                if tcp_socket is None:
                    print("[TCP] 连接断开，尝试重连...")
                    connect_tcp()
    except KeyboardInterrupt:
        pass

    # 清理: 发送所有手指零力
    print("\n[清理] 正在关闭...")
    try:
        if tcp_socket:
            for fs in finger_states:
                send_force_command(fs.servo_id, 0.0)
    except:
        pass

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
