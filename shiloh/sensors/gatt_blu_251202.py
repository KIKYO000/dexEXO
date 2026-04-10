#!/usr/bin/env python3
import asyncio
from bleak import BleakClient
import json
import numpy as np
import h5py
import time
import signal
import os
from collections import deque

# ==================== 配置区域 ====================
DEVICE_ADDRESSES = [
    "F0:FD:45:02:85:B3",  # 设备1 MAC地址
    "F0:FD:45:02:67:3B"   # 设备2 MAC地址
]
TX_CHAR_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # 发送数据的特征 UUID
RX_CHAR_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # 接收数据的特征 UUID
HDF5_FILE = "/home/pi/sensor_data.hdf5"    # 数据存储文件
STATS_INTERVAL = 5                         # 状态打印间隔(秒)
BUFFER_SIZE = 500                          # HDF5写入缓冲大小
SYNC_WINDOW = 0.1                          # 时间同步窗口(秒)
PRINT_ALL_DATA = True                      # 是否打印所有数据
DEBUG_RAW_DATA = True                      # 是否打印原始数据用于调试

# === WiFi 传输配置 ===
ENABLE_WIFI = True                         # 是否开启WiFi发送
WIFI_SERVER_IP = "10.42.0.1"               # Ubuntu电脑的IP地址
WIFI_SERVER_PORT = 9999                    # 接收端口
# ================================================

class WifiSender:
    """负责将数据通过TCP发送到上位机"""
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.socket = None
        self.connected = False
        self.connect_retry_time = 0
        # 导入socket库 (如果尚未导入)
        import socket as s
        self.socket_mod = s

    def connect(self):
        """尝试连接服务器"""
        if time.time() - self.connect_retry_time < 3.0: # 限制重连频率
            return

        try:
            if self.socket:
                self.socket.close()
            self.socket = self.socket_mod.socket(self.socket_mod.AF_INET, self.socket_mod.SOCK_STREAM)
            self.socket.settimeout(0.1) # 设置极短的超时，避免阻塞主循环
            self.socket.connect((self.host, self.port))
            self.connected = True
            print(f"[WiFi] 已连接到服务器 {self.host}:{self.port}")
        except Exception as e:
            self.connected = False
            self.connect_retry_time = time.time()
            # print(f"[WiFi] 连接失败: {e}") # 避免刷屏

    def send(self, data_dict):
        """发送字典数据(自动转JSON)"""
        if not ENABLE_WIFI: return

        if not self.connected:
            self.connect()
            if not self.connected: return

        try:
            # 序列化为JSON并添加换行符作为分隔
            json_str = json.dumps(data_dict) + "\n"
            self.socket.sendall(json_str.encode('utf-8'))
        except Exception as e:
            print(f"[WiFi] 发送错误: {e}")
            self.connected = False
            if self.socket: self.socket.close()

    def close(self):
        if self.socket:
            self.socket.close()

class SensorData:
    """JSON格式数据结构"""
    __slots__ = ['gyro', 'bend_sensors', 'tactile', 'timestamp', 'device_id', 'relative_time']

    def __init__(self, device_id):
        self.gyro = {
            "accel": np.empty(3, dtype=np.int16),
            "gyro": np.empty(3, dtype=np.int16),
            "angle": np.empty(3, dtype=np.int16)
        }
        self.bend_sensors = np.empty(18, dtype=np.uint16)
        self.tactile = {
            "group1": {
                "A1": np.empty(32, dtype=np.uint8),
                "B1": np.empty(32, dtype=np.uint8)
            },
            "group2": {
                "A2": np.empty(32, dtype=np.uint8),
                "B2": np.empty(32, dtype=np.uint8)
            },
            "group3": {
                "A3": np.empty(32, dtype=np.uint8),
                "B3": np.empty(32, dtype=np.uint8)
            },
            "group4": {
                "A4": np.empty(32, dtype=np.uint8),
                "B4": np.empty(32, dtype=np.uint8)
            },
            "group5": {
                "A5": np.empty(32, dtype=np.uint8),
                "B5": np.empty(32, dtype=np.uint8)
            }
        }
        self.timestamp = time.time()
        self.device_id = device_id  # 0或1，表示设备索引
        self.relative_time = 0.0    # 相对于设备开始时间的相对时间

    def __str__(self):
        """返回数据的字符串表示"""
        return (f"设备{self.device_id} | "
                f"时间: {self.timestamp:.6f} | "
                f"相对: {self.relative_time:.3f}s | "
                f"加速度: {self.gyro['accel']} | "
                f"陀螺仪: {self.gyro['gyro']} | "
                f"角度: {self.gyro['angle']} | "
                f"弯曲传感器: {self.bend_sensors[:3]}... | "
                f"触觉传感器: {self.tactile['group1']['A1'][:2]}...")

