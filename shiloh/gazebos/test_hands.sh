#!/bin/bash
# 双手运动测试包装脚本
# 使用系统Python并source ROS环境

# Source ROS 2环境
source /opt/ros/humble/setup.bash

# 运行测试脚本
/usr/bin/python3 /home/wxc/projects/dexEXO/gazebos/test_dual_hands_motion.py "$@"
