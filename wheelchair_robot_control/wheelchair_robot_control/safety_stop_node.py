#!/usr/bin/env python3
# safety_stop_node.py
import rclpy
from rclpy.node import Node
from rclpy.time import Time
from rclpy.qos import qos_profile_sensor_data
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Range, LaserScan, Imu
from nav_msgs.msg import Odometry
from std_msgs.msg import String, Bool
from typing import Optional, Dict
import json


class SafetyStopNode(Node):
    def __init__(self):
        super().__init__('safety_stop_node')

        # ===== 설정값 =====
        self.danger_distance_m = 0.20      # 전방 정지 거리
        self.clearance_min_m = 0.20         # 회피 가능 판단 임계값

        # ===== 거리 데이터 =====
        self.dist_front = 9.9
        self.dist_left = 9.9
        self.dist_right = 9.9
        self.was_in_danger = False

        # ===== 센서 위험 상태 (센서 이름 → 위험 여부) =====
        # 하나라도 True면 비상 정지. 각 센서는 독립적으로 갱신됨.
        self.sensor_danger = {
            'imu_emergency': False,           # IMU 노드의 위험 신호 (기울기/충격)
            'localization_emergency': False,  # Localization 노드의 위험 신호 (위치 분실)
            'lidar_lost': False,              # 라이다 끊김
            'imu_lost': False,                # IMU 끊김
            'ultrasonic_lost': False,         # 초음파 끊김
            'odom_lost': False,               # 모터(오도메트리) 끊김
        }
        # 현재 위험 상태인 센서 목록과 종합 비상 여부 (set_reason에서 자동 갱신)
        self.dangerous_sensors = []
        self.is_emergency = False

        # ===== 헬스 체크용 타임스탬프 =====
        # None은 "한 번도 메시지가 안 옴"을 의미
        self.last_seen: Dict[str, Optional[Time]] = {
            'lidar': None,
            'imu': None,
            'odom': None,
            'ultrasonic_front': None,
            'ultrasonic_left': None,
            'ultrasonic_right': None,
        }
        # 센서별 타임아웃 (초) — 이 시간 안에 메시지가 안 오면 끊김 판정
        self.timeout_sec = {
            'lidar': 1.0,                # 일반적으로 5~10Hz
            'imu': 1.0,                  # 일반적으로 50~100Hz
            'odom': 1.0,                 # 일반적으로 20~50Hz
            'ultrasonic_front': 2.0,     # 초음파는 느림
            'ultrasonic_left': 2.0,
            'ultrasonic_right': 2.0,
        }
        # 부팅 직후 false positive 방지용 grace time
        self.start_time = self.get_clock().now()
        self.startup_grace_sec = 5.0

        # ===== 구독 =====
        # 명령 토픽
        self.create_subscription(Twist, '/cmd_vel_nav', self.nav_cmd_callback, 10)

        # 초음파 (RELIABLE QoS, 일반 publisher와 매칭)
        self.create_subscription(Range, '/ultrasonic/range', self.front_callback, 10)
        self.create_subscription(Range, '/ultrasonic/left', self.left_callback, 10)
        self.create_subscription(Range, '/ultrasonic/right', self.right_callback, 10)

        # ⭐ 라이다·IMU는 sensor_data QoS 사용 (BEST_EFFORT, 드라이버와 매칭됨)
        self.create_subscription(LaserScan, '/scan', self.lidar_callback, qos_profile_sensor_data)
        self.create_subscription(Imu, '/imu/data', self.imu_callback, qos_profile_sensor_data)

        # 오도메트리 (RELIABLE)
        self.create_subscription(Odometry, '/odom', self.odom_callback, 10)

        # ⭐ 외부 비상 신호 — IMU와 Localization으로 분리
        self.create_subscription(
            Bool, '/emergency_stop/imu', self.imu_emergency_cb, 10)
        self.create_subscription(
            Bool, '/emergency_stop/localization', self.localization_emergency_cb, 10)

        # ===== 발행 =====
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel_safe', 10)
        self.zone_pub = self.create_publisher(String, '/current_zone', 10)
        self.avoid_pub = self.create_publisher(String, '/avoidance_direction', 10)
        self.alert_pub = self.create_publisher(String, '/safety_alert', 10)
        self.action_pub = self.create_publisher(String, '/safety_action', 10)
        self.health_pub = self.create_publisher(String, '/sensor_health', 10)

        # ===== 타이머 =====
        self.create_timer(1.0, self.publish_zone)
        self.create_timer(0.1, self.check_danger_state)
        self.create_timer(0.5, self.check_sensor_health)

        self.get_logger().info(
            f'Safety Stop Node 시작 | 전방 정지: {self.danger_distance_m*100:.0f}cm | '
            f'헬스체크 활성화 (라이다/IMU/초음파/모터)')

    # ============================================================
    #  센서 위험 상태 갱신
    # ============================================================
    
    def imu_emergency_cb(self, msg: Bool):
        self.set_reason('imu_emergency', msg.data)

    def localization_emergency_cb(self, msg: Bool):
        self.set_reason('localization_emergency', msg.data)
    
    def set_reason(self, key, active):
        """센서 위험 상태 변경 시 엣지 트리거 로그 (같은 상태면 로그 안 찍힘)"""
        prev = self.sensor_danger.get(key, False)
        if prev == active:
            return

        # 1) 상태 갱신
        self.sensor_danger[key] = active
        # 2) 파생 변수 즉시 갱신
        self.dangerous_sensors = [k for k, v in self.sensor_danger.items() if v]
        self.is_emergency = any(self.sensor_danger.values())

        # 3) 로그
        if active:
            self.get_logger().error(f'🛑 [{key}] 위험 상태 → 위험 센서: {self.dangerous_sensors}')
        else:
            if self.dangerous_sensors:
                self.get_logger().warn(f'✅ [{key}] 정상 복귀 → 남은 위험 센서: {self.dangerous_sensors}')
            else:
                self.get_logger().info(f'✅ [{key}] 정상 복귀 → 모든 센서 정상')

    #  센서 콜백 (마지막 수신 시각 기록)
    def lidar_callback(self, msg: LaserScan):
        self.last_seen['lidar'] = self.get_clock().now()

    def imu_callback(self, msg: Imu):
        self.last_seen['imu'] = self.get_clock().now()

    def odom_callback(self, msg: Odometry):
        self.last_seen['odom'] = self.get_clock().now()

    def front_callback(self, msg: Range):
        self.dist_front = msg.range
        self.last_seen['ultrasonic_front'] = self.get_clock().now()

    def left_callback(self, msg: Range):
        self.dist_left = msg.range
        self.last_seen['ultrasonic_left'] = self.get_clock().now()

    def right_callback(self, msg: Range):
        self.dist_right = msg.range
        self.last_seen['ultrasonic_right'] = self.get_clock().now()

    #  센서 헬스 체크 (0.5초마다)
    def check_sensor_health(self):
        now = self.get_clock().now()

        # 부팅 직후 grace 시간 동안은 체크 스킵
        if (now - self.start_time).nanoseconds / 1e9 < self.startup_grace_sec:
            return

        groups = {
            'lidar_lost': ['lidar'],
            'imu_lost': ['imu'],
            'odom_lost': ['odom'],
            'ultrasonic_lost': ['ultrasonic_front', 'ultrasonic_left', 'ultrasonic_right'],
        }

        health_status = {}
        for danger_key, sensor_keys in groups.items():
            any_lost = False
            for sk in sensor_keys:
                last = self.last_seen[sk]
                timeout = self.timeout_sec[sk]
                if last is None:
                    health_status[sk] = 'never'
                    any_lost = True
                else:
                    elapsed = (now - last).nanoseconds / 1e9
                    if elapsed > timeout:
                        health_status[sk] = f'lost({elapsed:.1f}s)'
                        any_lost = True
                    else:
                        health_status[sk] = 'ok'

            self.set_reason(danger_key, any_lost)

        msg = String()
        msg.data = json.dumps(health_status, ensure_ascii=False)
        self.health_pub.publish(msg)

    #  Cmd Vel 게이트웨이
    def nav_cmd_callback(self, msg: Twist):
        self.process_and_publish(msg, "Navigation")

    def process_and_publish(self, msg, source):
        """모든 cmd_vel이 거쳐가는 단일 안전 게이트웨이"""

        # 1) 비상 정지
        if self.is_emergency:
            self.cmd_pub.publish(Twist())
            self.publish_action(source, 'blocked', ','.join(self.dangerous_sensors))
            return

        # 2) 초음파 전방 장애물
        safe_msg = Twist()
        safe_msg.linear = msg.linear
        safe_msg.angular = msg.angular

        if msg.linear.x > 0.0 and self.dist_front <= self.danger_distance_m:
            safe_msg.linear.x = 0.0
            self.cmd_pub.publish(safe_msg)
            self.publish_action(source, 'modified', 'obstacle_front')
            return

        # 3) 정상 통과
        self.cmd_pub.publish(safe_msg)
        self.publish_action(source, 'allowed', '')

    def publish_action(self, source, action, reason):
        msg = String()
        msg.data = json.dumps({
            'source': source,
            'action': action,
            'reason': reason,
        }, ensure_ascii=False)
        self.action_pub.publish(msg)

    #  회피 방향 결정
    def check_danger_state(self):
        in_danger_now = self.dist_front <= self.danger_distance_m

        if in_danger_now and not self.was_in_danger:
            direction = self.decide_avoidance()
            self.get_logger().error(
                f'⚠️ 전방 장애물 진입! F:{self.dist_front*100:.1f}cm '
                f'L:{self.dist_left*100:.1f}cm R:{self.dist_right*100:.1f}cm '
                f'권장 회피: {direction}')
            self.alert_pub.publish(String(data='obstacle_too_close'))
            self.avoid_pub.publish(String(data=direction))
        elif not in_danger_now and self.was_in_danger:
            self.get_logger().info(f'✅ 전방 장애물 해소. F:{self.dist_front*100:.1f}cm')
            self.alert_pub.publish(String(data='obstacle_cleared'))

        self.was_in_danger = in_danger_now

    def decide_avoidance(self):
        if self.dist_left < self.clearance_min_m and \
           self.dist_right < self.clearance_min_m:
            return 'blocked'
        if self.dist_left > self.dist_right:
            return 'left'
        elif self.dist_right > self.dist_left:
            return 'right'
        else:
            return 'left'

    def publish_zone(self):
        zone_msg = String()
        if self.is_emergency:
            zone_msg.data = f'비상정지 | 위험 센서: {",".join(self.dangerous_sensors)}'
        elif self.dist_front <= self.danger_distance_m:
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