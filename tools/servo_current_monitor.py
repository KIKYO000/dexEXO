#!/usr/bin/env python3
"""
简单的舵机电流/报警实时监测脚本
在树莓派上运行，用于排查红灯闪烁是否由过流/电源造成。
"""
import time
from dynamixel_sdk import PortHandler, PacketHandler

DEVICENAME = "/dev/ttyAMA0"
BAUDRATE = 1000000
PROTOCOL_VERSION = 2.0
DXL_IDS = [1, 2, 3, 4, 5]
ADDR_PRESENT_CURRENT = 126
ADDR_HARDWARE_ERROR = 70
COMM_SUCCESS = 0


def to_signed16(val):
    """无符号16位 → 有符号16位"""
    return val - 65536 if val > 32767 else val


def main():
    portHandler = PortHandler(DEVICENAME)
    packetHandler = PacketHandler(PROTOCOL_VERSION)

    if not portHandler.openPort():
        print(f"无法打开串口 {DEVICENAME}")
        return
    if not portHandler.setBaudRate(BAUDRATE):
        print(f"无法设置波特率 {BAUDRATE}")
        return

    print(f"串口打开: {DEVICENAME} @ {BAUDRATE}")
    print("按 Ctrl+C 退出\n")

    # 先读一次硬件错误状态
    print("=== 硬件错误检查 ===")
    for sid in DXL_IDS:
        hw_err, res, err = packetHandler.read1ByteTxRx(portHandler, sid, ADDR_HARDWARE_ERROR)
        if res != COMM_SUCCESS:
            print(f"  ID{sid}: 通信失败 ({packetHandler.getTxRxResult(res)})")
        elif hw_err != 0:
            flags = []
            if hw_err & 0x01: flags.append("输入电压异常")
            if hw_err & 0x04: flags.append("过热")
            if hw_err & 0x08: flags.append("电机编码器")
            if hw_err & 0x10: flags.append("电气冲击")
            if hw_err & 0x20: flags.append("过载")
            print(f"  ID{sid}: ⚠️ 硬件错误=0x{hw_err:02X} → {', '.join(flags)}")
        else:
            print(f"  ID{sid}: ✅ 正常")
    print()

    try:
        while True:
            t0 = time.time()
            parts = []
            for sid in DXL_IDS:
                val, res, err = packetHandler.read2ByteTxRx(portHandler, sid, ADDR_PRESENT_CURRENT)
                if res != COMM_SUCCESS:
                    parts.append(f"ID{sid}:ERR")
                else:
                    cur_ma = to_signed16(val)
                    parts.append(f"ID{sid}:{cur_ma:+4d}mA")
            elapsed = time.time() - t0
            print(f"{time.strftime('%H:%M:%S')} ({elapsed*1000:.1f}ms) {' | '.join(parts)}")
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n中断，退出")
    finally:
        portHandler.closePort()


if __name__ == '__main__':
    main()
