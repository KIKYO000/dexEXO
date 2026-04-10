#!/bin/bash
# 手指重置脚本 - 将所有手指恢复到初始伸直状态

echo "========================================================================"
echo "  重置双手灵巧手到初始状态"
echo "========================================================================"

# Source ROS环境
source /opt/ros/humble/setup.bash

echo "🔄 重置四指到伸直状态 (180°)..."
for hand in right left; do
    for finger in index middle ring little; do
        ros2 topic pub -1 /ftp/${hand}_hand/${finger}/joint1/cmd std_msgs/Float64 '{data: 3.14159}' &
    done
done

echo "🔄 重置大拇指到初始状态..."
for hand in right left; do
    # thumb_1 复原 (0 rad)
    ros2 topic pub -1 /ftp/${hand}_hand/thumb/joint1/cmd std_msgs/Float64 '{data: 0.0}' &
    
    # thumb_2 伸直 (101°)
    ros2 topic pub -1 /ftp/${hand}_hand/thumb/joint2/cmd std_msgs/Float64 '{data: 1.7628}' &
done

# 等待所有命令发送完成
wait

echo ""
echo "✅ 重置完成!"
echo "   - 四指: 180° (伸直)"
echo "   - 大拇指侧摆: 0 rad (贴合)"
echo "   - 大拇指弯曲: 101° (伸直)"
echo ""
echo "⏳ 等待2秒让手指运动到位..."
sleep 2
echo "✅ 所有手指已就位"
