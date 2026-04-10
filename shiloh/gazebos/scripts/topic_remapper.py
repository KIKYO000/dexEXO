#!/usr/bin/env python3
"""
Topic Remapping Node for FTP Dexterous Hands
Maps ROS /cmd_pos topics to Gazebo /cmd_vel topics through ros_gz_bridge
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64


class TopicRemapper(Node):
    def __init__(self):
        super().__init__('ftp_hands_topic_remapper')
        
        # Define all 16 joints (8 per hand)
        joints = {
            'right': ['index_1', 'index_2', 'middle_1', 'middle_2',
                     'ring_1', 'ring_2', 'little_1', 'little_2'],
            'left': ['index_1', 'index_2', 'middle_1', 'middle_2',
                    'ring_1', 'ring_2', 'little_1', 'little_2']
        }
        
        self.publishers = {}
        self.subscriptions = {}
        
        # Create subscribers and publishers for each joint
        for hand, joint_list in joints.items():
            for joint in joint_list:
                # Input topic: /model/.../cmd_pos (user-friendly name)
                input_topic = f'/model/ftp_{hand}_hand_nested/joint/{hand}_{joint}_joint/cmd_pos'
                # Output topic: /model/.../cmd_vel (what JointController expects)
                output_topic = f'/model/ftp_{hand}_hand_nested/joint/{hand}_{joint}_joint/cmd_vel'
                
                # Create publisher for cmd_vel
                self.publishers[joint] = self.create_publisher(Float64, output_topic, 10)
                
                # Create subscriber for cmd_pos with lambda to capture correct publisher
                self.subscriptions[joint] = self.create_subscription(
                    Float64,
                    input_topic,
                    lambda msg, pub=self.publishers[joint]: pub.publish(msg),
                    10
                )
        
        self.get_logger().info(f'✅ Topic remapper initialized for {len(self.publishers)} joints')
        self.get_logger().info('📌 Mapping: /cmd_pos -> /cmd_vel')


def main(args=None):
    rclpy.init(args=args)
    remapper = TopicRemapper()
    
    try:
        rclpy.spin(remapper)
    except KeyboardInterrupt:
        pass
    finally:
        remapper.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
