#!/usr/bin/env python3
# safety_stop_node.py
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, PoseWithCovarianceStamped
from sensor_msgs.msg import LaserScan
from std_msgs.msg import String
import math


class SafetyStopNode(Node):
    def __init__(self):
        super().__init__('safety_stop_node')

        # ===== 파라미터 =====
        self.declare_parameter('stop_distance', 0.20)            # 전방 정지 거리 (m)
        self.declare_parameter('slowdown_distance', 0.40)        # 전방 감속 시작 거리 (m)
        self.declare_parameter('front_angle_range', 40.0)        # 전방 감지 각도 (+-20도)
        self.declare_parameter('rear_stop_distance', 0.10)       # 후방 정지 거리 (m)
        self.declare_parameter('rear_slowdown_distance', 0.15)   # 후방 감속 시작 거리 (m)
        self.declare_parameter('rear_angle_range', 40.0)         # 후방 감지 각도 (+-20도)

        self.stop_distance = self._get_float('stop_distance', 0.20)
        self.slowdown_distance = self._get_float('slowdown_distance', 0.40)
        self.front_angle_deg = self._get_float('front_angle_range', 40.0)
        self.rear_stop_distance = self._get_float('rear_stop_distance', 0.10)
        self.rear_slowdown_distance = self._get_float('rear_slowdown_distance', 0.25)
        self.rear_angle_deg = self._get_float('rear_angle_range', 40.0)

        # ===== 구역별 속도 제한 설정 =====
        self.slow_zones = [
            (-0.02, 1.23, -0.79, 0.89, 0.7, '서행구역1'),
        ]

        self.robot_x = 0.0
        self.robot_y = 0.0
        self.current_zone = '일반구역'
        self.target_speed_ratio = 1.0
        self.current_speed_ratio = 1.0
        self.smooth_factor = 0.15

        # ===== 장애물 상태 =====
        self.front_min_dist = float('inf')
        self.rear_min_dist = float('inf')
        self.front_state = 'clear'
        self.rear_state = 'clear'

        # ===== 토픽 구독 =====
        self.nav_cmd_sub = self.create_subscription(
            Twist, '/cmd_vel_nav', self.cmd_vel_callback, 10)
        self.scan_sub = self.create_subscription(
            LaserScan, '/scan', self.scan_callback, 10)
        self.amcl_sub = self.create_subscription(
            PoseWithCovarianceStamped, '/amcl_pose', self.amcl_callback, 10)

        # ===== 토픽 발행 =====
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel_safe', 10)
        self.zone_pub = self.create_publisher(String, '/current_zone', 10)

        # ===== 타이머 =====
        self.create_timer(0.1, self.smooth_speed_update)
        self.create_timer(1.0, self.publish_zone)

        self.get_logger().info(
            f'Safety Stop Node 시작\n'
            f'  전방 정지: {self.stop_distance}m | 감속: {self.slowdown_distance}m | 각도: ±{self.front_angle_deg / 2.0:.0f}도\n'
            f'  후방 정지: {self.rear_stop_distance}m | 감속: {self.rear_slowdown_distance}m | 각도: ±{self.rear_angle_deg / 2.0:.0f}도\n'
            f'  입력: /cmd_vel_nav → 출력: /cmd_vel_safe')

    # ===== 파라미터 헬퍼 =====
    def _get_float(self, name: str, default: float) -> float:
        v = self.get_parameter(name).value
        return float(v) if v is not None else default

    # ===== 속도 부드러운 전환 =====
    def smooth_speed_update(self):
        diff = self.target_speed_ratio - self.current_speed_ratio
        self.current_speed_ratio += diff * self.smooth_factor
        if abs(diff) < 0.01:
            self.current_speed_ratio = self.target_speed_ratio

    # ===== LiDAR 전방 + 후방 감지 =====
    def scan_callback(self, msg: LaserScan):
        front_half_rad = math.radians(self.front_angle_deg) / 2.0
        rear_half_rad = math.radians(self.rear_angle_deg) / 2.0

        front_min = float('inf')
        rear_min = float('inf')

        for i, r in enumerate(msg.ranges):
            if r < msg.range_min or r > msg.range_max:
                continue
            angle = msg.angle_min + i * msg.angle_increment

            # 전방: 0도 기준
            if abs(angle) <= front_half_rad:
                if r < front_min:
                    front_min = r

            # 후방: ±180도 기준
            rear_angle = abs(abs(angle) - math.pi)
            if rear_angle <= rear_half_rad:
                if r < rear_min:
                    rear_min = r

        self.front_min_dist = front_min
        self.rear_min_dist = rear_min

        # 전방 상태
        self.front_state = self._check_state(
            front_min, self.stop_distance, self.slowdown_distance,
            '전방', self.front_state)

        # 후방 상태
        self.rear_state = self._check_state(
            rear_min, self.rear_stop_distance, self.rear_slowdown_distance,
            '후방', self.rear_state)

    def _check_state(self, dist: float, stop_d: float, slow_d: float,
                     direction: str, prev_state: str) -> str:
        if dist <= stop_d:
            if prev_state != 'stop':
                self.get_logger().warn(
                    f'{direction} 장애물 정지! 거리: {dist:.2f}m')
            return 'stop'
        elif dist <= slow_d:
            if prev_state != 'slowdown':
                self.get_logger().info(
                    f'{direction} 장애물 감속 거리: {dist:.2f}m')
            return 'slowdown'
        return 'clear'

    # ===== AMCL 구역 판별 =====
    def amcl_callback(self, msg: PoseWithCovarianceStamped):
        self.robot_x = msg.pose.pose.position.x
        self.robot_y = msg.pose.pose.position.y

        for (x_min, x_max, y_min, y_max, ratio, name) in self.slow_zones:
            if x_min <= self.robot_x <= x_max and y_min <= self.robot_y <= y_max:
                if self.current_zone != name:
                    self.get_logger().warn(
                        f'서행 구역 진입: {name} | 속도 제한: {ratio * 100:.0f}%')
                self.current_zone = name
                self.target_speed_ratio = ratio
                return

        if self.current_zone != '일반구역':
            self.get_logger().info('일반 구역 복귀 | 속도 제한 해제')
        self.current_zone = '일반구역'
        self.target_speed_ratio = 1.0

    def publish_zone(self):
        zone_msg = String()
        zone_msg.data = (
            f'{self.current_zone} | 속도: {self.current_speed_ratio * 100:.0f}% | '
            f'전방: {self.front_state} ({self.front_min_dist:.2f}m) | '
            f'후방: {self.rear_state} ({self.rear_min_dist:.2f}m) | '
            f'위치: ({self.robot_x:.2f}, {self.robot_y:.2f})')
        self.zone_pub.publish(zone_msg)

    # ===== 속도 필터링 =====
    def cmd_vel_callback(self, msg: Twist):
        safe_cmd = Twist()
        safe_cmd.angular.z = msg.angular.z

        if msg.linear.x > 0:
            # ===== 전진 =====
            if self.front_state == 'stop':
                safe_cmd.linear.x = 0.0
            elif self.front_state == 'slowdown':
                ratio = (self.front_min_dist - self.stop_distance) / \
                        (self.slowdown_distance - self.stop_distance)
                ratio = max(0.2, min(1.0, ratio))
                safe_cmd.linear.x = msg.linear.x * ratio
            else:
                safe_cmd.linear.x = msg.linear.x

        elif msg.linear.x < 0:
            # ===== 후진 =====
            if self.rear_state == 'stop':
                safe_cmd.linear.x = 0.0
            elif self.rear_state == 'slowdown':
                ratio = (self.rear_min_dist - self.rear_stop_distance) / \
                        (self.rear_slowdown_distance - self.rear_stop_distance)
                ratio = max(0.2, min(1.0, ratio))
                safe_cmd.linear.x = msg.linear.x * ratio
            else:
                safe_cmd.linear.x = msg.linear.x
        else:
            safe_cmd.linear.x = 0.0

        # 서행 구역 속도 제한
        if self.current_speed_ratio < 1.0:
            safe_cmd.linear.x *= self.current_speed_ratio
            safe_cmd.angular.z *= self.current_speed_ratio

        self.cmd_pub.publish(safe_cmd)


def main(args=None):
    rclpy.init(args=args)
    node = SafetyStopNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()