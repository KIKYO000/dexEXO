#!/usr/bin/env python3
"""
大拇指映射控制测试脚本

功能:
- thumb_1: 直接控制,不映射
- thumb_2: 映射输入,自动计算thumb_3和thumb_4
  - 输入: Excel C列 (101.10°~140.18°)
  - 输出: Excel D列 (145.05°~189.25°), E列 (136.12°~170.34°)

使用方法:
1. 测试thumb_1直接控制:
   python3 test_thumb_mapping.py thumb1 right 0.5

2. 测试thumb_2映射:
   python3 test_thumb_mapping.py thumb2 right 120
   # 120°会自动映射到thumb_3和thumb_4

3. 交互模式:
   python3 test_thumb_mapping.py
"""

import sys
import math
from std_msgs.msg import Float64
import rclpy
from rclpy.node import Node


class ThumbTester(Node):
    def __init__(self):
        super().__init__('thumb_tester')
        
        # 创建发布器
        self.pubs = {}
        for hand in ['right', 'left']:
            for joint_num in [1, 2]:
                topic = f'/ftp/{hand}_hand/thumb/joint{joint_num}/cmd'
                self.pubs[f'{hand}_{joint_num}'] = self.create_publisher(
                    Float64, topic, 10
                )
        
        self.get_logger().info('✅ 大拇指测试节点已初始化')
    
    def send_thumb1(self, hand, angle_rad):
        """发送thumb_1角度(直接控制)"""
        key = f'{hand}_1'
        msg = Float64()
        msg.data = angle_rad
        self.pubs[key].publish(msg)
        
        self.get_logger().info(
            f'📤 {hand} thumb_1: {angle_rad:.4f} rad ({math.degrees(angle_rad):.2f}°)'
        )
    
    def send_thumb2(self, hand, angle_deg):
        """发送thumb_2角度(映射输入,Excel C列)"""
        key = f'{hand}_2'
        angle_rad = math.radians(angle_deg)
        
        msg = Float64()
        msg.data = angle_rad
        self.pubs[key].publish(msg)
        
        self.get_logger().info(
            f'📤 {hand} thumb_2: {angle_deg:.2f}° ({angle_rad:.4f} rad)'
        )
        self.get_logger().info(
            f'   -> 将自动映射到 thumb_3 (D列) 和 thumb_4 (E列)'
        )


def print_usage():
    print("""
╔═══════════════════════════════════════════════════════════════╗
║            大拇指映射控制测试脚本                              ║
╠═══════════════════════════════════════════════════════════════╣
║ thumb_1: 直接控制 (0~1.16 rad)                                ║
║ thumb_2: 映射输入 (101.10°~140.18°)                           ║
║   -> 自动计算 thumb_3 (145.05°~189.25°)                       ║
║   -> 自动计算 thumb_4 (136.12°~170.34°)                       ║
╚═══════════════════════════════════════════════════════════════╝

用法:
  1. 测试 thumb_1 直接控制:
     python3 test_thumb_mapping.py thumb1 <hand> <angle_rad>
     示例: python3 test_thumb_mapping.py thumb1 right 0.5
     
  2. 测试 thumb_2 映射:
     python3 test_thumb_mapping.py thumb2 <hand> <angle_deg>
     示例: python3 test_thumb_mapping.py thumb2 right 120
     
  3. 交互模式:
     python3 test_thumb_mapping.py
     
参数:
  <hand>       : right 或 left
  <angle_rad>  : thumb_1角度(弧度)
  <angle_deg>  : thumb_2角度(度数,Excel C列值)
  
推荐测试值:
  thumb_1: 0.0, 0.3, 0.6, 0.9, 1.1
  thumb_2: 105, 115, 120, 130, 138 (°)
""")


def interactive_mode():
    """交互式测试模式"""
    rclpy.init()
    tester = ThumbTester()
    
    print("\n" + "="*60)
    print("交互式大拇指测试模式")
    print("="*60)
    print("命令格式:")
    print("  thumb1 <hand> <rad>   : 控制thumb_1 (例: thumb1 right 0.5)")
    print("  thumb2 <hand> <deg>   : 控制thumb_2 (例: thumb2 right 120)")
    print("  quit / exit / q       : 退出")
    print("="*60 + "\n")
    
    try:
        while True:
            try:
                cmd = input("👉 请输入命令: ").strip()
                
                if cmd.lower() in ['quit', 'exit', 'q']:
                    print("👋 退出测试")
                    break
                
                parts = cmd.split()
                if len(parts) != 3:
                    print("❌ 格式错误! 使用: thumb1/thumb2 <hand> <value>")
                    continue
                
                joint_cmd, hand, value = parts
                
                if hand not in ['right', 'left']:
                    print("❌ hand必须是 right 或 left")
                    continue
                
                if joint_cmd == 'thumb1':
                    angle_rad = float(value)
                    if angle_rad < 0 or angle_rad > 1.2:
                        print("⚠️  thumb_1角度建议范围: 0~1.16 rad")
                    tester.send_thumb1(hand, angle_rad)
                    
                elif joint_cmd == 'thumb2':
                    angle_deg = float(value)
                    if angle_deg < 101 or angle_deg > 141:
                        print("⚠️  thumb_2角度建议范围: 101.10°~140.18°")
                    tester.send_thumb2(hand, angle_deg)
                    
                else:
                    print(f"❌ 未知命令: {joint_cmd}, 使用 thumb1 或 thumb2")
                    
            except ValueError:
                print("❌ 数值格式错误!")
            except KeyboardInterrupt:
                print("\n👋 退出测试")
                break
                
    finally:
        tester.destroy_node()
        rclpy.shutdown()


def main():
    if len(sys.argv) == 1:
        # 无参数,进入交互模式
        interactive_mode()
        return
    
    if sys.argv[1] in ['-h', '--help', 'help']:
        print_usage()
        return
    
    # 命令行模式
    if len(sys.argv) != 4:
        print("❌ 参数错误!")
        print_usage()
        return
    
    joint_cmd = sys.argv[1]
    hand = sys.argv[2]
    value = sys.argv[3]
    
    if hand not in ['right', 'left']:
        print(f"❌ hand必须是 right 或 left, 而不是 '{hand}'")
        return
    
    rclpy.init()
    tester = ThumbTester()
    
    try:
        if joint_cmd == 'thumb1':
            angle_rad = float(value)
            tester.send_thumb1(hand, angle_rad)
            
        elif joint_cmd == 'thumb2':
            angle_deg = float(value)
            tester.send_thumb2(hand, angle_deg)
            
        else:
            print(f"❌ 未知命令: {joint_cmd}")
            print_usage()
            return
        
        # 等待消息发送
        import time
        time.sleep(0.5)
        
    finally:
        tester.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
