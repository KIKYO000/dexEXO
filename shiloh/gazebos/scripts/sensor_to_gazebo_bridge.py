#!/usr/bin/env python3
"""
传感器数据到Gazebo仿真桥接器

功能流程:
1. 通过TCP接收来自树莓派的传感器数据(弯曲传感器、陀螺仪等)
2. 解析弯曲传感器数据并映射到手指关节角度
3. 发布到ROS2话题，由joint12_mapping_controller控制仿真手

数据映射:
- 18个弯曲传感器 -> 双手手指关节角度
- 左手传感器索引: 0-8 (9个传感器)
- 右手传感器索引: 9-17 (9个传感器)

传感器分配:
左手:
  - 拇指: sensors[0] -> thumb_2 (映射输入)
  - 食指: sensors[1] -> index_1
  - 中指: sensors[2] -> middle_1
  - 无名指: sensors[3] -> ring_1
  - 小指: sensors[4] -> little_1
  
右手:
  - 拇指: sensors[9] -> thumb_2 (映射输入)
  - 食指: sensors[10] -> index_1
  - 中指: sensors[11] -> middle_1
  - 无名指: sensors[12] -> ring_1
  - 小指: sensors[13] -> little_1
"""

import socket
import json
import threading
import numpy as np
import time
import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64


