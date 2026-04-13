#!/usr/bin/env python3
"""
触觉传感器标定工具
使用最大值与砝码重量进行标定
"""
import time
import sys
import json
from datetime import datetime

sys.path.insert(0, '/home/pi/dexEXO/ftp/inspire_hand_ws/inspire_hand_sdk/inspire_sdkpy')

from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelFactoryInitialize
from inspire_dds._inspire_hand_touch import inspire_hand_touch


class TouchCalibrator:
    # DDS字段名 → 手指名
    FINGER_FIELDS = {
        1: ("fingerfive_top_touch",  "大拇指"),
        2: ("fingerfour_top_touch",  "食指"),
        3: ("fingerthree_top_touch", "中指"),
        4: ("fingertwo_top_touch",   "无名指"),
        5: ("fingerone_top_touch",   "小指"),
    }

    def __init__(self, finger_id=2):
        self.latest_touch = None
        self.calibration_points = []  # [(max_value, force_N), ...]
        self.finger_id = finger_id
        field, name = self.FINGER_FIELDS[finger_id]
        self.field_name = field
        self.finger_name = name
        print(f"[标定目标] 手指{finger_id} - {name} (DDS字段: {field})")
        
    def touch_callback(self, msg):
        """触觉数据回调"""
        top = list(getattr(msg, self.field_name, []))
        self.latest_touch = {
            'raw': top,
            'max': max(top) if top else 0,
            'avg': sum(top) / len(top) if top else 0
        }
    
    def get_stable_max(self, samples=50, interval=0.02):
        """采集多次最大值取平均，减少噪声"""
        readings = []
        for _ in range(samples):
            if self.latest_touch:
                readings.append(self.latest_touch['max'])
            time.sleep(interval)
        
        if readings:
            return sum(readings) / len(readings)
        return 0
    
    def show_realtime(self):
        """显示实时最大值"""
        if self.latest_touch:
            print(f"\r当前最大值: {self.latest_touch['max']:6.1f}", end='', flush=True)
    
    def add_calibration_point(self, weight_g):
        """添加标定点 - 支持多次采样求平均"""
        force_n = weight_g * 0.00981  # 克转牛顿
        
        print(f"\n砝码: {weight_g}g = {force_n:.4f}N")
        print("命令: 's' 采样一次 | 'd' 完成并记录 | 'c' 取消 | Ctrl+C 退出程序")
        
        samples = []  # 存储多次采样的最大值
        
        import select
        try:
            while True:
                self.show_realtime()
                
                # 非阻塞检查输入
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    cmd = sys.stdin.readline().strip().lower()
                    
                    if cmd == 's':
                        # 采样一次
                        print("\n采集中...")
                        max_val = self.get_stable_max(samples=50)
                        samples.append(max_val)
                        print(f"第 {len(samples)} 次采样: {max_val:.2f}")
                        print(f"当前平均: {sum(samples)/len(samples):.2f}")
                        print("继续: 's' 再采样 | 'd' 完成 | 'c' 取消")
                    
                    elif cmd == 'd':
                        if not samples:
                            print("还没有采样数据，请先按 's' 采样")
                            continue
                        # 计算平均值并记录
                        avg_max = sum(samples) / len(samples)
                        self.calibration_points.append((avg_max, force_n))
                        print(f"\n已记录: 采样{len(samples)}次, 平均最大值={avg_max:.2f}, 力={force_n:.4f}N")
                        print(f"当前标定点数: {len(self.calibration_points)}")
                        break
                    
                    elif cmd == 'c':
                        print("已取消")
                        break
        except KeyboardInterrupt:
            print("\n程序退出")
            sys.exit(0)
    
    def calculate_calibration(self):
        """线性回归计算标定参数"""
        if len(self.calibration_points) < 2:
            print("错误: 需要至少2个标定点！")
            return None, None
        
        # y = k * x + b
        # force = k * max_value + b
        n = len(self.calibration_points)
        sum_x = sum(p[0] for p in self.calibration_points)
        sum_y = sum(p[1] for p in self.calibration_points)
        sum_xy = sum(p[0] * p[1] for p in self.calibration_points)
        sum_x2 = sum(p[0] ** 2 for p in self.calibration_points)
        
        denominator = n * sum_x2 - sum_x ** 2
        if abs(denominator) < 1e-10:
            print("错误: 标定点数据异常，无法计算")
            return None, None
        
        k = (n * sum_xy - sum_x * sum_y) / denominator
        b = (sum_y - k * sum_x) / n
        
        return k, b
    
    def save_calibration(self, k, b, filename='touch_calibration.json'):
        """保存标定参数"""
        data = {
            'timestamp': datetime.now().isoformat(),
            'k': k,
            'b': b,
            'points': self.calibration_points,
            'formula': f"F(N) = {k:.8f} * max_value + ({b:.8f})"
        }
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"标定参数已保存: {filename}")
        return data
    
    def verify_calibration(self, k, b):
        """验证标定结果"""
        print("\n=== 实时验证 (输入 'q' 退出) ===")
        
        import select
        while True:
            if self.latest_touch:
                max_val = self.latest_touch['max']
                force_n = k * max_val + b
                force_n = max(0, force_n)  # 力不能为负
                force_g = force_n / 0.00981  # 转换为等效克数
                
                print(f"\r最大值: {max_val:6.1f} | 力: {force_n:.4f}N | 约 {force_g:.1f}g", end='', flush=True)
            
            if select.select([sys.stdin], [], [], 0.05)[0]:
                cmd = sys.stdin.readline().strip().lower()
                if cmd == 'q':
                    print()
                    break
            
            time.sleep(0.05)


