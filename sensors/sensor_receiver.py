#!/usr/bin/env python3
"""
传感器数据接收器 - Ubuntu端
接收来自树莓派的传感器数据，处理后发送到 Gazebo 仿真环境
"""

import socket
import json
import threading
import time
import sys

# ==================== 配置区域 ====================
LISTEN_PORT = 9999                    # 监听端口（与树莓派端的WIFI_SERVER_PORT一致）
GAZEBO_BRIDGE_IP = "localhost"        # Gazebo bridge 地址
GAZEBO_BRIDGE_PORT = 5555             # Gazebo bridge 端口（需要配置）
ENABLE_GAZEBO = False                 # 是否启用 Gazebo 发送（调试时可关闭）
PRINT_DATA = True                     # 是否打印接收到的数据
DATA_PRINT_INTERVAL = 0.5             # 数据打印间隔(秒)
# ================================================

class SensorReceiver:
    """传感器数据接收器"""
    def __init__(self, port):
        self.port = port
        self.server_socket = None
        self.client_socket = None
        self.running = False
        self.data_count = 0
        self.start_time = time.time()
        self.last_print_time = time.time()
        
        # 数据缓存
        self.latest_data = {"device0": None, "device1": None}
        
    def start(self):
        """启动服务器"""
        self.running = True
        
        # 创建服务器 Socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('0.0.0.0', self.port))
        self.server_socket.listen(1)
        
        print(f"[接收器] 正在监听端口 {self.port}，等待树莓派连接...")
        
        while self.running:
            try:
                # 等待客户端连接
                self.client_socket, client_addr = self.server_socket.accept()
                print(f"[接收器] 已连接到树莓派: {client_addr}")
                
                # 处理数据流
                self._handle_client()
                
            except Exception as e:
                if self.running:
                    print(f"[接收器] 连接错误: {e}")
                    time.sleep(1)
    
    def _handle_client(self):
        """处理客户端连接"""
        buffer = ""
        
        try:
            while self.running:
                # 接收数据
                data = self.client_socket.recv(4096)
                if not data:
                    print("[接收器] 树莓派断开连接")
                    break
                
                # 解码并拼接到缓冲区
                buffer += data.decode('utf-8')
                
                # 处理完整的 JSON 行
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip():
                        self._process_data(line)
                        
        except Exception as e:
            print(f"[接收器] 数据处理错误: {e}")
        finally:
            if self.client_socket:
                self.client_socket.close()
    
    def _process_data(self, json_str):
        """处理接收到的 JSON 数据"""
        try:
            data = json.loads(json_str)
            self.data_count += 1
            
            # 根据设备 ID 存储数据
            device_id = data.get("id", 0)
            device_key = f"device{device_id}"
            self.latest_data[device_key] = data
            
            # 定期打印数据
            current_time = time.time()
            if PRINT_DATA and (current_time - self.last_print_time >= DATA_PRINT_INTERVAL):
                self._print_status(data)
                self.last_print_time = current_time
            
            # 发送到 Gazebo（如果启用）
            if ENABLE_GAZEBO:
                self._send_to_gazebo(data)
                
        except json.JSONDecodeError as e:
            print(f"[接收器] JSON 解析错误: {e}")
        except Exception as e:
            print(f"[接收器] 数据处理异常: {e}")
    
    def _print_status(self, data):
        """打印数据状态"""
        duration = time.time() - self.start_time
        freq = self.data_count / duration if duration > 0 else 0
        
        device_id = data.get("id", "?")
        rel_time = data.get("rel_ts", 0)
        
        # 提取弯曲传感器数据
        bend = data.get("bend", [])
        bend_preview = bend[:5] if len(bend) >= 5 else bend
        
        # 提取陀螺仪数据
        gyro = data.get("gyro", {})
        accel = gyro.get("acc", [0, 0, 0])
        
        print(f"[数据] 设备{device_id} | 相对时间: {rel_time:.3f}s | "
              f"弯曲传感器[0-4]: {bend_preview} | "
              f"加速度: {accel} | "
              f"总接收: {self.data_count} ({freq:.1f} Hz)")
    
    def _send_to_gazebo(self, data):
        """将数据发送到 Gazebo 仿真环境"""
        # TODO: 实现 Gazebo 通信逻辑
        # 这里需要根据您的 Gazebo bridge 接口来实现
        pass
    
    def stop(self):
        """停止服务器"""
        self.running = False
        if self.client_socket:
            self.client_socket.close()
        if self.server_socket:
            self.server_socket.close()
        print("[接收器] 已停止")

def main():
    """主函数"""
    print("=== 传感器数据接收器 ===")
    print(f"监听端口: {LISTEN_PORT}")
    print(f"Gazebo 发送: {'启用' if ENABLE_GAZEBO else '禁用'}")
    print(f"数据打印: {'启用' if PRINT_DATA else '禁用'}")
    print("按 Ctrl+C 停止...\n")
    
    receiver = SensorReceiver(LISTEN_PORT)
    
    try:
        receiver.start()
    except KeyboardInterrupt:
        print("\n接收到停止信号...")
    finally:
        receiver.stop()
        print("程序已退出")

if __name__ == "__main__":
    main()
