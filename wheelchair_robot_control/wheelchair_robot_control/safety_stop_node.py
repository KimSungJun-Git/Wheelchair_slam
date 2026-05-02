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
        self.clearance_min_m = 0.20      # 회피 가능 판단 임계값 (20cm)
        
        self.dist_front = 9.9
        self.dist_left = 9.9
        self.dist_right = 9.9
        # ===== 위험 상태 추적 (엣지 트리거용) =====
        self.was_in_danger = False
        
        # ===== 토픽 구독 (수동 조작과 네비게이션 모두 구독) =====
        # 1. 네비게이션 명령
        #self.nav_cmd_sub = self.create_subscription(Twist, '/cmd_vel_nav', self.nav_cmd_callback, 10)
        self.nav_cmd_sub = self.create_subscription(Twist, '/cmd_vel_nav', self.nav_cmd_callback, 10)
        self.front_sub = self.create_subscription(Range, '/ultrasonic/range', self.front_callback, 10)
        self.left_sub = self.create_subscription(Range, '/ultrasonic/left', self.left_callback, 10)
        self.right_sub = self.create_subscription(Range, '/ultrasonic/right', self.right_callback, 10)

        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel_safe', 10)
        self.zone_pub = self.create_publisher(String, '/current_zone', 10)
        self.avoid_pub = self.create_publisher(String, '/avoidance_direction', 10)
        self.alert_pub = self.create_publisher(String, '/safety_alert', 10)

        # ===== 토픽 발행 =====
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel_safe', 10)
        self.zone_pub = self.create_publisher(String, '/current_zone', 10)

        self.create_timer(1.0, self.publish_zone)
        self.create_timer(0.1, self.check_danger_state)
        self.get_logger().info(
            f'Safety Stop Node 시작 | 전방 정지: {self.danger_distance_m*100:.0f}cm | '
            f'회피 판단: 좌우 비교 (≥{self.clearance_min_m*100:.0f}cm 여유 시 권장)')
    
    
    def front_callback(self, msg: Range):
        self.dist_front = msg.range

    def left_callback(self, msg: Range):
        self.dist_left = msg.range

    def right_callback(self, msg: Range):
        self.dist_right = msg.range

    def ultrasonic_callback(self, msg: Range):
        self.current_distance_m = msg.range
        
    def check_danger_state(self):
        """위험 진입/탈출 순간에 딱 한 번 알림 발행"""
        in_danger_now = self.dist_front <= self.danger_distance_m

        # 안전 → 위험 (엣지 트리거)
        if in_danger_now and not self.was_in_danger:
            direction = self.decide_avoidance()
            self.get_logger().error(
                f'⚠️ 전방 장애물 진입! F:{self.dist_front*100:.1f}cm '
                f'L:{self.dist_left*100:.1f}cm R:{self.dist_right*100:.1f}cm '
                f'권장 회피: {direction}')

            alert_msg = String()
            alert_msg.data = 'obstacle_too_close'
            self.alert_pub.publish(alert_msg)

            # 회피 방향도 함께 발행
            avoid_msg = String()
            avoid_msg.data = direction
            self.avoid_pub.publish(avoid_msg)
            # 위험 → 안전 (엣지 트리거)
        elif not in_danger_now and self.was_in_danger:
            self.get_logger().info(
                f'✅ 전방 장애물 해소. F:{self.dist_front*100:.1f}cm')

            alert_msg = String()
            alert_msg.data = 'obstacle_cleared'
            self.alert_pub.publish(alert_msg)

        self.was_in_danger = in_danger_now
        
    def nav_cmd_callback(self, msg: Twist):
        safe_msg = Twist()
        safe_msg.linear = msg.linear
        safe_msg.angular = msg.angular

        # 전방 위험 + 전진 명령일 때 정지
        if msg.linear.x > 0.0 and self.dist_front <= self.danger_distance_m:
            safe_msg.linear.x = 0.0  # 회전/후진은 허용

        self.cmd_pub.publish(safe_msg)
        
    def decide_avoidance(self) -> str:
        """좌우 거리 비교해서 회피 방향 결정"""
        # 양쪽 다 막혀있으면 후진 권장
        if self.dist_left < self.clearance_min_m and \
           self.dist_right < self.clearance_min_m:
            return 'blocked'  # 후진 또는 정지 유지

        # 더 멀리 떨어진 쪽으로
        if self.dist_left > self.dist_right:
            return 'left'
        elif self.dist_right > self.dist_left:
            return 'right'
        else:
            return 'left'  # 동률이면 임의로 좌측
        
    
    def publish_zone(self):
        zone_msg = String()
        if self.dist_front <= self.danger_distance_m:
            zone_msg.data = (
                f'위험구역(정지) | F:{self.dist_front*100:.1f}cm '
                f'L:{self.dist_left*100:.1f}cm R:{self.dist_right*100:.1f}cm')
        else:
            zone_msg.data = (
                f'일반구역 | F:{self.dist_front*100:.1f}cm '
                f'L:{self.dist_left*100:.1f}cm R:{self.dist_right*100:.1f}cm')
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