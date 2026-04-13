#!/usr/bin/env python3
"""诊断工具：打印 DDS 触觉消息中所有手指字段的实时最大值，用于确认字段映射"""
import sys
import time

sys.path.insert(0, '/home/pi/dexEXO/ftp/inspire_hand_ws/inspire_hand_sdk/inspire_sdkpy')
from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelFactoryInitialize
from inspire_dds._inspire_hand_touch import inspire_hand_touch

ALL_FIELDS = [
    "fingerone_top_touch",
    "fingertwo_top_touch",
    "fingerthree_top_touch",
    "fingerfour_top_touch",
    "fingerfive_top_touch",
    "fingerone_bottom_touch",
    "fingertwo_bottom_touch",
    "fingerthree_bottom_touch",
    "fingerfour_bottom_touch",
    "fingerfive_bottom_touch",
    # 可能还有 palm 等
    "palm_top_touch",
    "palm_bottom_touch",
    "thumb_top_touch",
    "thumb_bottom_touch",
]

latest_msg = None

def callback(msg):
    global latest_msg
    latest_msg = msg

ChannelFactoryInitialize(0)
sub = ChannelSubscriber("rt/inspire_hand/touch/r", inspire_hand_touch)
sub.Init(callback, 10)

print("等待DDS数据...\n")
time.sleep(1)

print("===== 请依次按压每根手指，观察哪个字段变化 =====\n")
print("提示：用手指按压灵巧手的大拇指触觉传感器，看哪个字段的值变大\n")

try:
    while True:
        if latest_msg:
            parts = []
            for field in ALL_FIELDS:
                data = getattr(latest_msg, field, None)
                if data is not None and len(data) > 0:
                    max_val = max(data)
                    if max_val > 0:
                        parts.append(f"  {field}: max={max_val:.0f}")
                    else:
                        parts.append(f"  {field}: 0")
                else:
                    parts.append(f"  {field}: [无数据]")
            
            print("\033[2J\033[H")  # 清屏
            print("===== DDS 触觉数据实时监控 =====")
            print("按压大拇指传感器，看哪一行的值变化！\n")
            for p in parts:
                # 高亮非零值
                if ": max=" in p:
                    print(f"\033[1;32m{p}\033[0m")  # 绿色高亮
                else:
                    print(p)
            print(f"\n(Ctrl+C 退出)")
        time.sleep(0.2)
except KeyboardInterrupt:
    print("\n退出")
