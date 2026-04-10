#!/usr/bin/env bash
###############################################################################
# FTP 双手灵巧手完整控制系统启动脚本
# 功能:
#   1. 启动 Gazebo 仿真环境
#   2. 启动 ROS-Gazebo 桥接(连接所有 16 个关节)
#   3. 提供测试命令示例
###############################################################################

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

echo "==============================================="
echo "🤖 FTP 双手灵巧手控制系统启动"
echo "==============================================="

# 检查 Gazebo 是否已运行 (更完善的检测)
GAZEBO_RUNNING=false
if pgrep -f "ign gazebo" > /dev/null 2>&1; then
    GAZEBO_RUNNING=true
elif pgrep -f "ign-gazebo" > /dev/null 2>&1; then
    GAZEBO_RUNNING=true
elif ps aux | grep -E "(ign gazebo|ign-gazebo)" | grep -v grep > /dev/null 2>&1; then
    GAZEBO_RUNNING=true
fi

if [ "$GAZEBO_RUNNING" = true ]; then
    echo "✅ Gazebo 已在运行"
else
    echo ""
    echo "❌ 请先启动 Gazebo (在另一个终端):"
    echo "   ./launch_hands_correct.sh"
    echo ""
    echo "💡 提示: 等待 Gazebo GUI 完全加载后再启动桥接"
    echo ""
    exit 1
fi

# 检查 ROS 环境
if [ ! -f "/opt/ros/humble/setup.bash" ]; then
    echo "❌ 未找到 ROS 2 Humble"
    exit 1
fi

echo ""
echo "🔗 启动 ROS-Gazebo 桥接..."
echo "   连接 16 个关节 (cmd_vel 话题)"

# 停止现有桥接
pkill -f "ros_gz_bridge" 2>/dev/null || true
sleep 1

# 启动桥接(后台运行)
bash --login -c "source /opt/ros/humble/setup.bash && \
    ros2 run ros_gz_bridge parameter_bridge \
    /model/ftp_right_hand_nested/joint/right_index_1_joint/cmd_vel@std_msgs/msg/Float64]gz.msgs.Double \
    /model/ftp_right_hand_nested/joint/right_index_2_joint/cmd_vel@std_msgs/msg/Float64]gz.msgs.Double \
    /model/ftp_right_hand_nested/joint/right_middle_1_joint/cmd_vel@std_msgs/msg/Float64]gz.msgs.Double \
    /model/ftp_right_hand_nested/joint/right_middle_2_joint/cmd_vel@std_msgs/msg/Float64]gz.msgs.Double \
    /model/ftp_right_hand_nested/joint/right_ring_1_joint/cmd_vel@std_msgs/msg/Float64]gz.msgs.Double \
    /model/ftp_right_hand_nested/joint/right_ring_2_joint/cmd_vel@std_msgs/msg/Float64]gz.msgs.Double \
    /model/ftp_right_hand_nested/joint/right_little_1_joint/cmd_vel@std_msgs/msg/Float64]gz.msgs.Double \
    /model/ftp_right_hand_nested/joint/right_little_2_joint/cmd_vel@std_msgs/msg/Float64]gz.msgs.Double \
    /model/ftp_right_hand_nested/joint/right_thumb_1_joint/cmd_vel@std_msgs/msg/Float64]gz.msgs.Double \
    /model/ftp_right_hand_nested/joint/right_thumb_2_joint/cmd_vel@std_msgs/msg/Float64]gz.msgs.Double \
    /model/ftp_right_hand_nested/joint/right_thumb_3_joint/cmd_vel@std_msgs/msg/Float64]gz.msgs.Double \
    /model/ftp_right_hand_nested/joint/right_thumb_4_joint/cmd_vel@std_msgs/msg/Float64]gz.msgs.Double \
    /model/ftp_left_hand_nested/joint/left_index_1_joint/cmd_vel@std_msgs/msg/Float64]gz.msgs.Double \
    /model/ftp_left_hand_nested/joint/left_index_2_joint/cmd_vel@std_msgs/msg/Float64]gz.msgs.Double \
    /model/ftp_left_hand_nested/joint/left_middle_1_joint/cmd_vel@std_msgs/msg/Float64]gz.msgs.Double \
    /model/ftp_left_hand_nested/joint/left_middle_2_joint/cmd_vel@std_msgs/msg/Float64]gz.msgs.Double \
    /model/ftp_left_hand_nested/joint/left_ring_1_joint/cmd_vel@std_msgs/msg/Float64]gz.msgs.Double \
    /model/ftp_left_hand_nested/joint/left_ring_2_joint/cmd_vel@std_msgs/msg/Float64]gz.msgs.Double \
    /model/ftp_left_hand_nested/joint/left_little_1_joint/cmd_vel@std_msgs/msg/Float64]gz.msgs.Double \
    /model/ftp_left_hand_nested/joint/left_little_2_joint/cmd_vel@std_msgs/msg/Float64]gz.msgs.Double \
    /model/ftp_left_hand_nested/joint/left_thumb_1_joint/cmd_vel@std_msgs/msg/Float64]gz.msgs.Double \
    /model/ftp_left_hand_nested/joint/left_thumb_2_joint/cmd_vel@std_msgs/msg/Float64]gz.msgs.Double \
    /model/ftp_left_hand_nested/joint/left_thumb_3_joint/cmd_vel@std_msgs/msg/Float64]gz.msgs.Double \
    /model/ftp_left_hand_nested/joint/left_thumb_4_joint/cmd_vel@std_msgs/msg/Float64]gz.msgs.Double \
    > /tmp/ros_gz_bridge.log 2>&1" &

