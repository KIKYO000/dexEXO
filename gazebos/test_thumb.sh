#!/bin/bash
# 大拇指映射控制测试脚本包装器
# 使用系统Python运行,隔离conda环境

# Source ROS 2环境
source /opt/ros/humble/setup.bash

# 使用系统Python运行
/usr/bin/python3 /home/wxc/projects/dexEXO/gazebos/test_thumb_mapping.py "$@"
