#!/usr/bin/env python3
"""
시나리오 러너 (Scenario Runner) — 풀버전
==========================================
프로젝트 전체 안전/UI 시나리오를 터미널 메뉴로 트리거.
fake 환경에서 풀스택을 띄운 뒤 별도 터미널에서 실행한다.

사용:
  ros2 run wheelchair_robot_fake scenario_runner

전제:
  fake_ultrasonic_node, fake_lidar_node, fake_imu_node가 떠 있어야
  관련 시나리오가 동작. fake_navigation.launch.py 실행하면 자동 포함.
"""
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, Empty, String
from std_srvs.srv import Empty as EmptySrv


# (key, label, group)  group: 헤더 표시용
SCENARIOS = [
    ('--HDR--', '🔊 초음파 센서', None),
    ('1',  '전방 초음파 → 위험거리 (장애물 감지)', 'ultra'),
    ('2',  '좌측 초음파 → 위험거리', 'ultra'),
    ('3',  '우측 초음파 → 위험거리', 'ultra'),
    ('4',  '전방 초음파 → 끊김 (sensor_lost)', 'ultra'),
    ('5',  '좌측 초음파 → 끊김', 'ultra'),
    ('6',  '우측 초음파 → 끊김', 'ultra'),
    ('7',  '모든 초음파 정상 복귀', 'ultra'),

    ('--HDR--', '📡 LiDAR', None),
    ('10', 'LiDAR 전방 장애물 강제 (전방 ±15° = 0.3m)', 'lidar'),
    ('11', 'LiDAR 후방 장애물 강제 (후진 시 정지 테스트)', 'lidar'),
    ('12', 'LiDAR 장애물 해제', 'lidar'),
    ('13', 'LiDAR 발행 중단 (sensor_lost)', 'lidar'),
    ('14', 'LiDAR 발행 재개', 'lidar'),
    ('15', '위치 점프 (AMCL 분실 유도)', 'lidar'),
    ('16', 'LiDAR 전체 리셋', 'lidar'),

    ('--HDR--', '🎯 IMU', None),
    ('20', 'IMU 충격 시뮬 (3초간 큰 가속도)', 'imu'),
    ('21', 'IMU 기울기 시뮬 (pitch 30°, roll 20°)', 'imu'),
    ('22', 'IMU shock/tilt 해제', 'imu'),
    ('23', 'IMU 발행 중단', 'imu'),
    ('24', 'IMU 발행 재개', 'imu'),
    ('25', 'IMU 전체 리셋', 'imu'),

    ('--HDR--', '🗺️ 위치추정 & Nav2', None),
    ('30', 'AMCL 글로벌 재인식 요청', 'amcl'),
    ('31', '키포아웃 영역 좌표로 점프 (keepout 위반)', 'nav'),
    ('32', '서행구역 좌표로 점프 (감속 확인)', 'nav'),
    ('33', 'Nav2 goal 취소', 'nav'),

    ('--HDR--', '🆘 안전 액션', None),
    ('40', 'SOS 트리거 (/sos_trigger)', 'safety'),
    ('41', '비상정지 (/emergency_stop/manual)', 'safety'),
    ('42', '사용자 정지 (/user_stop)', 'safety'),
    ('43', 'safety_alert: obstacle_too_close 발행', 'safety'),
    ('44', 'safety_alert: keepout_violation 발행', 'safety'),
    ('45', 'safety_alert: imu_emergency 발행', 'safety'),
    ('46', 'safety_alert: localization_lost 발행', 'safety'),

    ('--HDR--', '🎮 UI / 명령', None),
    ('50', '목적지 → room_101', 'ui'),
    ('51', '목적지 → room_102', 'ui'),
    ('52', '목적지 → emergency', 'ui'),
    ('53', '홈 귀환 (/go_home)', 'ui'),
    ('54', '모드 토글 (/mode_switch)', 'ui'),

    ('--HDR--', '🔁 종합', None),
    ('90', '모든 fake 노드 정상 복귀 (전체 리셋)', 'reset'),
    ('0',  '종료', 'exit'),
]


# Keepout / Speed 영역 좌표는 프로젝트 mask와 다를 수 있으니 적절히 조정
KEEPOUT_ZONE_POSE = (3.5, 2.5, 0.0)   # x, y, yaw
SPEED_ZONE_POSE = (-0.5, 0.5, 0.0)


