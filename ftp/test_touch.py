#!/usr/bin/env python3
"""简单订阅触觉数据（无 GUI）"""
import time
import sys
sys.path.insert(0, '/home/pi/dexEXO/ftp/inspire_hand_ws/inspire_hand_sdk/inspire_sdkpy')
from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelFactoryInitialize
from inspire_dds._inspire_hand_touch import inspire_hand_touch

def touch_callback(msg):
    # 打印食指指尖触觉（96个值）
    top = list(msg.fingerfour_top_touch)
    # 取平均值或最大值作为简化指标
    avg = sum(top) / len(top) if top else 0
    max_val = max(top) if top else 0
    print(f"食指指尖: avg={avg:.1f}, max={max_val}, 前10值={top[:10]}")

def main():
    ChannelFactoryInitialize(0)
    sub = ChannelSubscriber("rt/inspire_hand/touch/r", inspire_hand_touch)
    sub.Init(touch_callback, 10)
    
    print("等待触觉数据...")
    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()