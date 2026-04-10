#!/usr/bin/env bash
# Helper to run thumb_from_joint2_and_publish.py in a ROS2 environment
# Usage: ./run_thumb_publish.sh <angle> [deg|rad] [model]
# Example: ./run_thumb_publish.sh 140 deg ftp_right_hand

set -euo pipefail
ANGLE=${1:-140}
UNIT=${2:-deg}
MODEL=${3:-ftp_right_hand}

# Adjust ROS2 distro if needed
ROS2_SETUP=/opt/ros/humble/setup.bash
if [ ! -f "$ROS2_SETUP" ]; then
  echo "ERROR: ROS2 setup not found at $ROS2_SETUP. Please update this script to point to your ROS2 installation." >&2
  exit 1
fi

source "$ROS2_SETUP"
# Optionally source your workspace if you have one
# source ~/your_ros2_ws/install/setup.bash || true

python3 "$(dirname "$0")/thumb_from_joint2_and_publish.py" \
  --angle "$ANGLE" \
  --input-unit "$UNIT" \
  --output-unit rad \
  --model "$MODEL" \
  --joint2 right_thumb_2_joint \
  --joint3 right_thumb_3_joint \
  --joint4 right_thumb_4_joint \
  --once
