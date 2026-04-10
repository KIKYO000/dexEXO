# Finger Force BLE Controller

该目录包含树莓派端的五舵机力反馈控制脚本，使用 BLE 从 STM32 接收 `touch_sensors` 并作为力反馈闭环的反馈量。

## 依赖

- Python 3.8+
- `bleak`
- `DynamixelSDK`

## 安装依赖

在树莓派上执行：

```bash
pip3 install -r requirements.txt
```

## 运行

```bash
python3 finger_force.py
```

## Unitree G1 灵巧手触觉桥接（可选）

如果需要将 G1 上 Inspire FTP 灵巧手触觉数据作为目标力输入，可在 G1 的 PC2 上运行
`unitree_touch_bridge.py`，它会订阅 DDS 话题并通过 TCP 向树莓派发送 `N:2:NUM` 指令。

### 依赖

- `unitree_sdk2_python`
- `inspire_hand_sdk`

### 运行示例

```bash
python3 unitree_touch_bridge.py --pi-ip <树莓派IP> \
  --topic rt/inspire_hand/touch/r --finger index --region tip \
  --scale 1.0 --offset 0.0 --interval 0.1
```

> 提示：`--scale/--offset` 用于把触觉值映射为牛顿（N）。

## 说明

- 修改 `finger_force.py` 中的 `DEVICE_ADDRESSES` 为你的 STM32 BLE MAC 地址。
- STM32 发送 JSON 示例：
  ```json
  {"touch_sensors": [4.903]}
  ```
- 当 `touch_sensors` 只有一个值时，会自动广播到 5 个舵机；若有 5 个值则一一对应。
