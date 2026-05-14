#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import String


class LaneCameraNode(Node):
    def __init__(self):
        super().__init__('cam_controller')

        self.robot_mode = 'manual'
        self.latest_lane_cmd = Twist()

        self.mode_sub = self.create_subscription(String, '/robot_mode', self.mode_callback, 10)
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel_lane', 10)

        self.create_timer(0.1, self.control_loop)

    def mode_callback(self, msg: String):
        self.robot_mode = msg.data.strip().lower()

        if self.robot_mode != 'lane':
            self.publish_stop()
            
    def publish_stop(self):
        self.latest_lane_cmd = Twist()
        self.cmd_pub.publish(self.latest_lane_cmd)
        
    def control_loop(self):
        if self.robot_mode != 'lane':
            return
        self.latest_lane_cmd = self.compute_lane_command()
        self.cmd_pub.publish(self.latest_lane_cmd)


    def compute_lane_command(self):

        cmd = Twist()
        cmd.linear.x = 0.0
        cmd.angular.z = 0.0
        return cmd

    


def main(args=None):
    rclpy.init(args=args)
    node = LaneCameraNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()