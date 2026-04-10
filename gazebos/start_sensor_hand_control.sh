#!/bin/bash
# 启动传感器控制灵巧手系统
# 
# 使用方法:
#   1. 确保树莓派上已运行 gatt_blu_251202.py
#   2. 在 Ubuntu 上运行此脚本: ./start_sensor_hand_control.sh

set -e  # 遇到错误立即退出

echo "========================================="
echo "🤖 启动传感器控制灵巧手系统"
echo "========================================="
echo ""

# 检查 Gazebo 是否已运行
if ! pgrep -x "gz sim" > /dev/null; then
    echo "⚠️  Gazebo 未运行！"
    echo "请先运行: ./launch_hands_correct.sh"
    echo ""
    read -p "是否现在启动 Gazebo? (y/n): " choice
    if [ "$choice" == "y" ] || [ "$choice" == "Y" ]; then
        echo "🚀 启动 Gazebo..."
        gnome-terminal -- bash -c "./launch_hands_correct.sh; exec bash" &
        echo "⏳ 等待 Gazebo 启动 (15秒)..."
        sleep 15
    else
        echo "❌ 已取消"
        exit 1
    fi
fi

echo "✅ Gazebo 已运行"
echo ""

# 检查 ROS2 环境
if [ -z "$ROS_DISTRO" ]; then
    echo "⚠️  ROS2 环境未配置"
    echo "正在加载 ROS2 环境..."
    source /opt/ros/humble/setup.bash
    export GZ_VERSION=harmonic
fi

echo "✅ ROS2 环境: $ROS_DISTRO"
echo "✅ Gazebo 版本: $GZ_VERSION"
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GAZEBO_DIR="$(dirname "$SCRIPT_DIR")"

cd "$GAZEBO_DIR"

echo "========================================="
echo "📡 第1步: 启动关节映射控制器"
echo "========================================="
echo ""

# 启动 joint12_mapping_controller (在新终端)
gnome-terminal --title="关节映射控制器" -- bash -c "
    source /opt/ros/humble/setup.bash
    export GZ_VERSION=harmonic
    cd '$GAZEBO_DIR'
    echo '🎮 启动 joint12_mapping_controller.py...'
    python3 scripts/joint12_mapping_controller.py
    exec bash
" &

sleep 3

echo "========================================="
echo "📡 第2步: 启动传感器桥接器"
echo "========================================="
echo ""

# 启动 sensor_to_gazebo_bridge (在新终端)
gnome-terminal --title="传感器桥接器" -- bash -c "
    source /opt/ros/humble/setup.bash
    export GZ_VERSION=harmonic
    cd '$GAZEBO_DIR'
    echo '🌉 启动传感器到Gazebo桥接器...'
    echo '📡 TCP服务器监听端口: 9999'
    echo '等待树莓派连接...'
    echo ''
    python3 scripts/sensor_to_gazebo_bridge.py
    exec bash
" &

sleep 2

echo ""
echo "========================================="
echo "✅ 系统启动完成！"
echo "========================================="
echo ""
echo "📋 组件状态:"
echo "   ✓ Gazebo 仿真环境"
echo "   ✓ 关节映射控制器 (joint12_mapping_controller)"
echo "   ✓ 传感器桥接器 (sensor_to_gazebo_bridge)"
echo ""
echo "📡 现在请在树莓派上运行:"
echo "   python3 gatt_blu_251202.py"
echo ""
echo "🎮 数据流向:"
echo "   树莓派传感器 → WiFi → Ubuntu桥接器 → 关节映射控制器 → Gazebo仿真"
echo ""
echo "🛑 停止系统: Ctrl+C 或关闭相应终端窗口"
echo ""
