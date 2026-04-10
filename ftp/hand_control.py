#!/usr/bin/env python3
"""
因时灵巧手控制脚本 - 伸直/握拳
通过 DDS 发送控制指令
"""
import sys
import time

sys.path.insert(0, '/home/pi/dexEXO/ftp/inspire_hand_ws/inspire_hand_sdk/inspire_sdkpy')

from unitree_sdk2py.core.channel import ChannelPublisher, ChannelFactoryInitialize
from inspire_dds._inspire_hand_ctrl import inspire_hand_ctrl


class HandController:
    def __init__(self, hand='r'):
        """
        hand: 'r' 右手, 'l' 左手
        """
        ChannelFactoryInitialize(0)
        self.pub = ChannelPublisher(f"rt/inspire_hand/ctrl/{hand}", inspire_hand_ctrl)
        self.pub.Init()
        time.sleep(0.5)
        print(f"灵巧手控制器初始化完成 ({hand})")

    def send_command(self, pos_set, mode=2):
        """
        发送控制指令
        pos_set: 6个关节位置 [小指, 无名指, 中指, 食指, 大拇指弯曲, 大拇指旋转]
                 0 = 伸直, 1000 = 完全握拳
        mode: 控制模式
              1 = 角度控制
              2 = 位置控制
              4 = 力控制
              8 = 速度控制
              可组合，如 3 = 角度+位置
        """
        msg = inspire_hand_ctrl(
            pos_set=pos_set,
            angle_set=[0, 0, 0, 0, 0, 0],
            force_set=[200, 200, 200, 200, 200, 200],
            speed_set=[500, 500, 500, 500, 500, 500],
            mode=mode
        )
        self.pub.Write(msg)

    def open_hand(self):
        """伸直（张开）"""
        print("灵巧手伸直...")
        self.send_command([0, 0, 0, 0, 0, 0])

    def close_hand(self):
        """握拳"""
        print("灵巧手握拳...")
        self.send_command([1000, 1000, 1000, 1000, 1000, 500])

    def set_position(self, pos_list):
        """
        设置指定位置
        pos_list: [小指, 无名指, 中指, 食指, 大拇指弯曲, 大拇指旋转]
        """
        print(f"设置位置: {pos_list}")
        self.send_command(pos_list)


def main():
    print("=== 因时灵巧手控制 ===")
    print("命令: open / close / pos:p1,p2,p3,p4,p5,p6 / exit")
    print("位置范围: 0(伸直) ~ 1000(握拳)")
    print()

    controller = HandController(hand='r')

    while True:
        try:
            cmd = input("Hand> ").strip().lower()

            if cmd == "open":
                controller.open_hand()
            elif cmd == "close":
                controller.close_hand()
            elif cmd.startswith("pos:"):
                try:
                    parts = cmd[4:].split(",")
                    pos = [int(p.strip()) for p in parts]
                    if len(pos) == 6:
                        controller.set_position(pos)
                    else:
                        print("需要 6 个位置值")
                except ValueError:
                    print("无效的位置格式")
            elif cmd == "exit":
                print("退出")
                break
            elif cmd == "help":
                print("open  - 伸直")
                print("close - 握拳")
                print("pos:p1,p2,p3,p4,p5,p6 - 设置位置")
                print("exit  - 退出")
            else:
                print("未知命令，输入 help 查看帮助")

            time.sleep(0.1)

        except KeyboardInterrupt:
            print("\n退出")
            break


if __name__ == "__main__":
    main()
