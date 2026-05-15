#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import String


class LaneCameraNode(Node):
    def __init__(self):
        super().__init__('cam_controller')

        self.robot_mode = 'manual'
        self.mode_sub = self.create_subscription(String, '/robot_mode', self.mode_callback, 10)
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel_lane', 10)
        self.create_timer(0.1, self.control_loop)

        self.get_logger().info('Lane Camera Node 시작 → /cmd_vel_lane 발행 대기')

    def mode_callback(self, msg: String):
        self.robot_mode = msg.data.strip().lower()
        if self.robot_mode != 'lane':
            self.cmd_pub.publish(Twist())

    def control_loop(self):
        if self.robot_mode != 'lane':
            return

        linear_x, angular_z = self.compute_lane_command()

        cmd = Twist()
        cmd.linear.x = float(linear_x)
        cmd.angular.z = float(angular_z)
        self.cmd_pub.publish(cmd)

    #  여기에 작성: 카메라로 
    def compute_lane_command(self):
        """
        반환:
            linear_x  (float, m/s)  : 전진 속도
            angular_z (float, rad/s): 회전 각속도 (양수=좌회전, 음수=우회전)
        """
        linear_x = 0.0
        angular_z = 0.0
        return linear_x, angular_z


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