#!/usr/bin/env bash
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="${SCRIPT_DIR}/../config/cmd_pos_static_bridges.yaml"

# 加载 ROS 2 环境
if [ -f "/opt/ros/humble/setup.bash" ]; then
  source /opt/ros/humble/setup.bash
else
  echo "未找到 /opt/ros/humble/setup.bash，请确认已安装 ROS 2 Humble"
  exit 1
fi

echo "使用 YAML: ${CONFIG}"

# 依次尝试三种启动方式：
# 1) static_bridge --bridge-file <yaml>
# 2) static_bridge --ros-args -p config_file:=<yaml>
# 3) parameter_bridge --ros-args -p config_file:=<yaml>

try_start_bridge() {
  CMD="$1"; DESC="$2"
  echo "尝试启动: ${DESC}"
  bash -lc "${CMD} &" >/dev/null 2>&1
  PID=$!
  sleep 1
  if ps -p ${PID} >/dev/null 2>&1; then
    echo "桥接已通过 ${DESC} 启动 (PID=${PID})"
    echo ${PID}
    return 0
  fi
  return 1
}

PID=""
PID=$(try_start_bridge "ros2 run ros_gz_bridge static_bridge --bridge-file \"${CONFIG}\"" "static_bridge --bridge-file") || true
if [ -z "$PID" ]; then
  PID=$(try_start_bridge "ros2 run ros_gz_bridge static_bridge --ros-args -p config_file:=\"${CONFIG}\"" "static_bridge -p config_file") || true
fi
if [ -z "$PID" ]; then
  PID=$(try_start_bridge "ros2 run ros_gz_bridge parameter_bridge --ros-args -p config_file:=\"${CONFIG}\"" "parameter_bridge -p config_file") || true
fi

if [ -z "$PID" ]; then
  echo "桥接进程启动失败，请检查 ros_gz_bridge 版本与 YAML 路径: ${CONFIG}"
  exit 1
fi

echo "静态桥已启动 (PID=${PID})。按需使用："
echo "  ros2 topic info /model/ftp_right_hand_nested/joint/right_index_1_joint/cmd_pos"