# 灵巧手与力反馈手套启动命令

## 系统架构

```
灵巧手触觉传感器 --DDS--> dds_to_force.py --TCP--> finger_force.py --舵机--> 力反馈手套
                         (目标力计算)            (舵机控制+BLE反馈)
```

## 树莓派终端命令

```bash
# 1. 配置网络（每次开机需执行）
sudo ip addr add 192.168.123.100/24 dev eth0
sudo ip link set eth0 up
```

### 终端 1：灵巧手驱动

```bash
cd /home/pi/dexEXO/ftp/inspire_hand_ws/inspire_hand_sdk/example
source /home/pi/dexEXO/dexEXO/bin/activate
python Headless_driver_r.py
```

### 终端 2：舵机力反馈控制

```bash
cd /home/pi/dexEXO/Finger_force_test
source /home/pi/dexEXO/dexEXO/bin/activate
python finger_force.py
```

### 终端 3：DDS 触觉数据桥接

```bash
cd /home/pi/dexEXO/Finger_force_test
source /home/pi/dexEXO/dexEXO/bin/activate
python dds_to_force.py
```

**启动顺序：终端1 → 终端2 → 终端3**

## 程序说明

### dds_to_force.py
- 订阅 DDS 话题 `rt/inspire_hand/touch/r`
- 读取食指指尖触觉数据 (fingerfour 的 max 值)
- 使用标定公式转换: `F(N) = 0.00292650 * raw_max - 0.60379472`
- 通过 TCP 端口 8888 发送 `N:2:力值` 给 finger_force.py

### finger_force.py
- TCP 服务器监听 8888 端口
- 接收目标力命令，控制舵机2
- BLE 连接力反馈手套获取实际触觉反馈
- PID 力闭环控制 + 佩戴位置初始化

## 佩戴操作流程

1. 启动终端1、2、3（见上方）
2. 戴好力反馈手套，调整好手指位置
3. 在终端2中输入 `INIT` 进行佩戴初始化（记录当前位置）
4. 启动终端3 开始力反馈控制
5. 当目标力变为0或BLE断连时，舵机会自动回到INIT时记录的位置

## 首次使用需额外执行

```bash
# 激活串口（只需执行一次，然后重启）
sudo raspi-config
# 选择: Interface Options -> Serial Port -> No(登录shell) -> Yes(硬件串口)
sudo reboot

# 安装依赖（只需执行一次）
pip3 install dynamixel-sdk bleak
```

## 手动测试命令

在 finger_force.py 运行时，可以手动输入：
- `INIT` - **佩戴初始化**（记录所有舵机当前位置，必须先执行）
- `INIT:2` - 初始化单个舵机（例如舵机2）
- `N:2:1.5` - 设置舵机2目标力为1.5N
- `N:2:0` - 舵机2回到初始化位置
- `NALL:0` - 所有舵机回到初始化位置
- `STATUS` - 查看状态
- `HELP` - 查看所有命令