def main():
    # 命令行参数: python touch_calibration.py [手指ID]
    # 手指ID: 1=大拇指, 2=食指, 3=中指, 4=无名指, 5=小指
    finger_id = 2  # 默认食指
    if len(sys.argv) > 1:
        try:
            finger_id = int(sys.argv[1])
            if finger_id not in range(1, 6):
                print("错误: 手指ID必须是 1-5")
                print("  1=大拇指, 2=食指, 3=中指, 4=无名指, 5=小指")
                return
        except ValueError:
            print("用法: python touch_calibration.py [手指ID]")
            print("  1=大拇指, 2=食指, 3=中指, 4=无名指, 5=小指")
            return

    ChannelFactoryInitialize(0)
    
    calibrator = TouchCalibrator(finger_id)
    sub = ChannelSubscriber("rt/inspire_hand/touch/r", inspire_hand_touch)
    sub.Init(calibrator.touch_callback, 10)
    
    print("=" * 50)
    print(f"    触觉传感器标定工具 — {calibrator.finger_name}")
    print("=" * 50)
    print("\n命令说明:")
    print("  <数字>    - 输入砝码克数，准备标定")
    print("  calc      - 计算标定参数")
    print("  list      - 查看已记录的标定点")
    print("  clear     - 清空标定点")
    print("  exit      - 退出")
    print()
    
    time.sleep(0.5)  # 等待数据连接
    
    k, b = None, None
    
    while True:
        try:
            # 显示实时值
            if calibrator.latest_touch:
                print(f"\n当前最大值: {calibrator.latest_touch['max']:.1f}")
            
            cmd = input("\nCalib> ").strip().lower()
            
            if cmd == 'exit':
                print("退出")
                break
            
            elif cmd == 'calc':
                k, b = calibrator.calculate_calibration()
                if k is not None:
                    print("\n" + "=" * 40)
                    print("标定结果:")
                    print(f"  k = {k:.8f}")
                    print(f"  b = {b:.8f}")
                    print(f"  公式: F(N) = {k:.8f} * max + ({b:.8f})")
                    print("=" * 40)
                    
                    # 显示各标定点误差
                    print("\n标定点验证:")
                    for i, (raw, actual) in enumerate(calibrator.calibration_points):
                        predicted = k * raw + b
                        error = abs(predicted - actual)
                        print(f"  点{i+1}: raw={raw:.1f}, 实际={actual:.4f}N, 预测={predicted:.4f}N, 误差={error:.4f}N")
                    
                    # 保存
                    save = input("\n保存标定结果? (y/n): ").strip().lower()
                    if save == 'y':
                        calibrator.save_calibration(k, b)
                        
                        verify = input("进入实时验证? (y/n): ").strip().lower()
                        if verify == 'y':
                            calibrator.verify_calibration(k, b)
            
            elif cmd == 'list':
                if not calibrator.calibration_points:
                    print("暂无标定点")
                else:
                    print("\n已记录的标定点:")
                    for i, (raw, force) in enumerate(calibrator.calibration_points):
                        print(f"  {i+1}. 最大值={raw:.2f}, 力={force:.4f}N ({force/0.00981:.1f}g)")
            
            elif cmd == 'clear':
                calibrator.calibration_points.clear()
                print("已清空所有标定点")
            
            elif cmd.replace('.', '').isdigit():
                # 输入的是数字，作为砝码克数
                weight_g = float(cmd)
                calibrator.add_calibration_point(weight_g)
            
            else:
                print("未知命令。输入砝码克数(如: 50)、calc、list、clear 或 exit")
        
        except KeyboardInterrupt:
            print("\n退出")
            break
        except Exception as e:
            print(f"错误: {e}")


if __name__ == "__main__":
    main()
