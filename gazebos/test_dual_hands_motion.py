#!/usr/bin/env python3
"""
双手灵巧手运动测试脚本

功能:
- 测试双手所有手指的完整运动范围
- 每个手指弯曲/伸直分成3步执行
- 大拇指侧摆(thumb_1)分成3步到极限,3步复原
- 自动化测试序列,无需人工干预

测试内容:
1. 四指(食指/中指/无名指/小指):
   - 3步弯曲: 180° -> 150° -> 120° -> 87°
   - 3步伸直: 87° -> 120° -> 150° -> 180°
   
2. 大拇指侧摆(thumb_1):
   - 3步外展: 0 -> 0.4 -> 0.8 -> 1.16 rad
   - 3步复原: 1.16 -> 0.8 -> 0.4 -> 0 rad
   
3. 大拇指弯曲(thumb_2):
   - 3步弯曲: 101° -> 115° -> 127° -> 140°
   - 3步伸直: 140° -> 127° -> 115° -> 101°

使用方法:
    python3 test_dual_hands_motion.py
    
参数选项:
    --hand <right|left|both>  : 选择测试哪只手 (默认: both)
    --delay <seconds>         : 每步之间的延迟时间 (默认: 2.0)
    --fingers <list>          : 选择测试的手指 (默认: 全部)
                                例: --fingers index,middle,thumb
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64
import time
import math
import argparse
import sys


class DualHandMotionTester(Node):
    def __init__(self):
        super().__init__('dual_hand_motion_tester')
        
        # 创建发布器
        self.joint1_pubs = {}  # 四指joint1
        self.thumb1_pubs = {}  # 大拇指joint1
        self.thumb2_pubs = {}  # 大拇指joint2
        
        # 四指发布器
        for hand in ['right', 'left']:
            for finger in ['index', 'middle', 'ring', 'little']:
                topic = f'/ftp/{hand}_hand/{finger}/joint1/cmd'
                key = f'{hand}_{finger}'
                self.joint1_pubs[key] = self.create_publisher(Float64, topic, 10)
        
        # 大拇指发布器
        for hand in ['right', 'left']:
            topic1 = f'/ftp/{hand}_hand/thumb/joint1/cmd'
            topic2 = f'/ftp/{hand}_hand/thumb/joint2/cmd'
            self.thumb1_pubs[hand] = self.create_publisher(Float64, topic1, 10)
            self.thumb2_pubs[hand] = self.create_publisher(Float64, topic2, 10)
        
        self.get_logger().info('✅ 双手运动测试节点已初始化')
    
    def send_finger_joint1(self, hand, finger, angle_deg):
        """发送四指joint1角度(Excel G列,度数)"""
        key = f'{hand}_{finger}'
        angle_rad = math.radians(angle_deg)
        
        msg = Float64()
        msg.data = angle_rad
        self.joint1_pubs[key].publish(msg)
        
        self.get_logger().info(
            f'  📤 {hand} {finger}: {angle_deg:.1f}° ({angle_rad:.4f} rad)'
        )
    
    def send_thumb1(self, hand, angle_rad):
        """发送大拇指joint1角度(侧摆,弧度)"""
        msg = Float64()
        msg.data = angle_rad
        self.thumb1_pubs[hand].publish(msg)
        
        self.get_logger().info(
            f'  📤 {hand} thumb_1: {angle_rad:.3f} rad ({math.degrees(angle_rad):.1f}°)'
        )
    
    def send_thumb2(self, hand, angle_deg):
        """发送大拇指joint2角度(弯曲,度数)"""
        angle_rad = math.radians(angle_deg)
        
        msg = Float64()
        msg.data = angle_rad
        self.thumb2_pubs[hand].publish(msg)
        
        self.get_logger().info(
            f'  📤 {hand} thumb_2: {angle_deg:.1f}° ({angle_rad:.4f} rad)'
        )


def print_header(text):
    """打印标题"""
    print('\n' + '='*70)
    print(f'  {text}')
    print('='*70)


def test_four_fingers(tester, hands, fingers, delay):
    """测试四指弯曲和伸直"""
    
    # 四指Excel G列范围: 87° (弯曲) ~ 180° (伸直)
    # 3步弯曲序列
    bend_sequence = [
        180.0,  # 初始伸直
        150.0,  # 第1步: 轻微弯曲
        120.0,  # 第2步: 中度弯曲
        87.0    # 第3步: 最大弯曲
    ]
    
    # 3步伸直序列
    straight_sequence = [
        87.0,   # 初始弯曲
        120.0,  # 第1步: 部分伸直
        150.0,  # 第2步: 大部分伸直
        180.0   # 第3步: 完全伸直
    ]
    
    for hand in hands:
        print_header(f'{hand.upper()}手 - 四指运动测试')
        
        for finger in fingers:
            if finger == 'thumb':
                continue
            
            # === 弯曲测试 ===
            tester.get_logger().info(f'\n🔽 {hand} {finger} - 开始弯曲 (3步)')
            for i in range(len(bend_sequence)):
                angle = bend_sequence[i]
                if i == 0:
                    tester.get_logger().info(f'  第0步: 初始位置 {angle:.1f}°')
                else:
                    tester.get_logger().info(f'  第{i}步: 弯曲至 {angle:.1f}°')
                
                tester.send_finger_joint1(hand, finger, angle)
                time.sleep(delay)
            
            # 在弯曲和伸直之间多等待一会
            tester.get_logger().info(f'  ⏸️  保持弯曲状态...')
            time.sleep(delay * 1.5)
            
            # === 伸直测试 ===
            tester.get_logger().info(f'\n🔼 {hand} {finger} - 开始伸直 (3步)')
            for i in range(len(straight_sequence)):
                angle = straight_sequence[i]
                if i == 0:
                    tester.get_logger().info(f'  第0步: 初始位置 {angle:.1f}°')
                else:
                    tester.get_logger().info(f'  第{i}步: 伸直至 {angle:.1f}°')
                
                tester.send_finger_joint1(hand, finger, angle)
                time.sleep(delay)
            
            tester.get_logger().info(f'  ✅ {hand} {finger} 测试完成\n')
            time.sleep(delay * 0.5)


def test_thumb_abduction(tester, hands, delay):
    """测试大拇指侧摆(thumb_1)"""
    
    # thumb_1范围: 0 (贴合) ~ 1.16 rad (最大外展)
    # 3步外展序列
    abduct_sequence = [
        0.0,    # 初始贴合
        0.4,    # 第1步: 轻微外展
        0.8,    # 第2步: 中度外展
        1.16    # 第3步: 最大外展
    ]
    
    # 3步复原序列
    return_sequence = [
        1.16,   # 初始外展
        0.8,    # 第1步: 部分复原
        0.4,    # 第2步: 大部分复原
        0.0     # 第3步: 完全贴合
    ]
    
    for hand in hands:
        print_header(f'{hand.upper()}手 - 大拇指侧摆测试 (thumb_1)')
        
        # === 外展测试 ===
        tester.get_logger().info(f'\n↔️  {hand} thumb - 开始外展 (3步)')
        for i in range(len(abduct_sequence)):
            angle = abduct_sequence[i]
            if i == 0:
                tester.get_logger().info(f'  第0步: 初始位置 {angle:.2f} rad')
            else:
                tester.get_logger().info(f'  第{i}步: 外展至 {angle:.2f} rad')
            
            tester.send_thumb1(hand, angle)
            time.sleep(delay)
        
        tester.get_logger().info(f'  ⏸️  保持外展状态...')
        time.sleep(delay * 1.5)
        
        # === 复原测试 ===
        tester.get_logger().info(f'\n↔️  {hand} thumb - 开始复原 (3步)')
        for i in range(len(return_sequence)):
            angle = return_sequence[i]
            if i == 0:
                tester.get_logger().info(f'  第0步: 初始位置 {angle:.2f} rad')
            else:
                tester.get_logger().info(f'  第{i}步: 复原至 {angle:.2f} rad')
            
            tester.send_thumb1(hand, angle)
            time.sleep(delay)
        
        tester.get_logger().info(f'  ✅ {hand} thumb 侧摆测试完成\n')
        time.sleep(delay * 0.5)


def test_thumb_bend(tester, hands, delay):
    """测试大拇指弯曲(thumb_2)"""
    
    # thumb_2 Excel C列范围: 101° (伸直) ~ 140° (弯曲)
    # 3步弯曲序列
    bend_sequence = [
        101.0,  # 初始伸直
        115.0,  # 第1步: 轻微弯曲
        127.0,  # 第2步: 中度弯曲
        140.0   # 第3步: 最大弯曲
    ]
    
    # 3步伸直序列
    straight_sequence = [
        140.0,  # 初始弯曲
        127.0,  # 第1步: 部分伸直
        115.0,  # 第2步: 大部分伸直
        101.0   # 第3步: 完全伸直
    ]
    
    for hand in hands:
        print_header(f'{hand.upper()}手 - 大拇指弯曲测试 (thumb_2)')
        
        # === 弯曲测试 ===
        tester.get_logger().info(f'\n🔽 {hand} thumb - 开始弯曲 (3步)')
        for i in range(len(bend_sequence)):
            angle = bend_sequence[i]
            if i == 0:
                tester.get_logger().info(f'  第0步: 初始位置 {angle:.1f}°')
            else:
                tester.get_logger().info(f'  第{i}步: 弯曲至 {angle:.1f}°')
            
            tester.send_thumb2(hand, angle)
            time.sleep(delay)
        
        tester.get_logger().info(f'  ⏸️  保持弯曲状态...')
        time.sleep(delay * 1.5)
        
        # === 伸直测试 ===
        tester.get_logger().info(f'\n🔼 {hand} thumb - 开始伸直 (3步)')
        for i in range(len(straight_sequence)):
            angle = straight_sequence[i]
            if i == 0:
                tester.get_logger().info(f'  第0步: 初始位置 {angle:.1f}°')
            else:
                tester.get_logger().info(f'  第{i}步: 伸直至 {angle:.1f}°')
            
            tester.send_thumb2(hand, angle)
            time.sleep(delay)
        
        tester.get_logger().info(f'  ✅ {hand} thumb 弯曲测试完成\n')
        time.sleep(delay * 0.5)


def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description='双手灵巧手运动测试脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
测试序列:
  1. 四指弯曲/伸直测试 (每个手指3步)
  2. 大拇指侧摆测试 (3步外展 + 3步复原)
  3. 大拇指弯曲测试 (3步弯曲 + 3步伸直)

示例:
  # 测试双手所有手指
  python3 test_dual_hands_motion.py
  
  # 只测试右手
  python3 test_dual_hands_motion.py --hand right
  
  # 只测试食指和大拇指
  python3 test_dual_hands_motion.py --fingers index,thumb
  
  # 加快测试速度 (每步1秒)
  python3 test_dual_hands_motion.py --delay 1.0
        """
    )
    
    parser.add_argument(
        '--hand',
        choices=['right', 'left', 'both'],
        default='both',
        help='选择测试哪只手 (默认: both)'
    )
    
    parser.add_argument(
        '--delay',
        type=float,
        default=2.0,
        help='每步之间的延迟时间(秒) (默认: 2.0)'
    )
    
    parser.add_argument(
        '--fingers',
        type=str,
        default='all',
        help='选择测试的手指,逗号分隔 (默认: all)\n'
             '可选: index, middle, ring, little, thumb'
    )
    
    args = parser.parse_args()
    
    # 确定测试哪些手
    if args.hand == 'both':
        hands = ['right', 'left']
    else:
        hands = [args.hand]
    
    # 确定测试哪些手指
    if args.fingers == 'all':
        fingers = ['index', 'middle', 'ring', 'little', 'thumb']
    else:
        fingers = [f.strip() for f in args.fingers.split(',')]
        # 验证手指名称
        valid_fingers = ['index', 'middle', 'ring', 'little', 'thumb']
        for f in fingers:
            if f not in valid_fingers:
                print(f'❌ 错误: 无效的手指名称 "{f}"')
                print(f'   有效选项: {", ".join(valid_fingers)}')
                return
    
    # 初始化ROS 2
    rclpy.init()
    tester = DualHandMotionTester()
    
    # 打印测试配置
    print('\n' + '='*70)
    print('  双手灵巧手运动测试')
    print('='*70)
    print(f'测试手: {", ".join([h.upper() for h in hands])}')
    print(f'测试手指: {", ".join(fingers)}')
    print(f'延迟时间: {args.delay} 秒/步')
    print('='*70)
    
    # 等待发布器建立连接
    tester.get_logger().info('⏳ 等待ROS话题连接...')
    time.sleep(1.0)
    
    try:
        # === 测试序列 ===
        
        # 1. 四指测试 (如果选择了)
        four_fingers = [f for f in fingers if f != 'thumb']
        if four_fingers:
            test_four_fingers(tester, hands, four_fingers, args.delay)
        
        # 2. 大拇指测试 (如果选择了)
        if 'thumb' in fingers:
            test_thumb_abduction(tester, hands, args.delay)
            test_thumb_bend(tester, hands, args.delay)
        
        # === 测试完成 ===
        print_header('✅ 所有测试完成!')
        print('\n测试摘要:')
        print(f'  - 测试手数: {len(hands)}')
        print(f'  - 测试手指: {len(fingers)}')
        print(f'  - 总步数: {len(fingers) * len(hands) * 6}')  # 每个手指6步(弯曲3步+伸直3步)
        print(f'  - 总耗时: 约 {len(fingers) * len(hands) * 6 * args.delay / 60:.1f} 分钟')
        print('\n📊 查看详细日志:')
        print('    tail -f /tmp/joint12_controller.log')
        print()
        
    except KeyboardInterrupt:
        tester.get_logger().info('\n⚠️  测试被用户中断')
    except Exception as e:
        tester.get_logger().error(f'\n❌ 测试出错: {e}')
        import traceback
        traceback.print_exc()
    finally:
        tester.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
