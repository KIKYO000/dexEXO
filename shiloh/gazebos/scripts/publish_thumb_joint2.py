#!/usr/bin/env python3
"""
Simple ROS2 publisher for thumb joint2 angle.
Publishes std_msgs/msg/Float64 to the ignition_ros2_bridge expected topic:
  /model/<model_name>/joint/<joint_name>/cmd_pos

Usage:
  ./publish_thumb_joint2.py --model ftp_right_hand --joint right_thumb_2_joint --angle 0.5
  ./publish_thumb_joint2.py --topic /model/ftp_right_hand/joint/right_thumb_2_joint/cmd_pos --angle 0.5

If ROS2 is not installed/configured this script will fail. Adjust topic/model/joint names as needed.
"""
import argparse
import json
import time

try:
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import Float64
except Exception as e:
    rclpy = None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default='ftp_right_hand', help='Model name in ignition')
    parser.add_argument('--joint', default='right_thumb_2_joint', help='Joint name in model')
    parser.add_argument('--topic', default=None, help='Full topic to publish to (overrides model/joint)')
    parser.add_argument('--angle', type=float, required=True, help='Joint angle in radians to publish')
    parser.add_argument('--rate', type=float, default=10.0, help='Publish rate Hz')
    args = parser.parse_args()

    if args.topic:
        topic = args.topic
    else:
        topic = f'/model/{args.model}/joint/{args.joint}/cmd_pos'

    if rclpy is None:
        print('ERROR: rclpy (ROS2 Python) not available in this environment. Please run this on a ROS2-enabled shell.')
        print(f'Would publish to topic: {topic} value: {args.angle}')
        return

    rclpy.init()
    node = Node('thumb_joint2_publisher')
    pub = node.create_publisher(Float64, topic, 10)
    msg = Float64()
    msg.data = args.angle

    try:
        print(f'Publishing {msg.data} to {topic} at {args.rate} Hz (Ctrl-C to stop)')
        while rclpy.ok():
            pub.publish(msg)
            rclpy.spin_once(node, timeout_sec=1.0/args.rate)
            time.sleep(1.0/args.rate)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