class HDF5Writer:
    """高性能HDF5写入器"""
    def __init__(self, filename, buffer_size=BUFFER_SIZE):
        self.filename = filename
        self.buffer = []
        self.buffer_size = buffer_size
        self.file = None
        self._ensure_file_ready()

    def _ensure_file_ready(self):
        """确保HDF5文件已正确初始化"""
        try:
            # 尝试打开现有文件
            self.file = h5py.File(self.filename, 'a')

            # 检查必要的数据集是否存在
            required_datasets = [
                'gyro/accel', 'gyro/gyro', 'gyro/angle',
                'bend_sensors',
                'tactile/group1/A1', 'tactile/group1/B1',
                'tactile/group2/A2', 'tactile/group2/B2',
                'tactile/group3/A3', 'tactile/group3/B3',
                'tactile/group4/A4', 'tactile/group4/B4',
                'tactile/group5/A5', 'tactile/group5/B5',
                'timestamp', 'device_id', 'relative_time'
            ]

            for ds in required_datasets:
                if ds not in self.file:
                    raise KeyError(f"数据集 {ds} 不存在")

        except (FileNotFoundError, KeyError):
            # 文件不存在或数据集不完整，重新创建
            if self.file:
                self.file.close()

            # 创建新文件并初始化所有数据集
            self.file = h5py.File(self.filename, 'w')
            chunk_size = min(1000, self.buffer_size)

            # 创建陀螺仪组和数据集
            gyro_group = self.file.create_group('gyro')
            gyro_group.create_dataset('accel', (0, 3), maxshape=(None, 3),
                                    dtype=np.int16, chunks=(chunk_size, 3))
            gyro_group.create_dataset('gyro', (0, 3), maxshape=(None, 3),
                                    dtype=np.int16, chunks=(chunk_size, 3))
            gyro_group.create_dataset('angle', (0, 3), maxshape=(None, 3),
                                    dtype=np.int16, chunks=(chunk_size, 3))

            # 创建弯曲传感器数据集
            self.file.create_dataset('bend_sensors', (0, 18), maxshape=(None, 18),
                                   dtype=np.uint16, chunks=(chunk_size, 18))

            # 创建触觉传感器组和数据集
            tactile_group = self.file.create_group('tactile')
            for group_num in range(1, 6):
                group_name = f'group{group_num}'
                group = tactile_group.create_group(group_name)
                group.create_dataset(f'A{group_num}', (0, 32), maxshape=(None, 32),
                                   dtype=np.uint8, chunks=(chunk_size, 32))
                group.create_dataset(f'B{group_num}', (0, 32), maxshape=(None, 32),
                                   dtype=np.uint8, chunks=(chunk_size, 32))

            # 创建时间戳和设备ID数据集
            self.file.create_dataset('timestamp', (0,), maxshape=(None,),
                                  dtype=np.float64, chunks=(chunk_size,))
            self.file.create_dataset('device_id', (0,), maxshape=(None,),
                                  dtype=np.uint8, chunks=(chunk_size,))
            self.file.create_dataset('relative_time', (0,), maxshape=(None,),
                                  dtype=np.float64, chunks=(chunk_size,))

    def add_data(self, data):
        """添加数据到缓冲区"""
        self.buffer.append(data)
        if len(self.buffer) >= self.buffer_size:
            self._flush()

    def _flush(self):
        """将缓冲数据写入文件"""
        if not self.buffer or not self.file:
            return

        try:
            current_size = self.file['gyro/accel'].shape[0]
            new_size = current_size + len(self.buffer)

            # 批量准备数据
            accel_data = np.array([d.gyro['accel'] for d in self.buffer])
            gyro_data = np.array([d.gyro['gyro'] for d in self.buffer])
            angle_data = np.array([d.gyro['angle'] for d in self.buffer])
            bend_sensors_data = np.array([d.bend_sensors for d in self.buffer])

            # 触觉传感器数据
            tactile_data = {}
            for group_num in range(1, 6):
                group_name = f'group{group_num}'
                tactile_data[f'{group_name}/A{group_num}'] = np.array([d.tactile[group_name][f'A{group_num}'] for d in self.buffer])
                tactile_data[f'{group_name}/B{group_num}'] = np.array([d.tactile[group_name][f'B{group_num}'] for d in self.buffer])

            timestamps = np.array([d.timestamp for d in self.buffer], dtype=np.float64)
            device_ids = np.array([d.device_id for d in self.buffer], dtype=np.uint8)
            relative_times = np.array([d.relative_time for d in self.buffer], dtype=np.float64)

            # 扩展并写入数据集
            datasets = [
                ('gyro/accel', accel_data),
                ('gyro/gyro', gyro_data),
                ('gyro/angle', angle_data),
                ('bend_sensors', bend_sensors_data),
                ('timestamp', timestamps),
                ('device_id', device_ids),
                ('relative_time', relative_times)
            ]

            # 添加触觉传感器数据
            for name, data in tactile_data.items():
                datasets.append((f'tactile/{name}', data))

            for name, data in datasets:
                self.file[name].resize((new_size, *data.shape[1:]))
                self.file[name][current_size:new_size] = data

            self.buffer.clear()
        except Exception as e:
            print(f"写入HDF5文件时出错: {e}")
            # 尝试重新初始化文件
            self.file.close()
            self._ensure_file_ready()

    def close(self):
        """关闭文件"""
        if self.file:
            try:
                self._flush()
                self.file.close()
            except:
                pass
            finally:
                self.file = None

