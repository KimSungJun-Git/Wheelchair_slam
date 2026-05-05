#!/usr/bin/env python3
# safety_stop_node.py
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan
from std_msgs.msg import String


class SafetyStopNode(Node):
    def __init__(self):
        super().__init__('safety_stop_node')

        # ===== 토픽 구독 =====
        self.nav_cmd_sub = self.create_subscription(
            Twist, '/cmd_vel_nav', self.cmd_vel_callback, 10)
        self.scan_sub = self.create_subscription(
            LaserScan, '/scan', self.scan_callback, 10)

        # ===== 토픽 발행 =====
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel_safe', 10)
        self.zone_pub = self.create_publisher(String, '/current_zone', 10)

        # ===== 타이머 =====
        self.create_timer(1.0, self.publish_zone)

        self.get_logger().info(
            'Safety Stop Node 시작\n'
            '  입력: /cmd_vel_nav → 출력: /cmd_vel_safe')

    def scan_callback(self, msg: LaserScan):
        pass

    def cmd_vel_callback(self, msg: Twist):
        self.cmd_pub.publish(msg)

    def publish_zone(self):
        zone_msg = String()
        zone_msg.data = '일반구역'
        self.zone_pub.publish(zone_msg)


def main(args=None):
    rclpy.init(args=args)
    node = SafetyStopNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()