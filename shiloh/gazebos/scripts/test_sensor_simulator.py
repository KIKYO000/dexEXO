#!/usr/bin/env python3
"""
模拟传感器数据发送器
用于测试 sensor_to_gazebo_bridge 是否正常工作

功能:
- 模拟18个弯曲传感器的数据
- 通过TCP发送到Ubuntu桥接器
- 模拟左右手弯曲动作
"""

import socket
import json
import time
import numpy as np

# 配置
SERVER_IP = "10.42.0.1"  # Ubuntu IP
SERVER_PORT = 9999
SEND_RATE = 20  # Hz

def create_dummy_sensor_packet(device_id, timestamp):
    """
    创建模拟传感器数据包
    
    Args:
        device_id: 0=左手, 1=右手
        timestamp: 当前时间戳
    
    Returns:
        字典格式的数据包
    """
    # 模拟弯曲传感器数据
    # 使用正弦波模拟手指弯曲动作
    t = timestamp
    freq = 0.5  # 0.5Hz (2秒一个周期)
    
    # 基础值: 500 (伸直) 到 3500 (弯曲)
    base = 2000
    amplitude = 1500
    
    # 18个传感器
    bend_sensors = []
    for i in range(18):
        # 每个传感器有不同的相位，模拟手指依次弯曲
        phase = i * np.pi / 9  # 相位差
        value = int(base + amplitude * np.sin(2 * np.pi * freq * t + phase))
        value = np.clip(value, 500, 3500)
        bend_sensors.append(value)
    
    # 模拟陀螺仪数据 (简单的随机抖动)
    gyro_data = {
        "acc": [
            int(np.random.randn() * 10),
            int(np.random.randn() * 10),
            int(np.random.randn() * 10)
        ],
        "gyr": [
            int(np.random.randn() * 5),
            int(np.random.randn() * 5),
            int(np.random.randn() * 5)
        ],
        "ang": [
            int(np.random.randn() * 2),
            int(np.random.randn() * 2),
            int(np.random.randn() * 2)
        ]
    }
    
    # 构造数据包
    packet = {
        "id": device_id,
        "ts": time.time(),
        "rel_ts": timestamp,
        "gyro": gyro_data,
        "bend": bend_sensors
        # 不发送触觉数据，节省带宽
    }
    
    return packet

def main():
    """主函数"""
    print("========================================")
    print("🧪 传感器数据模拟器")
    print("========================================")
    print(f"目标服务器: {SERVER_IP}:{SERVER_PORT}")
    print(f"发送频率: {SEND_RATE} Hz")
    print("")
    print("正在连接...")
    
    try:
        # 连接服务器
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((SERVER_IP, SERVER_PORT))
        print("✅ 连接成功！")
        print("")
        print("📡 开始发送模拟数据...")
        print("   (Ctrl+C 停止)")
        print("")
        
        start_time = time.time()
        packet_count = 0
        
        while True:
            timestamp = time.time() - start_time
            
            # 交替发送左手和右手数据
            device_id = packet_count % 2
            
            # 创建数据包
            packet = create_dummy_sensor_packet(device_id, timestamp)
            
            # 序列化为JSON
            json_str = json.dumps(packet) + "\n"
            
            # 发送
            try:
                sock.sendall(json_str.encode('utf-8'))
                packet_count += 1
                
                # 每秒打印一次状态
                if packet_count % SEND_RATE == 0:
                    hand = "左手" if device_id == 0 else "右手"
                    print(f"📊 已发送 {packet_count} 包 | "
                          f"当前: {hand} | "
                          f"传感器[0-2]: {packet['bend'][:3]}")
            
            except BrokenPipeError:
                print("❌ 连接断开")
                break
            
            # 控制发送频率
            time.sleep(1.0 / SEND_RATE)
    
    except ConnectionRefusedError:
        print("❌ 连接失败: 目标服务器拒绝连接")
        print("   请确保 sensor_to_gazebo_bridge.py 已启动")
    except KeyboardInterrupt:
        print("\n\n🛑 已停止")
    except Exception as e:
        print(f"❌ 错误: {e}")
    finally:
        if 'sock' in locals():
            sock.close()
        print("连接已关闭")

if __name__ == '__main__':
    main()
