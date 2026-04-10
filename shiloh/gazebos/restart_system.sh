#!/usr/bin/env bash
###############################################################################
# 完整系统重启脚本 - 使用移除mimic约束的新URDF
###############################################################################

echo "=========================================="
echo "🔄 重启FTP双手灵巧手系统"
echo "=========================================="
echo ""

# 1. 停止所有相关进程
echo "1️⃣  停止现有进程..."
pkill -9 -f "ign gazebo" 2>/dev/null || true
pkill -9 -f "ros_gz_bridge" 2>/dev/null || true
pkill -9 -f "joint12_mapping_controller" 2>/dev/null || true
sleep 2

# 2. 启动Gazebo
echo "2️⃣  启动Gazebo(使用新URDF,无mimic约束)..."
cd /home/wxc/projects/dexEXO/gazebos
nohup bash launch_hands_correct.sh > /tmp/gazebo_launch.log 2>&1 &
echo "   等待Gazebo加载..."
sleep 8

# 3. 启动ROS-Gazebo桥接
echo "3️⃣  启动ROS-Gazebo桥接..."
bash start_hand_control.sh > /tmp/bridge_start.log 2>&1
sleep 2

# 4. 启动映射控制器
echo "4️⃣  启动关节1-2映射控制器..."
nohup bash start_joint12_controller.sh > /tmp/controller_start.log 2>&1 &
sleep 3

echo ""
echo "=========================================="
echo "✅ 系统启动完成!"
echo "=========================================="
echo ""
echo "📊 进程状态:"
pgrep -f "ign gazebo" > /dev/null && echo "  ✅ Gazebo运行中" || echo "  ❌ Gazebo未运行"
pgrep -f "ros_gz_bridge" > /dev/null && echo "  ✅ Bridge运行中" || echo "  ❌ Bridge未运行"
pgrep -f "joint12_mapping_controller" > /dev/null && echo "  ✅ Controller运行中" || echo "  ❌ Controller未运行"
echo ""
echo "📝 测试命令:"
echo "  伸直: ros2 topic pub -1 /ftp/right_hand/index/joint1/cmd std_msgs/Float64 '{data: 3.14}'"
echo "  弯曲: ros2 topic pub -1 /ftp/right_hand/index/joint1/cmd std_msgs/Float64 '{data: 1.52}'"
echo ""
echo "🔍 查看日志:"
echo "  tail -f /tmp/joint12_controller.log"
