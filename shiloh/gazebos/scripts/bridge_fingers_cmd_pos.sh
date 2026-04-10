#!/usr/bin/env bash
# Bridge /model/<model>/joint/<hand>_<finger>_<1|2>_joint/cmd_pos for 4 fingers
# Usage:
#   ./bridge_fingers_cmd_pos.sh right ftp_right_hand_nested
#   ./bridge_fingers_cmd_pos.sh left  ftp_left_hand_nested
#   # 同时桥接左右手：
#   ./bridge_fingers_cmd_pos.sh right ftp_right_hand_nested left ftp_left_hand_nested

set -eo pipefail

ROS2_SETUP=/opt/ros/humble/setup.bash
if [ ! -f "$ROS2_SETUP" ]; then
  echo "ERROR: ROS2 setup not found at $ROS2_SETUP" >&2
  exit 1
fi
source "$ROS2_SETUP"

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 <hand:left|right> <model> [<hand> <model> ...]" >&2
  exit 2
fi

FINGERS=(index middle ring little)
BRIDGE=ros2
BRIDGE_ARGS=(run ros_gz_bridge parameter_bridge)

pids=()
while [ "$#" -ge 2 ]; do
  HAND="$1"; shift
  MODEL="$1"; shift
  case "$HAND" in
    left|right) :;;
    *) echo "ERROR: hand must be left|right, got '$HAND'" >&2; exit 3;;
  esac
  for f in "${FINGERS[@]}"; do
    for j in 1 2; do
      JOINT="${HAND}_${f}_${j}_joint"
      TOPIC_BASE="/model/${MODEL}/joint/${JOINT}"
      # 一些Ignition控制器使用无轴索引的路径，另一些使用 /0 子路径
      for SUF in "cmd_pos" "0/cmd_pos"; do
        TOPIC="${TOPIC_BASE}/${SUF}"
        echo "Bridging ${TOPIC} (std_msgs/Float64 <-> gz.msgs.Double)"
        $BRIDGE "${BRIDGE_ARGS[@]}" \
          "${TOPIC}@std_msgs/msg/Float64@gz.msgs.Double" \
          >/dev/null 2>&1 &
        pids+=("$!")
      done
    done
  done
done

echo "Started ${#pids[@]} bridge processes. To stop: kill ${pids[*]} or pkill -f ros_gz_bridge"