class DataProcessor:
    """高性能数据处理流水线，支持双设备时间同步"""
    def __init__(self):
        self.byte_buffers = [bytearray(), bytearray()]  # 每个设备一个缓冲区
        self.writer = HDF5Writer(HDF5_FILE)
        self.start_time = time.time()
        self.packet_count = [0, 0]  # 每个设备的包计数
        self.last_print_time = self.start_time
        self.running = True
        self.last_data_print_time = self.start_time
        self.data_print_interval = 0.1  # 数据打印间隔(秒)

        # 设备开始时间（用于相对时间计算）
        self.device_start_times = [None, None]
        self.device_connect_times = [None, None]  # 设备连接时间戳
        self.device_first_data_times = [None, None]  # 设备第一个数据包时间戳

        # 用于时间同步的数据队列
        self.data_queues = [deque(), deque()]

        # 注册信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # 初始化WiFi发送器
        self.wifi_sender = WifiSender(WIFI_SERVER_IP, WIFI_SERVER_PORT)

    def _signal_handler(self, signum, frame):
        """处理终止信号"""
        print("\n接收到终止信号，正在停止...")
        self.running = False

    def set_device_connect_time(self, device_id, connect_time):
        """设置设备连接时间戳"""
        self.device_connect_times[device_id] = connect_time
        print(f"设备{device_id}连接时间戳: {connect_time:.6f}")

    def process(self, data, device_id):
        """处理原始蓝牙数据"""
        current_time = time.time()

        # 记录设备第一个数据包到达的时间
        if self.device_first_data_times[device_id] is None:
            self.device_first_data_times[device_id] = current_time
            connect_time = self.device_connect_times[device_id] or current_time
            delay = current_time - connect_time
            print(f"设备{device_id}第一个数据包时间戳: {current_time:.6f}")
            print(f"设备{device_id}连接后数据延迟: {delay:.3f}秒")

        # 记录设备开始时间（第一个数据包到达的时间）
        if self.device_start_times[device_id] is None:
            self.device_start_times[device_id] = current_time
            print(f"设备{device_id}开始接收数据，相对时间基准已设置")

        # 打印原始数据用于调试
        if DEBUG_RAW_DATA and len(data) > 0:
            print(f"设备{device_id} 原始数据 ({len(data)} 字节): {data.hex()[:100]}...")  # 显示前50字节的十六进制

        self.byte_buffers[device_id].extend(data)

        # 尝试多种数据格式解析
        parsed_data = self._try_parse_data(device_id)

        # 处理解析后的数据
        if parsed_data:
            self.packet_count[device_id] += len(parsed_data)

            # 打印数据（如果启用）
            if PRINT_ALL_DATA and current_time - self.last_data_print_time >= self.data_print_interval:
                for data_item in parsed_data:
                    print(str(data_item))
                self.last_data_print_time = current_time

            # 将数据添加到同步队列
            for data in parsed_data:
                self.data_queues[device_id].append(data)

            # 尝试时间同步
            self._try_sync_data()

            # 定期打印状态
            if time.time() - self.last_print_time >= STATS_INTERVAL:
                self._print_status()

    def _try_parse_data(self, device_id):
        """尝试多种数据格式解析"""
        parsed_data = []

        # 方法1: 尝试解析JSON格式
        json_data = self._try_parse_json(device_id)
        if json_data:
            for json_obj in json_data:
                try:
                    sensor_data = self._json_to_sensor_data(json_obj, device_id)
                    parsed_data.append(sensor_data)
                    print(f"设备{device_id} JSON数据解析成功")
                except Exception as e:
                    print(f"设备{device_id} JSON数据转换错误: {e}")

        # 如果JSON解析失败，尝试二进制格式解析
        if not parsed_data:
            binary_data = self._try_parse_binary(device_id)
            if binary_data:
                parsed_data.extend(binary_data)

        return parsed_data

    def _try_parse_json(self, device_id):
        """尝试解析JSON格式数据"""
        json_objects = []
        buffer = self.byte_buffers[device_id]

        try:
            # 查找JSON对象开始和结束位置
            start_pos = buffer.find(b'{')
            if start_pos == -1:
                # 没有找到JSON开始标记，清空缓冲区
                self.byte_buffers[device_id].clear()
                return []

            # 查找匹配的结束大括号
            brace_count = 0
            end_pos = -1
            for i in range(start_pos, len(buffer)):
                if buffer[i] == ord(b'{'):
                    brace_count += 1
                elif buffer[i] == ord(b'}'):
                    brace_count -= 1
                    if brace_count == 0:
                        end_pos = i
                        break

            if end_pos == -1:
                return []  # 没有找到完整的JSON对象

            # 提取JSON字符串
            json_bytes = buffer[start_pos:end_pos+1]

            try:
                json_str = json_bytes.decode('utf-8')
                json_obj = json.loads(json_str)
                json_objects.append(json_obj)

                # 从缓冲区移除已处理的数据
                self.byte_buffers[device_id] = buffer[end_pos+1:]

                print(f"设备{device_id} JSON解析成功，数据长度: {len(json_bytes)} 字节")

            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                print(f"设备{device_id} JSON解析失败: {e}")
                print(f"原始数据 (十六进制): {json_bytes.hex()[:100]}...")
                # 移除无效数据
                self.byte_buffers[device_id] = buffer[start_pos+1:]

        except Exception as e:
            print(f"设备{device_id} JSON解析过程错误: {e}")
            # 清空缓冲区以避免无限循环
            self.byte_buffers[device_id].clear()

        return json_objects

    def _try_parse_binary(self, device_id):
        """尝试解析二进制格式数据"""
        # 这里可以添加二进制数据解析逻辑
        # 目前先清空缓冲区，避免数据堆积
        if len(self.byte_buffers[device_id]) > 1000:  # 如果缓冲区太大，清空它
            print(f"设备{device_id} 缓冲区过大 ({len(self.byte_buffers[device_id])} 字节)，清空缓冲区")
            self.byte_buffers[device_id].clear()
        return []

    def _json_to_sensor_data(self, json_data, device_id):
        """将JSON数据转换为SensorData对象"""
        data = SensorData(device_id)

        # 调试：打印接收到的JSON结构
        if DEBUG_RAW_DATA:
            print(f"设备{device_id} 接收到的JSON键: {list(json_data.keys())}")

        # 安全地解析陀螺仪数据
        if 'gyro' in json_data:
            gyro_data = json_data['gyro']
            if isinstance(gyro_data, dict):
                if 'accel' in gyro_data and isinstance(gyro_data['accel'], list) and len(gyro_data['accel']) == 3:
                    data.gyro['accel'][:] = gyro_data['accel']
                if 'gyro' in gyro_data and isinstance(gyro_data['gyro'], list) and len(gyro_data['gyro']) == 3:
                    data.gyro['gyro'][:] = gyro_data['gyro']
                if 'angle' in gyro_data and isinstance(gyro_data['angle'], list) and len(gyro_data['angle']) == 3:
                    data.gyro['angle'][:] = gyro_data['angle']
            else:
                print(f"设备{device_id} 警告: gyro字段不是字典格式: {type(gyro_data)}")
        else:
            print(f"设备{device_id} 警告: 缺少gyro字段")

        # 安全地解析弯曲传感器数据
        if 'bend_sensors' in json_data and isinstance(json_data['bend_sensors'], list) and len(json_data['bend_sensors']) == 18:
            data.bend_sensors[:] = json_data['bend_sensors']
        else:
            print(f"设备{device_id} 警告: bend_sensors格式错误或缺失")

        # 安全地解析触觉传感器数据
        if 'tactile' in json_data and isinstance(json_data['tactile'], dict):
            tactile_data = json_data['tactile']
            for group_num in range(1, 6):
                group_name = f'group{group_num}'
                if group_name in tactile_data and isinstance(tactile_data[group_name], dict):
                    group_data = tactile_data[group_name]
                    a_key = f'A{group_num}'
                    b_key = f'B{group_num}'
                    if a_key in group_data and isinstance(group_data[a_key], list) and len(group_data[a_key]) == 32:
                        data.tactile[group_name][a_key][:] = group_data[a_key]
                    if b_key in group_data and isinstance(group_data[b_key], list) and len(group_data[b_key]) == 32:
                        data.tactile[group_name][b_key][:] = group_data[b_key]

        data.timestamp = time.time()

        # 计算相对时间（从设备开始接收数据算起）
        if self.device_start_times[device_id] is not None:
            data.relative_time = data.timestamp - self.device_start_times[device_id]
            
        # --- WiFi 发送逻辑 ---
        if ENABLE_WIFI:
            try:
                # 构造可序列化的字典
                wifi_payload = {
                    "id": device_id,
                    "ts": data.timestamp,
                    "rel_ts": data.relative_time,
                    "gyro": {
                        "acc": data.gyro['accel'].tolist(),
                        "gyr": data.gyro['gyro'].tolist(),
                        "ang": data.gyro['angle'].tolist()
                    },
                    "bend": data.bend_sensors.tolist(),
                    # 触觉数据量较大，如果WiFi卡顿可考虑注释掉
                    "tactile": {} 
                }
                
                # 填充触觉数据
                for g_name, g_val in data.tactile.items():
                    wifi_payload["tactile"][g_name] = {}
                    for k, v in g_val.items():
                        wifi_payload["tactile"][g_name][k] = v.tolist()
                
                self.wifi_sender.send(wifi_payload)
            except Exception as e:
                print(f"WiFi数据准备错误: {e}")

        return data

    def _try_sync_data(self):
        """尝试同步两个设备的数据（基于相对时间）"""
        # 确保两个队列都有数据且设备开始时间都已设置
        if (not all(self.data_queues) or min(len(q) for q in self.data_queues) == 0 or
            any(t is None for t in self.device_start_times)):
            return

        # 检查时间同步（基于相对时间）
        while all(self.data_queues) and min(len(q) for q in self.data_queues) > 0:
            # 获取两个队列中最早的数据
            data0 = self.data_queues[0][0]
            data1 = self.data_queues[1][0]

            # 检查相对时间差
            time_diff = abs(data0.relative_time - data1.relative_time)

            if time_diff <= SYNC_WINDOW:
                # 时间同步，写入数据
                self.writer.add_data(data0)
                self.writer.add_data(data1)

                # 移除已处理的数据
                self.data_queues[0].popleft()
                self.data_queues[1].popleft()

                # 打印同步信息
                if PRINT_ALL_DATA:
                    print(f"=== 同步数据对 ===")
                    print(f"设备0: {data0}")
                    print(f"设备1: {data1}")
                    print(f"时间差: {time_diff:.3f}s")
                    print("=================")
            elif data0.relative_time < data1.relative_time:
                # 设备0的数据较早，只写入设备0数据
                self.writer.add_data(data0)
                self.data_queues[0].popleft()
            else:
                # 设备1的数据较早，只写入设备1数据
                self.writer.add_data(data1)
                self.data_queues[1].popleft()

    def _print_status(self):
        """打印当前统计信息"""
        now = time.time()
        duration = now - self.start_time
        total_packets = sum(self.packet_count)
        avg_freq = total_packets / duration if duration > 0 else 0

        queue_status = f"{len(self.data_queues[0])}/{len(self.data_queues[1])}"
        start_time_status = f"{self.device_start_times[0] is not None}/{self.device_start_times[1] is not None}"

        # 打印时间戳信息
        time_info = ""
        for i in range(2):
            if self.device_connect_times[i] is not None:
                time_info += f"设备{i}连接: {self.device_connect_times[i]:.3f}s, "
            if self.device_first_data_times[i] is not None:
                time_info += f"首包: {self.device_first_data_times[i]:.3f}s; "

        print(f"[状态] 总包数: {total_packets} (设备0: {self.packet_count[0]}, 设备1: {self.packet_count[1]}) | "
              f"平均频率: {avg_freq:.1f} Hz | "
              f"运行时间: {duration:.1f}s | "
              f"队列长度: {queue_status} | "
              f"设备就绪: {start_time_status}")
        print(f"[时间信息] {time_info}")

        self.last_print_time = now

    def shutdown(self):
        """清理资源"""
        # 处理剩余数据
        for device_id in range(2):
            while self.data_queues[device_id]:
                data = self.data_queues[device_id].popleft()
                self.writer.add_data(data)

        # 打印最终时间统计
        print("\n=== 时间统计 ===")
        for i in range(2):
            if (self.device_connect_times[i] is not None and
                self.device_first_data_times[i] is not None):
                delay = self.device_first_data_times[i] - self.device_connect_times[i]
                print(f"设备{i}: 连接时间 {self.device_connect_times[i]:.6f}, "
                      f"首包时间 {self.device_first_data_times[i]:.6f}, "
                      f"延迟 {delay:.3f}秒")

        self.writer.close()
        if self.wifi_sender:
            self.wifi_sender.close()

