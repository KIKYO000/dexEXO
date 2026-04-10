# 传感器控制灵巧手系统使用指南

## 系统架构

```
[树莓派] 蓝牙传感器采集
    ↓ (gatt_blu_251202.py)
    ↓ WiFi TCP (端口9999)
    ↓
[Ubuntu] 传感器数据桥接器
    ↓ (sensor_to_gazebo_bridge.py)
    ↓ ROS2 话题
    ↓
[Ubuntu] 关节映射控制器
    ↓ (joint12_mapping_controller.py)
    ↓ Gazebo 仿真接口
    ↓
[Gazebo] 灵巧手仿真
```

## 快速开始

### 1. 树莓派端 (传感器采集)

```bash
# 在树莓派上运行
cd cd /home/pi/dexEXO  # 或您的实际路径
python3 gatt_blu_251202.py
```

**配置说明 (gatt_blu_251202.py):**
- `DEVICE_ADDRESSES`: 两个蓝牙传感器设备的MAC地址
  - 设备0 (左手): `F0:FD:45:02:85:B3`
  - 设备1 (右手): `F0:FD:45:02:67:3B`
- `WIFI_SERVER_IP`: Ubuntu电脑的IP地址 (默认 `10.42.0.1`)
- `WIFI_SERVER_PORT`: 数据发送端口 (默认 `9999`)
- `ENABLE_WIFI`: 是否开启WiFi发送 (默认 `True`)

**数据格式 (通过WiFi发送的JSON):**
```json
{
  "id": 0,                    // 设备ID: 0=左手, 1=右手
  "ts": 1234567890.123456,    // 绝对时间戳
  "rel_ts": 12.345,           // 相对时间戳(秒)
  "gyro": {
    "acc": [x, y, z],         // 加速度
    "gyr": [x, y, z],         // 角速度
    "ang": [x, y, z]          // 角度
  },
  "bend": [s0, s1, ..., s17], // 18个弯曲传感器
  "tactile": {...}            // 触觉传感器数据
}
```

### 2. Ubuntu端 (一键启动)

```bash
cd /home/wxc/projects/dexEXO/gazebos
./start_sensor_hand_control.sh
```

这个脚本会自动启动：
1. Gazebo 仿真环境 (如果未运行)
2. 关节映射控制器 (`joint12_mapping_controller.py`)
3. 传感器桥接器 (`sensor_to_gazebo_bridge.py`)

### 3. 手动启动 (调试用)

如果需要分步调试，可以手动启动各组件：

**步骤1: 启动 Gazebo**
```bash
cd /home/wxc/projects/dexEXO/gazebos
./launch_hands_correct.sh
```

**步骤2: 启动关节映射控制器**
```bash
cd /home/wxc/projects/dexEXO/gazebos
source /opt/ros/humble/setup.bash
export GZ_VERSION=harmonic
python3 scripts/joint12_mapping_controller.py
```

**步骤3: 启动传感器桥接器**
```bash
cd /home/wxc/projects/dexEXO/gazebos
source /opt/ros/humble/setup.bash
export GZ_VERSION=harmonic
python3 scripts/sensor_to_gazebo_bridge.py
```

## 传感器映射关系

### 弯曲传感器索引 (18个传感器)

**左手 (设备0, 索引0-8):**
- `sensors[0]` → 左手拇指 (`left_thumb_2`)
- `sensors[1]` → 左手食指 (`left_index_1`)
- `sensors[2]` → 左手中指 (`left_middle_1`)
- `sensors[3]` → 左手无名指 (`left_ring_1`)
- `sensors[4]` → 左手小指 (`left_little_1`)
- `sensors[5-8]` → (备用/未使用)

**右手 (设备1, 索引9-17):**
- `sensors[9]` → 右手拇指 (`right_thumb_2`)
- `sensors[10]` → 右手食指 (`right_index_1`)
- `sensors[11]` → 右手中指 (`right_middle_1`)
- `sensors[12]` → 右手无名指 (`right_ring_1`)
- `sensors[13]` → 右手小指 (`right_little_1`)
- `sensors[14-17]` → (备用/未使用)

### 传感器值到关节角度映射

**四指 (食指/中指/无名指/小指):**
- 传感器范围: `500 - 3500` (ADC值)
- 关节角度范围: `1.52 - 3.14 rad` (87° - 180°)
- 映射公式: `angle = 1.52 + (sensor - 500) / 3000 * (3.14 - 1.52)`

**拇指 (特殊映射):**
- 传感器范围: `500 - 3500` (ADC值)
- 关节角度范围: `1.765 - 2.446 rad` (101° - 140°)
- 映射公式: `angle = 1.765 + (sensor - 500) / 3000 * (2.446 - 1.765)`

## ROS2 话题接口

### 发布话题 (sensor_to_gazebo_bridge → joint12_mapping_controller)

**四指关节1命令:**
- `/ftp/left_hand/index/joint1/cmd` (Float64)
- `/ftp/left_hand/middle/joint1/cmd` (Float64)
- `/ftp/left_hand/ring/joint1/cmd` (Float64)
- `/ftp/left_hand/little/joint1/cmd` (Float64)
- `/ftp/right_hand/index/joint1/cmd` (Float64)
- `/ftp/right_hand/middle/joint1/cmd` (Float64)
- `/ftp/right_hand/ring/joint1/cmd` (Float64)
- `/ftp/right_hand/little/joint1/cmd` (Float64)

