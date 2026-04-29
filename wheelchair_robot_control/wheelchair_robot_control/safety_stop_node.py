#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Range
from std_msgs.msg import String

class SafetyStopNode(Node):
    def __init__(self):
        super().__init__('safety_stop_node')

        # 설정값
        self.danger_distance_m = 0.15  # 15cm
        self.current_distance_m = 9.9 

        # ===== 토픽 구독 (수동 조작과 네비게이션 모두 구독) =====
        # 1. 네비게이션 명령
        self.nav_cmd_sub = self.create_subscription(
            Twist, '/cmd_vel_nav', self.nav_cmd_callback, 10)
        
        # 2. 수동 조작 명령 (키보드 제어 등)
        self.manual_cmd_sub = self.create_subscription(
            Twist, '/cmd_vel_manual', self.manual_cmd_callback, 10)
        
        # 3. 라즈베리파이 초음파 센서
        self.ultrasonic_sub = self.create_subscription(
            Range, '/ultrasonic/range', self.ultrasonic_callback, 10)

        # ===== 토픽 발행 =====
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel_safe', 10)
        self.zone_pub = self.create_publisher(String, '/current_zone', 10)

        self.create_timer(1.0, self.publish_zone)
        self.get_logger().info('Safety Stop Node: 수동/네비 통합 안전 모드 활성화')

    def ultrasonic_callback(self, msg: Range):
        self.current_distance_m = msg.range

    def nav_cmd_callback(self, msg: Twist):
        # 네비게이션 명령 처리
        self.process_and_publish(msg, "Navigation")

    def manual_cmd_callback(self, msg: Twist):
        # 수동 조작 명령 처리
        self.process_and_publish(msg, "Manual")

    def process_and_publish(self, msg, source):
        """명령의 안전성을 검사하고 안전한 토픽으로 재발행"""
        safe_msg = Twist()
        # 기본적으로 모든 명령 복사
        safe_msg.linear = msg.linear
        safe_msg.angular = msg.angular

        # 전진 중이고 장애물이 15cm 이내인 경우
        if msg.linear.x > 0.0 and self.current_distance_m <= self.danger_distance_m:
            self.get_logger().warn(
                f'[{source}] 전방 장애물 감지! ({self.current_distance_m*100:.1f}cm). 전진 정지!'
            )
            safe_msg.linear.x = 0.0  # 전진만 0으로 정지 (회전 및 후진은 허용)

        self.cmd_pub.publish(safe_msg)

    def publish_zone(self):
        zone_msg = String()
        if self.current_distance_m <= self.danger_distance_m:
            zone_msg.data = '위험구역(정지)'
        else:
            zone_msg.data = '일반구역'
        self.zone_pub.publish(zone_msg)

def main(args=None):
    rclpy.init(args=args)
    node = SafetyStopNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()