class DualBleClient:
    """双BLE客户端管理器"""
    def __init__(self):
        self.processor = DataProcessor()
        self.clients = [None, None]
        self.connected = [False, False]

        # BLE连接参数优化
        self.ble_settings = {
            "address_type": "public",
            "timeout": 30.0,
            "use_cached": False
        }

    async def connect_device(self, device_id):
        """连接单个设备"""
        address = DEVICE_ADDRESSES[device_id]

        try:
            print(f"正在连接设备{device_id} ({address})...")
            connect_start_time = time.time()
            client = BleakClient(address, **self.ble_settings)
            await client.connect()
            connect_end_time = time.time()

            # 记录连接时间戳
            self.processor.set_device_connect_time(device_id, connect_end_time)
            print(f"设备{device_id}连接耗时: {connect_end_time - connect_start_time:.3f}秒")

            # 设置通知处理
            await client.start_notify(RX_CHAR_UUID,
                                     lambda sender, data: self.processor.process(data, device_id))

            self.clients[device_id] = client
            self.connected[device_id] = True
            print(f"设备{device_id}连接成功")
            return True

        except Exception as e:
            print(f"设备{device_id}连接失败: {str(e)}")
            self.connected[device_id] = False
            return False

    async def disconnect_device(self, device_id):
        """断开单个设备"""
        if self.clients[device_id] and self.connected[device_id]:
            try:
                await self.clients[device_id].stop_notify(RX_CHAR_UUID)
                await self.clients[device_id].disconnect()
                print(f"设备{device_id}已断开连接")
            except Exception as e:
                print(f"设备{device_id}断开连接错误: {str(e)}")
            finally:
                self.connected[device_id] = False
                self.clients[device_id] = None

    async def run(self):
        """运行双设备采集"""
        print(f"启动双设备高速数据采集")
        print(f"设备0: {DEVICE_ADDRESSES[0]}")
        print(f"设备1: {DEVICE_ADDRESSES[1]}")
        print(f"TX UUID: {TX_CHAR_UUID}")
        print(f"RX UUID: {RX_CHAR_UUID}")
        print(f"数据格式: JSON (自动检测)")
        print(f"数据打印: {'启用' if PRINT_ALL_DATA else '禁用'}")
        print(f"调试模式: {'启用' if DEBUG_RAW_DATA else '禁用'}")
        print("按Ctrl+C停止采集...")

        # 顺序连接设备（避免BlueZ的并发限制）
        success0 = await self.connect_device(0)
        if not success0:
            print("设备0连接失败，正在退出...")
            await self.shutdown()
            return

        # 等待一段时间再连接第二个设备
        await asyncio.sleep(2.0)

        success1 = await self.connect_device(1)
        if not success1:
            print("设备1连接失败，正在退出...")
            await self.shutdown()
            return

        # 主循环
        try:
            while self.processor.running:
                await asyncio.sleep(0.1)

                # 检查连接状态
                for device_id in range(2):
                    if self.connected[device_id] and not self.clients[device_id].is_connected:
                        print(f"设备{device_id}连接丢失，尝试重连...")
                        self.connected[device_id] = False
                        await asyncio.sleep(1.0)  # 等待一段时间再重连
                        await self.connect_device(device_id)

        except Exception as e:
            print(f"主循环错误: {str(e)}")
        finally:
            await self.shutdown()

    async def shutdown(self):
        """清理资源"""
        print("正在关闭连接...")
        # 顺序断开连接
        await self.disconnect_device(0)
        await asyncio.sleep(1.0)  # 等待一段时间再断开第二个设备
        await self.disconnect_device(1)

        self.processor.shutdown()
        duration = time.time() - self.processor.start_time
        total_packets = sum(self.processor.packet_count)
        print(f"\n采集结束 - 共接收 {total_packets} 个数据包")
        print(f"设备0: {self.processor.packet_count[0]} 包")
        print(f"设备1: {self.processor.packet_count[1]} 包")
        print(f"平均频率: {total_packets/max(duration,0.001):.1f} Hz")
        print(f"数据已保存到: {os.path.abspath(HDF5_FILE)}")

async def main():
    """主函数"""
    # 删除可能损坏的旧文件
    if os.path.exists(HDF5_FILE):
        try:
            os.remove(HDF5_FILE)
            print(f"已删除旧的HDF5文件: {HDF5_FILE}")
        except Exception as e:
            print(f"删除旧文件失败: {e}")

    # 创建并运行双BLE客户端
    dual_client = DualBleClient()
    await dual_client.run()

if __name__ == "__main__":
    asyncio.run(main())