**拇指关节2命令 (映射输入):**
- `/ftp/left_hand/thumb/joint2/cmd` (Float64)
- `/ftp/right_hand/thumb/joint2/cmd` (Float64)

### 订阅话题 (joint12_mapping_controller → Gazebo)

控制器会自动将输入映射到以下Gazebo仿真话题：
- `/model/ftp_left_hand_nested/joint/left_index_1_joint/cmd_vel`
- `/model/ftp_left_hand_nested/joint/left_index_2_joint/cmd_vel` (自动映射)
- ... (其他手指关节)

## 参数校准

### 传感器校准 (sensor_to_gazebo_bridge.py)

如果仿真手指运动范围不正确，请修改以下参数：

```python
# 传感器原始值范围
self.sensor_min = 500    # 手指伸直时的传感器读数
self.sensor_max = 3500   # 手指完全弯曲时的传感器读数

# 关节角度范围
self.joint_min = 1.52    # 关节伸直角度 (rad)
self.joint_max = 3.14    # 关节弯曲角度 (rad)
```

**校准步骤:**
1. 让用户伸直手指，记录传感器值 → 设置为 `sensor_min`
2. 让用户完全弯曲手指，记录传感器值 → 设置为 `sensor_max`
3. 重启桥接器

## 故障排查

### 问题1: 树莓派连接不上Ubuntu

**检查清单:**
- [ ] 确认Ubuntu IP地址是否为 `10.42.0.1` (使用 `hostname -I` 查看)
- [ ] 确认防火墙是否允许 9999 端口 (`sudo ufw allow 9999`)
- [ ] 检查树莓派和Ubuntu是否在同一网络
- [ ] 查看桥接器日志，确认是否显示 "等待树莓派连接..."

### 问题2: 仿真手指不动

**检查清单:**
- [ ] Gazebo 是否正常运行
- [ ] `joint12_mapping_controller` 是否启动成功
- [ ] 使用 `ros2 topic list` 查看话题是否存在
- [ ] 使用 `ros2 topic echo /ftp/left_hand/index/joint1/cmd` 监听数据
- [ ] 检查传感器数据是否正常接收 (查看桥接器日志)

### 问题3: 手指运动方向反了

修改 `sensor_to_gazebo_bridge.py` 中的映射逻辑：

```python
# 原始映射
angle = self.joint_min + normalized * (self.joint_max - self.joint_min)

# 反向映射
angle = self.joint_max - normalized * (self.joint_max - self.joint_min)
```

### 问题4: 手指运动范围过大/过小

调整 `sensor_min` 和 `sensor_max` 参数（见"参数校准"章节）。

## 系统监控

### 查看实时数据流

**监听传感器数据 (在Ubuntu上):**
```bash
# 监听端口9999的TCP数据
nc -l -p 9999
```

**监听ROS2话题:**
```bash
# 监听食指关节1命令
ros2 topic echo /ftp/left_hand/index/joint1/cmd

# 查看所有话题
ros2 topic list

# 查看话题发布频率
ros2 topic hz /ftp/left_hand/index/joint1/cmd
```

### 日志输出

**树莓派端日志:**
- 显示蓝牙连接状态
- 显示WiFi连接状态
- 显示数据包接收统计

**Ubuntu桥接器日志:**
- 显示TCP连接状态
- 显示接收到的传感器数据
- 每2秒打印一次数据统计

## 性能优化

### 降低数据传输量

如果WiFi带宽不足，可以在 `gatt_blu_251202.py` 中注释掉触觉传感器数据：

```python
# 注释掉这部分，只发送弯曲传感器和陀螺仪
# for g_name, g_val in data.tactile.items():
#     wifi_payload["tactile"][g_name] = {}
#     for k, v in g_val.items():
#         wifi_payload["tactile"][g_name][k] = v.tolist()
```

### 调整发布频率

在 `sensor_to_gazebo_bridge.py` 中修改定时器频率：

```python
# 原始: 20Hz (0.05秒)
self.timer = self.create_timer(0.05, self._publish_to_gazebo)

# 降低到10Hz (0.1秒)
self.timer = self.create_timer(0.1, self._publish_to_gazebo)
```

## 文件清单

### 树莓派端
- `sensors/gatt_blu_251202.py` - 蓝牙传感器采集和WiFi发送

### Ubuntu端
- `gazebos/scripts/sensor_to_gazebo_bridge.py` - 传感器数据接收和ROS2桥接
- `gazebos/scripts/joint12_mapping_controller.py` - 关节映射控制器 (已存在)
- `gazebos/start_sensor_hand_control.sh` - 一键启动脚本
- `gazebos/SENSOR_CONTROL_GUIDE.md` - 本使用指南

## 开发者信息

**数据流时序:**
1. 蓝牙传感器 → 树莓派 (异步接收, ~100Hz)
2. 树莓派 → WiFi → Ubuntu (TCP, JSON格式)
3. Ubuntu 桥接器 → ROS2 话题 (20Hz 定时发布)
4. 关节映射控制器 → Gazebo (10Hz 速度控制)

**关键性能参数:**
- 蓝牙采样率: ~100Hz
- WiFi 传输延迟: ~10-50ms
- ROS2 发布频率: 20Hz
- Gazebo 更新频率: 10Hz
- 端到端延迟: ~100-200ms

## 致谢

系统基于以下组件构建：
- ROS2 Humble
- Gazebo Harmonic
- Bleak (Python BLE 库)
- Dynamixel SDK