class ScenarioRunner(Node):
    def __init__(self):
        super().__init__('scenario_runner')

        # 제어 토픽
        self.ultra_ctrl_pub = self.create_publisher(String, '/fake/ultrasonic_control', 10)
        self.lidar_ctrl_pub = self.create_publisher(String, '/fake/lidar_control', 10)
        self.imu_ctrl_pub = self.create_publisher(String, '/fake/imu_control', 10)

        # 안전 / UI 토픽
        self.sos_pub = self.create_publisher(String, '/sos_trigger', 10)
        self.emergency_pub = self.create_publisher(Bool, '/emergency_stop/manual', 10)
        self.user_stop_pub = self.create_publisher(Bool, '/user_stop', 10)
        self.safety_alert_pub = self.create_publisher(String, '/safety_alert', 10)
        self.destination_pub = self.create_publisher(String, '/destination', 10)
        self.go_home_pub = self.create_publisher(Empty, '/go_home', 10)
        self.mode_switch_pub = self.create_publisher(Empty, '/mode_switch', 10)

        # initialpose (텔레포트용)
        from geometry_msgs.msg import PoseWithCovarianceStamped
        self.initialpose_pub = self.create_publisher(
            PoseWithCovarianceStamped, '/initialpose', 10)

        # AMCL 재인식 서비스
        self.relocalize_client = self.create_client(
            EmptySrv, '/reinitialize_global_localization')

        # Nav2 goal 취소 (action cancel은 service로 노출)
        # /navigate_to_pose/_action/cancel_goal은 action_msgs/CancelGoal 서비스
        try:
            from action_msgs.srv import CancelGoal
            self.cancel_goal_client = self.create_client(
                CancelGoal, '/navigate_to_pose/_action/cancel_goal')
        except ImportError:
            self.cancel_goal_client = None

        time.sleep(0.5)
        self.get_logger().info('Scenario Runner ready')

    # ── 헬퍼 ───────────────────────────────────────────────
    def _pub_str(self, pub, topic, data):
        m = String(); m.data = data
        pub.publish(m)
        print(f'  ✓ {topic}: "{data}"')

    def _pub_bool(self, pub, topic, data):
        m = Bool(); m.data = data
        pub.publish(m)
        print(f'  ✓ {topic}: {data}')

    def _pub_empty(self, pub, topic):
        pub.publish(Empty())
        print(f'  ✓ {topic}')

    def _teleport(self, x, y, yaw, label):
        # fake_lidar는 자체 텔레포트 토픽이 없어 lidar_control "teleport"는 1.5m 가까운 점프만.
        # 정확한 좌표로 점프하려면 /initialpose 발행으로 AMCL을 강제 정렬.
        # 단, fake_lidar의 실제 위치는 그대로라 raycasting과 AMCL 위치가 어긋남 → 분실 유도됨.
        import math
        from geometry_msgs.msg import PoseWithCovarianceStamped
        msg = PoseWithCovarianceStamped()
        msg.header.frame_id = 'map'
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.pose.pose.position.x = float(x)
        msg.pose.pose.position.y = float(y)
        msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
        msg.pose.pose.orientation.w = math.cos(yaw / 2.0)
        msg.pose.covariance = [
            0.25, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.25, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.068,
        ]
        self.initialpose_pub.publish(msg)
        print(f'  ✓ /initialpose → {label}: ({x}, {y}, yaw={yaw})')

    def _call_relocalize(self):
        if not self.relocalize_client.wait_for_service(timeout_sec=1.0):
            print('  ❌ /reinitialize_global_localization 응답 없음')
            return
        self.relocalize_client.call_async(EmptySrv.Request())
        print('  ✓ AMCL 파티클 재분포 요청 전송')

    def _cancel_nav_goal(self):
        if self.cancel_goal_client is None:
            print('  ❌ action_msgs.srv.CancelGoal import 실패')
            return
        if not self.cancel_goal_client.wait_for_service(timeout_sec=1.0):
            print('  ❌ /navigate_to_pose/_action/cancel_goal 응답 없음')
            return
        from action_msgs.srv import CancelGoal
        req = CancelGoal.Request()  # 빈 요청 = 모든 goal 취소
        self.cancel_goal_client.call_async(req)
        print('  ✓ Nav2 goal 전체 취소 요청 전송')

    # ── 시나리오 실행 ──────────────────────────────────────
    def run_scenario(self, key):
        # 초음파
        if key == '1': self._pub_str(self.ultra_ctrl_pub, '/fake/ultrasonic_control', 'front_close')
        elif key == '2': self._pub_str(self.ultra_ctrl_pub, '/fake/ultrasonic_control', 'left_close')
        elif key == '3': self._pub_str(self.ultra_ctrl_pub, '/fake/ultrasonic_control', 'right_close')
        elif key == '4': self._pub_str(self.ultra_ctrl_pub, '/fake/ultrasonic_control', 'front_lost')
        elif key == '5': self._pub_str(self.ultra_ctrl_pub, '/fake/ultrasonic_control', 'left_lost')
        elif key == '6': self._pub_str(self.ultra_ctrl_pub, '/fake/ultrasonic_control', 'right_lost')
        elif key == '7': self._pub_str(self.ultra_ctrl_pub, '/fake/ultrasonic_control', 'reset')

        # LiDAR
        elif key == '10': self._pub_str(self.lidar_ctrl_pub, '/fake/lidar_control', 'obstacle_front')
        elif key == '11': self._pub_str(self.lidar_ctrl_pub, '/fake/lidar_control', 'obstacle_back')
        elif key == '12': self._pub_str(self.lidar_ctrl_pub, '/fake/lidar_control', 'clear_obstacle')
        elif key == '13': self._pub_str(self.lidar_ctrl_pub, '/fake/lidar_control', 'lost')
        elif key == '14': self._pub_str(self.lidar_ctrl_pub, '/fake/lidar_control', 'restore')
        elif key == '15': self._pub_str(self.lidar_ctrl_pub, '/fake/lidar_control', 'teleport')
        elif key == '16': self._pub_str(self.lidar_ctrl_pub, '/fake/lidar_control', 'reset')

        # IMU
        elif key == '20': self._pub_str(self.imu_ctrl_pub, '/fake/imu_control', 'shock')
        elif key == '21': self._pub_str(self.imu_ctrl_pub, '/fake/imu_control', 'tilt')
        elif key == '22': self._pub_str(self.imu_ctrl_pub, '/fake/imu_control', 'clear')
        elif key == '23': self._pub_str(self.imu_ctrl_pub, '/fake/imu_control', 'lost')
        elif key == '24': self._pub_str(self.imu_ctrl_pub, '/fake/imu_control', 'restore')
        elif key == '25': self._pub_str(self.imu_ctrl_pub, '/fake/imu_control', 'reset')

        # AMCL / Nav2
        elif key == '30': self._call_relocalize()
        elif key == '31': self._teleport(*KEEPOUT_ZONE_POSE, 'keepout zone')
        elif key == '32': self._teleport(*SPEED_ZONE_POSE, 'speed zone')
        elif key == '33': self._cancel_nav_goal()

        # 안전 액션
        elif key == '40': self._pub_str(self.sos_pub, '/sos_trigger', 'sos')
        elif key == '41': self._pub_bool(self.emergency_pub, '/emergency_stop/manual', True)
        elif key == '42': self._pub_bool(self.user_stop_pub, '/user_stop', True)
        elif key == '43': self._pub_str(self.safety_alert_pub, '/safety_alert', 'obstacle_too_close')
        elif key == '44': self._pub_str(self.safety_alert_pub, '/safety_alert', 'keepout_violation')
        elif key == '45': self._pub_str(self.safety_alert_pub, '/safety_alert', 'imu_emergency')
        elif key == '46': self._pub_str(self.safety_alert_pub, '/safety_alert', 'localization_lost')

        # UI
        elif key == '50': self._pub_str(self.destination_pub, '/destination', 'room_101')
        elif key == '51': self._pub_str(self.destination_pub, '/destination', 'room_102')
        elif key == '52': self._pub_str(self.destination_pub, '/destination', 'emergency')
        elif key == '53': self._pub_empty(self.go_home_pub, '/go_home')
        elif key == '54': self._pub_empty(self.mode_switch_pub, '/mode_switch')

        # 전체 리셋
        elif key == '90':
            print('  → 전체 리셋 시퀀스 실행')
            self._pub_str(self.ultra_ctrl_pub, '/fake/ultrasonic_control', 'reset')
            self._pub_str(self.lidar_ctrl_pub, '/fake/lidar_control', 'reset')
            self._pub_str(self.imu_ctrl_pub, '/fake/imu_control', 'reset')
            self._pub_str(self.safety_alert_pub, '/safety_alert', 'ok')
            print('  ✓ 모든 fake 노드 정상 복귀')

        else:
            print(f'  ❌ 잘못된 번호: {key}')

    # ── 메뉴 루프 ─────────────────────────────────────────
    def menu_loop(self):
        while rclpy.ok():
            print()
            print('=' * 64)
            print('  🚦 Scenario Runner — 시나리오 번호 선택')
            print('=' * 64)
            for key, label, group in SCENARIOS:
                if key == '--HDR--':
                    print()
                    print(f'  ── {label} ──')
                else:
                    print(f'  [{key:>2}] {label}')
            print('=' * 64)

            try:
                choice = input('번호 입력 (0=종료): ').strip()
            except (EOFError, KeyboardInterrupt):
                print('\n종료합니다.')
                break

            if not choice:
                continue
            if choice == '0':
                print('종료합니다.')
                break

            self.run_scenario(choice)


def main():
    rclpy.init()
    node = ScenarioRunner()
    try:
        node.menu_loop()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
