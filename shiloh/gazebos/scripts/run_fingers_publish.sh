#!/usr/bin/env bash
# Helper to run fingers_from_joint1_and_publish.py in a ROS2 environment
# Usage examples:
#   ./run_fingers_publish.sh right ftp_right_hand 0.6 rad --once
#   ./run_fingers_publish.sh left  ftp_left_hand  30  deg --rate 10
#   # 或者单独给每根手指：
#   ./run_fingers_publish.sh right ftp_right_hand --unit deg --index 20 --middle 30 --ring 25 --little 15 --once

# 注意：不要在 source 之前启用 `set -u`，否则 ROS2 ament setup 会因为未绑定变量报错。
set -eo pipefail

# Adjust ROS2 distro if needed
ROS2_SETUP=/opt/ros/humble/setup.bash
if [ ! -f "$ROS2_SETUP" ]; then
  echo "ERROR: ROS2 setup not found at $ROS2_SETUP. Please update this script to point to your ROS2 installation." >&2
  exit 1
fi
source "$ROS2_SETUP"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PY="$SCRIPT_DIR/fingers_from_joint1_and_publish.py"

if [ ! -f "$PY" ]; then
  echo "ERROR: not found $PY" >&2
  exit 1
fi

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 <hand:left|right> <model> [--angle <v>|--index <v> --middle <v> --ring <v> --little <v>] [--unit rad|deg] [--once|--rate N]" >&2
  exit 2
fi

HAND="$1"; shift
MODEL="$1"; shift

# 选择一个能 import rclpy 的 Python 解释器（规避本地 venv 影响）
PY_CANDIDATES=("python3" "/usr/bin/python3")
PY_RUN=""
for C in "${PY_CANDIDATES[@]}"; do
  if env -u VIRTUAL_ENV -u PYTHONHOME -u PYTHONPATH PYTHONNOUSERSITE=1 "$C" -c "import rclpy" >/dev/null 2>&1; then
    PY_RUN=(env -u VIRTUAL_ENV -u PYTHONHOME -u PYTHONPATH PYTHONNOUSERSITE=1 "$C")
    break
  fi
done

if [ -z "$PY_RUN" ]; then
  echo "ERROR: 未找到可用的 Python 解释器加载 rclpy。请在 ROS2 环境中运行或为当前 Python 安装 rclpy。" >&2
  echo "提示：在此终端执行 'python3 -c \"import rclpy\"' 应该无错误。" >&2
  exit 3
fi

"${PY_RUN[@]}" "$PY" --hand "$HAND" --model "$MODEL" "$@"
