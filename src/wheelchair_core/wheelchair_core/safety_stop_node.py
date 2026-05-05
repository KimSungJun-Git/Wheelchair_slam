#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, PoseWithCovarianceStamped
from std_msgs.msg import String

class SafetyStopNode(Node):
    def __init__(self):
        super().__init__('safety_stop_node')

        # ===== 구역별 속도 제한 설정 =====
        # (x_min, x_max, y_min, y_max, speed_ratio, 이름)
        self.slow_zones = [
            (-5.32, -0.81, -2.46, -0.98, 0.3, '서행구역1'),
        ]

        # (x_min, x_max, y_min, y_max, 이름)
        self.keepout_zones = [
            # (-2.0, -1.5, -1.0, -0.5, '금지구역1'),
        ]

        self.robot_x = 0.0
        self.robot_y = 0.0
        self.current_zone = '일반구역'
        self.speed_ratio = 1.0

        # 입력: collision_monitor 출력
        self.nav_cmd_sub = self.create_subscription(
            Twist, '/cmd_vel_nav', self.cmd_vel_callback, 10)

        # AMCL 위치 구독
        self.amcl_sub = self.create_subscription(
            PoseWithCovarianceStamped, '/amcl_pose', self.amcl_callback, 10)

        # 출력: mode_switch_node로 전달
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel_safe', 10)

        # 구역 상태 발행
        self.zone_pub = self.create_publisher(String, '/current_zone', 10)
        self.create_timer(1.0, self.publish_zone)

        self.get_logger().info(
            f'Safety Stop Node 시작\n'
            f'  입력: /cmd_vel_nav → 출력: /cmd_vel_safe\n'
            f'  서행 구역: {len(self.slow_zones)}개\n'
            f'  금지 구역: {len(self.keepout_zones)}개')

    def amcl_callback(self, msg):
        """AMCL 위치 업데이트 + 구역 판별"""
        self.robot_x = msg.pose.pose.position.x
        self.robot_y = msg.pose.pose.position.y

        for (x_min, x_max, y_min, y_max, ratio, name) in self.slow_zones:
            if x_min <= self.robot_x <= x_max and y_min <= self.robot_y <= y_max:
                if self.current_zone != name:
                    self.get_logger().warn(
                        f'서행 구역 진입: {name} | 속도 제한: {ratio*100:.0f}%')
                self.current_zone = name
                self.speed_ratio = ratio
                return

        for (x_min, x_max, y_min, y_max, name) in self.keepout_zones:
            if x_min <= self.robot_x <= x_max and y_min <= self.robot_y <= y_max:
                if self.current_zone != name:
                    self.get_logger().error(
                        f'금지 구역 진입: {name} | 긴급 정지!')
                self.current_zone = name
                self.speed_ratio = 0.0
                return

        if self.current_zone != '일반구역':
            self.get_logger().info('일반 구역 복귀 | 속도 제한 해제')
        self.current_zone = '일반구역'
        self.speed_ratio = 1.0

    def publish_zone(self):
        zone_msg = String()
        zone_msg.data = f'{self.current_zone} | 속도: {self.speed_ratio*100:.0f}% | 위치: ({self.robot_x:.2f}, {self.robot_y:.2f})'
        self.zone_pub.publish(zone_msg)

    def cmd_vel_callback(self, msg):
        """구역별 속도 제한 적용"""
        safe_cmd = Twist()

        if self.speed_ratio == 0.0:
            safe_cmd.linear.x = 0.0
            safe_cmd.angular.z = 0.0
        elif self.speed_ratio < 1.0:
            safe_cmd.linear.x = msg.linear.x * self.speed_ratio
            safe_cmd.angular.z = msg.angular.z * self.speed_ratio
        else:
            safe_cmd = msg

        self.cmd_pub.publish(safe_cmd)


def main(args=None):
    rclpy.init(args=args)
    node = SafetyStopNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()