BRIDGE_PID=$!
sleep 2

# 检查桥接是否成功启动
if ps -p ${BRIDGE_PID} > /dev/null; then
    echo "✅ 桥接已启动 (PID: ${BRIDGE_PID})"
    echo "   日志: /tmp/ros_gz_bridge.log"
else
    echo "❌ 桥接启动失败,查看日志:"
    cat /tmp/ros_gz_bridge.log
    exit 1
fi

echo ""
echo "==============================================="
echo "✅ 系统启动完成!"
echo "==============================================="
echo ""
echo "📝 使用方法:"
echo ""
echo "1️⃣  测试单个关节 (右手食指关节1,弯曲到 0.8 弧度):"
echo "   bash --login -c \"source /opt/ros/humble/setup.bash && \\"
echo "   ros2 topic pub -1 /model/ftp_right_hand_nested/joint/right_index_1_joint/cmd_vel \\"
echo "   std_msgs/Float64 '{data: 0.8}'\""
echo ""
echo "2️⃣  伸直关节 (回到 0.0):"
echo "   bash --login -c \"source /opt/ros/humble/setup.bash && \\"
echo "   ros2 topic pub -1 /model/ftp_right_hand_nested/joint/right_index_1_joint/cmd_vel \\"
echo "   std_msgs/Float64 '{data: 0.0}'\""
echo ""
echo "3️⃣  控制左手中指关节2:"
echo "   bash --login -c \"source /opt/ros/humble/setup.bash && \\"
echo "   ros2 topic pub -1 /model/ftp_left_hand_nested/joint/left_middle_2_joint/cmd_vel \\"
echo "   std_msgs/Float64 '{data: 1.0}'\""
echo ""
echo "📋 可用关节名称 (每只手 8 个):"
echo "   右手: right_index_1, right_index_2, right_middle_1, right_middle_2,"
echo "        right_ring_1, right_ring_2, right_little_1, right_little_2"
echo "   左手: left_index_1, left_index_2, left_middle_1, left_middle_2,"
echo "        left_ring_1, left_ring_2, left_little_1, left_little_2"
echo ""
echo "🛑 停止桥接:"
echo "   pkill -f ros_gz_bridge"
echo ""
echo "==============================================="