class SensorToGazeboBridge(Node):
    def __init__(self):
        super().__init__('sensor_to_gazebo_bridge')
        
        # TCP 服务器配置
        self.tcp_host = '0.0.0.0'  # 监听所有网络接口
        self.tcp_port = 9999
        self.server_socket = None
        
        # ROS2 发布者字典
        self.publishers = {}
        
        # 创建发布者
        self._create_publishers()
        
        # 弯曲传感器数据缓存
        self.latest_bend_data = {
            'left': [0] * 9,
            'right': [0] * 9
        }
        
        # 传感器校准参数 (根据实际测量调整)
        # 假设弯曲传感器输出范围: 0-4095 (12位ADC)
        # 映射到手指关节角度: 1.52-3.14 rad (伸直到弯曲)
        self.sensor_min = 500    # 传感器伸直时的读数
        self.sensor_max = 3500   # 传感器完全弯曲时的读数
        self.joint_min = 1.52    # 关节伸直角度 (rad)
        self.joint_max = 3.14    # 关节弯曲角度 (rad)
        
        # 大拇指特殊映射 (thumb_2输入范围)
        self.thumb_joint_min = np.radians(101.10)  # 1.765 rad
        self.thumb_joint_max = np.radians(140.18)  # 2.446 rad
        
        # 统计信息
        self.packet_count = 0
        self.last_print_time = time.time()
        
        # 启动 TCP 服务器线程
        self.running = True
        self.tcp_thread = threading.Thread(target=self._tcp_server_thread, daemon=True)
        self.tcp_thread.start()
        
        # 创建定时器，定期发布数据到Gazebo (20Hz)
        self.timer = self.create_timer(0.05, self._publish_to_gazebo)
        
        self.get_logger().info('✅ 传感器到Gazebo桥接器已启动')
        self.get_logger().info(f'📡 TCP 服务器监听: {self.tcp_host}:{self.tcp_port}')
        self.get_logger().info('等待树莓派连接...')
    
    def _create_publishers(self):
        """创建所有ROS2发布者"""
        fingers = ['index', 'middle', 'ring', 'little']
        hands = ['left', 'right']
        
        # 四指关节1发布者
        for hand in hands:
            for finger in fingers:
                topic = f'/ftp/{hand}_hand/{finger}/joint1/cmd'
                self.publishers[f'{hand}_{finger}_1'] = self.create_publisher(
                    Float64, topic, 10
                )
                self.get_logger().info(f'📤 创建发布者: {topic}')
            
            # 大拇指关节2发布者 (映射输入)
            thumb_topic = f'/ftp/{hand}_hand/thumb/joint2/cmd'
            self.publishers[f'{hand}_thumb_2'] = self.create_publisher(
                Float64, thumb_topic, 10
            )
            self.get_logger().info(f'📤 创建发布者: {thumb_topic}')
    
    def _tcp_server_thread(self):
        """TCP服务器线程"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.tcp_host, self.tcp_port))
            self.server_socket.listen(1)
            
            self.get_logger().info(f'🌐 TCP 服务器已启动，等待连接...')
            
            while self.running:
                try:
                    conn, addr = self.server_socket.accept()
                    self.get_logger().info(f'✅ 树莓派已连接: {addr}')
                    
                    # 处理客户端数据
                    buffer = b''
                    while self.running:
                        try:
                            data = conn.recv(4096)
                            if not data:
                                self.get_logger().warn('树莓派断开连接')
                                break
                            
                            buffer += data
                            
                            # 处理粘包：按换行符分割
                            while b'\n' in buffer:
                                line, buffer = buffer.split(b'\n', 1)
                                if line.strip():
                                    self._process_sensor_data(line)
                        
                        except socket.timeout:
                            continue
                        except Exception as e:
                            self.get_logger().error(f'接收数据错误: {e}')
                            break
                    
                    conn.close()
                    self.get_logger().info('连接已关闭，等待重连...')
                
                except Exception as e:
                    self.get_logger().error(f'服务器错误: {e}')
                    time.sleep(1)
        
        except Exception as e:
            self.get_logger().error(f'TCP服务器启动失败: {e}')
        finally:
            if self.server_socket:
                self.server_socket.close()
    
    def _process_sensor_data(self, json_bytes):
        """处理接收到的传感器JSON数据"""
        try:
            # 解析JSON
            data = json.loads(json_bytes.decode('utf-8'))
            
            # 提取弯曲传感器数据
            if 'bend' in data and isinstance(data['bend'], list) and len(data['bend']) == 18:
                bend_sensors = data['bend']
                device_id = data.get('id', 0)  # 0=左手, 1=右手
                
                # 根据设备ID更新对应手的数据
                if device_id == 0:  # 左手设备
                    self.latest_bend_data['left'] = bend_sensors[:9]
                elif device_id == 1:  # 右手设备
                    self.latest_bend_data['right'] = bend_sensors[9:18]
                
                self.packet_count += 1
                
                # 定期打印统计
                if time.time() - self.last_print_time > 2.0:
                    self.get_logger().info(
                        f'📊 接收数据包: {self.packet_count} | '
                        f'左手传感器[0-2]: {self.latest_bend_data["left"][:3]} | '
                        f'右手传感器[9-11]: {self.latest_bend_data["right"][:3]}'
                    )
                    self.last_print_time = time.time()
        
        except json.JSONDecodeError as e:
            self.get_logger().error(f'JSON解析错误: {e}')
        except Exception as e:
            self.get_logger().error(f'数据处理错误: {e}')
    
    def _sensor_to_joint_angle(self, sensor_value, is_thumb=False):
        """
        将传感器值映射到关节角度
        
        Args:
            sensor_value: 传感器原始值 (0-4095)
            is_thumb: 是否为大拇指
        
        Returns:
            关节角度 (弧度)
        """
        # 限制范围
        sensor_value = np.clip(sensor_value, self.sensor_min, self.sensor_max)
        
        # 归一化到 0-1
        normalized = (sensor_value - self.sensor_min) / (self.sensor_max - self.sensor_min)
        
        # 映射到关节角度范围
        if is_thumb:
            angle = self.thumb_joint_min + normalized * (self.thumb_joint_max - self.thumb_joint_min)
        else:
            angle = self.joint_min + normalized * (self.joint_max - self.joint_min)
        
        return float(angle)
    
    def _publish_to_gazebo(self):
        """定时发布数据到Gazebo (20Hz)"""
        try:
            # 发布左手
            self._publish_hand_data('left', self.latest_bend_data['left'])
            
            # 发布右手
            self._publish_hand_data('right', self.latest_bend_data['right'])
        
        except Exception as e:
            self.get_logger().error(f'发布数据错误: {e}')
    
    def _publish_hand_data(self, hand, sensor_data):
        """
        发布单手的传感器数据到ROS2话题
        
        Args:
            hand: 'left' 或 'right'
            sensor_data: 9个传感器的数据列表
        """
        # 传感器索引映射到手指
        finger_map = {
            0: 'thumb',   # 拇指 (特殊处理)
            1: 'index',   # 食指
            2: 'middle',  # 中指
            3: 'ring',    # 无名指
            4: 'little'   # 小指
        }
        
        for idx, finger in finger_map.items():
            if idx >= len(sensor_data):
                continue
            
            sensor_value = sensor_data[idx]
            
            if finger == 'thumb':
                # 大拇指发布到 thumb_2 (映射输入)
                angle = self._sensor_to_joint_angle(sensor_value, is_thumb=True)
                msg = Float64()
                msg.data = angle
                pub_key = f'{hand}_thumb_2'
                if pub_key in self.publishers:
                    self.publishers[pub_key].publish(msg)
            else:
                # 其他手指发布到 joint1
                angle = self._sensor_to_joint_angle(sensor_value, is_thumb=False)
                msg = Float64()
                msg.data = angle
                pub_key = f'{hand}_{finger}_1'
                if pub_key in self.publishers:
                    self.publishers[pub_key].publish(msg)
    
    def shutdown(self):
        """关闭节点"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        self.get_logger().info('桥接器已关闭')


def main(args=None):
    rclpy.init(args=args)
    
    bridge = SensorToGazeboBridge()
    
    try:
        rclpy.spin(bridge)
    except KeyboardInterrupt:
        pass
    finally:
        bridge.shutdown()
        bridge.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
