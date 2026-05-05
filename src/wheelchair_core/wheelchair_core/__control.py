#!/usr/bin/env python3
"""
docking_control_node.py (Gazebo 버전)
─────────────────────────────────────────────────────────────────
TurtleBot3 Waffle Pi용 5단계 후진 직각 주차 제어
- EKF 센서 퓨전 적용 (/odometry/filtered 구독)
- LiDAR 스캔 처리로 전방 거리 계산 (/scan 토픽)
- 마커 정중앙 인식 시 10프레임 평균 보정 적용
"""
import math
from enum import Enum
from collections import deque

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, PointStamped
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan


# ── 상태 정의 ─────────────────────────────────────────────────
class State(Enum):
    SEARCHING     = 'SEARCHING'
    TURN_LATERAL  = 'TURN_LATERAL'
    DRIVE_LATERAL = 'DRIVE_LATERAL'
    TURN_REVERSE  = 'TURN_REVERSE'
    DRIVE_BACK    = 'DRIVE_BACK'
    COMPLETE      = 'COMPLETE'


class DockingControlNode(Node):
    def __init__(self):
        super().__init__('docking_control_node')

        # ── 제어 설정값 (TurtleBot3 Waffle Pi 튜닝) ──────────
        self.drive_speed       = 0.08   # 전진/후진 속도 (m/s) - 낮춤
        self.turn_speed_max    = 0.25   # 회전 최대 각속도 (rad/s)
        self.turn_kp           = 1.5    # 회전 보정 게인
        self.steer_kp          = 0.8    # 직진 조향 보정 게인
        self.goal_dist_thresh  = 0.05   # 도달 판정 거리 (m)
        self.turn_angle_thresh = 0.05   # 도달 판정 각도 (rad, ~2.9도)
        self.lidar_stop_dist   = 0.25   # LiDAR 긴급 정지 거리 (m)

        # ── 상태 변수 ─────────────────────────────────────────
        self.state    = State.SEARCHING
        self.odom_x   = 0.0
        self.odom_y   = 0.0
        self.odom_yaw = 0.0
        self.front_dist = 999.0  # 전방 장애물 거리

        self.goal_x    = 0.0
        self.goal_y    = 0.0
        self.base_yaw  = 0.0   # 벽 정면 방향
        self.lat_yaw   = 0.0   # 측면 이동 방향
        
        self.is_gathering = False
        self.lock_count   = 0
        self.tag_cam_x    = 0.0
        
        self.debug_count  = 0  # 디버그 로그 출력 횟수

        self.tag_world_x = 0.0
        self.tag_world_y = 0.0
        self.fwd_world_x = 0.0
        self.fwd_world_y = 0.0
        
        self.sum_goal_x  = 0.0
        self.sum_goal_y  = 0.0
        self.sum_tag_x   = 0.0
        self.sum_tag_y   = 0.0
        self.sum_fwd_x   = 0.0
        self.sum_fwd_y   = 0.0

        self.got_tag       = False
        self.got_fwd       = False
        self.target_locked = False
        
        # LiDAR 전방 거리 버퍼 (이동평균)
        self.lidar_buffer = deque(maxlen=5)

        # ── 구독 ──────────────────────────────────────────────
        self.create_subscription(Odometry,     '/odom',                self._odom_cb,   10)
        self.create_subscription(PointStamped, '/tag/raw_tag',        self._tag_cb,    10)
        self.create_subscription(PointStamped, '/tag/forward_dir',    self._fwd_cb,    10)
        self.create_subscription(PointStamped, '/tag/parking_target', self._target_cb, 10)
        self.create_subscription(LaserScan,    '/scan',               self._scan_cb,   10)

        # ── 발행 ──────────────────────────────────────────────
        self._pub_vel = self.create_publisher(Twist, '/cmd_vel', 10)

        # ── 타이머 (10 Hz) ────────────────────────────────────
        self.create_timer(0.1, self._loop)

        self.get_logger().info('🤖 DockingControlNode: TurtleBot3 Waffle Pi 준비 완료!')

    # ── 센서 콜백 ──────────────────────────────────────────────
    def _scan_cb(self, msg: LaserScan):
        """LiDAR 스캔에서 전방 거리 추출 (중앙 70도 범위)"""
        if not msg.ranges:
            return
        
        # 전방 방향 (0도) 주변 70도 범위의 거리값 수집
        ranges = msg.ranges
        center_idx = len(ranges) // 2
        angle_range = int(70 / 2 * len(ranges) / 360.0)  # 70도를 인덱스로 변환
        
        front_ranges = []
        for i in range(max(0, center_idx - angle_range), 
                      min(len(ranges), center_idx + angle_range)):
            r = ranges[i]
            if msg.range_min <= r <= msg.range_max:
                front_ranges.append(r)
        
        if front_ranges:
            self.front_dist = sum(front_ranges) / len(front_ranges)

    def _odom_cb(self, msg: Odometry):
        """EKF 필터링된 odometry 수신"""
        self.odom_x = msg.pose.pose.position.x
        self.odom_y = msg.pose.pose.position.y
        q = msg.pose.pose.orientation
        self.odom_yaw = math.atan2(
            2.0 * (q.w * q.z + q.x * q.y),
            1.0 - 2.0 * (q.y * q.y + q.z * q.z))

    # ── 핵심: 카메라 좌표 → 월드 좌표 변환 ──────────────────────
    def _cam_to_world(self, cam_z: float, cam_x: float):
        bx =  cam_z   # 카메라 Z → 로봇 전방
        by = -cam_x   # 카메라 X → 로봇 좌측
        wx = self.odom_x + bx * math.cos(self.odom_yaw) - by * math.sin(self.odom_yaw)
        wy = self.odom_y + bx * math.sin(self.odom_yaw) + by * math.cos(self.odom_yaw)
        return wx, wy

    def _tag_cb(self, msg: PointStamped):
        self.tag_cam_x = msg.point.x 
        self.tag_world_x, self.tag_world_y = self._cam_to_world(msg.point.z, msg.point.x)
        self.got_tag = True

    def _fwd_cb(self, msg: PointStamped):
        self.fwd_world_x, self.fwd_world_y = self._cam_to_world(msg.point.z, msg.point.x)
        self.got_fwd = True

    def _target_cb(self, msg: PointStamped):
        if self.target_locked:
            return

        gx, gy = self._cam_to_world(msg.point.z, msg.point.x)

        if self.got_tag and self.got_fwd:
            # 1. 마커가 정중앙인지 확인 (화면상 ±15cm)
            if not self.is_gathering:
                if abs(self.tag_cam_x) < 0.15: 
                    self.is_gathering = True
                    self._pub(0.0, 0.0)
                    self.get_logger().info('📸 마커 정면 포착! 로봇 정지 후 데이터 수집...')
                else:
                    return

            # 2. 10프레임 데이터 누적
            self.lock_count += 1
            self.sum_goal_x += gx
            self.sum_goal_y += gy
            self.sum_tag_x  += self.tag_world_x
            self.sum_tag_y  += self.tag_world_y
            self.sum_fwd_x  += self.fwd_world_x
            self.sum_fwd_y  += self.fwd_world_y

            # 3. 평균 계산 및 목표 각도 설정
            if self.lock_count >= 10:
                self.goal_x = self.sum_goal_x / 10.0
                self.goal_y = self.sum_goal_y / 10.0
                avg_tag_x   = self.sum_tag_x / 10.0
                avg_tag_y   = self.sum_tag_y / 10.0
                avg_fwd_x   = self.sum_fwd_x / 10.0
                avg_fwd_y   = self.sum_fwd_y / 10.0

                # 벽면 각도 도출
                marker_yaw = math.atan2(avg_fwd_y - avg_tag_y, avg_fwd_x - avg_tag_x)
                self.base_yaw = self._norm(marker_yaw + math.pi)

                dx = self.goal_x - avg_tag_x
                dy = self.goal_y - avg_tag_y
                target_angle = math.atan2(dy, dx)
                diff = self._norm(target_angle - marker_yaw)

                if diff > 0:
                    self.lat_yaw = self._norm(self.base_yaw + math.pi / 2.0)
                else:
                    self.lat_yaw = self._norm(self.base_yaw - math.pi / 2.0)

                self.target_locked = True
                self.get_logger().info(
                    f'✅ 목표 잠금 완료!')
                self.get_logger().info(
                    f'   마커(avg): ({avg_tag_x:.3f}, {avg_tag_y:.3f})')
                self.get_logger().info(
                    f'   목표(avg): ({self.goal_x:.3f}, {self.goal_y:.3f})')
                self.get_logger().info(
                    f'   marker_yaw: {math.degrees(marker_yaw):.1f}°')
                self.get_logger().info(
                    f'   base_yaw: {math.degrees(self.base_yaw):.1f}°')
                self.get_logger().info(
                    f'   lat_yaw: {math.degrees(self.lat_yaw):.1f}°')

    # ── 메인 제어 루프 (10 Hz) ────────────────────────────────
    def _loop(self):
        if self.state == State.COMPLETE:
            return

        # 🚨 LiDAR 긴급 정지
        if self.front_dist < self.lidar_stop_dist:
            self._pub(0.0, 0.0)
            self.get_logger().warn(
                f'⚠️ 전방 장애물 감지! ({self.front_dist:.2f}m) 긴급 정지',
                throttle_duration_sec=2.0)
            return

        # ── 0. 태그 탐색 ──────────────────────────────────────
        if self.state == State.SEARCHING:
            if not self.target_locked:
                if getattr(self, 'is_gathering', False):
                    self._pub(0.0, 0.0)
                else:
                    self._pub(0.0, 0.20)
            else:
                self.get_logger().info('🎯 목표 확인! 측면 회전 시작')
                self.state = State.TURN_LATERAL

        # ── 1. 측면 방향 회전 ─────────────────────────────────
        elif self.state == State.TURN_LATERAL:
            err = abs(self._norm(self.lat_yaw - self.odom_yaw))
            self.get_logger().info(
                f'🔄 [1/4] 측면 회전... {math.degrees(err):.1f}°',
                throttle_duration_sec=0.5)

            if self._turn_to(self.lat_yaw, self.turn_speed_max, self.turn_kp, self.turn_angle_thresh):
                self.get_logger().info('✅ [1/4] 측면 정렬 완료')
                self.state = State.DRIVE_LATERAL

        # ── 2. 측면 직진 ──────────────────────────────────────
        elif self.state == State.DRIVE_LATERAL:
            err_lat = (
                -(self.goal_x - self.odom_x) * math.sin(self.base_yaw)
                +(self.goal_y - self.odom_y) * math.cos(self.base_yaw)
            )
            
            # 🔍 디버그 정보 (처음 3번만 출력)
            if self.debug_count < 3:
                self.get_logger().info(
                    f'🔍 [측면 직진 디버그]')
                self.get_logger().info(
                    f'   현재 위치: ({self.odom_x:.3f}, {self.odom_y:.3f})')
                self.get_logger().info(
                    f'   목표 위치: ({self.goal_x:.3f}, {self.goal_y:.3f})')
                self.get_logger().info(
                    f'   base_yaw: {math.degrees(self.base_yaw):.1f}°')
                self.get_logger().info(
                    f'   lat_yaw: {math.degrees(self.lat_yaw):.1f}°')
                self.get_logger().info(
                    f'   측면 오차(err_lat): {err_lat:.3f}m')
                self.debug_count += 1
            
            self.get_logger().info(
                f'➡️ [2/4] 측면 직진... {err_lat:.3f}m',
                throttle_duration_sec=0.3)

            if abs(err_lat) < self.goal_dist_thresh:
                self._pub(0.0, 0.0)
                self.get_logger().info('✅ [2/4] 측면 이동 완료')
                self.state = State.TURN_REVERSE
            else:
                self._drive_straight(self.lat_yaw, self.drive_speed, self.steer_kp)

        # ── 3. 후진 준비 회전 ─────────────────────────────────
        elif self.state == State.TURN_REVERSE:
            rev_yaw = self._norm(self.base_yaw + math.pi)
            err = abs(self._norm(rev_yaw - self.odom_yaw))
            self.get_logger().info(
                f'🔄 [3/4] 후진 준비... {math.degrees(err):.1f}°',
                throttle_duration_sec=0.5)

            if self._turn_to(rev_yaw, self.turn_speed_max, self.turn_kp, self.turn_angle_thresh):
                self.get_logger().info('✅ [3/4] 후진 자세 완료')
                self.state = State.DRIVE_BACK

        # ── 4. 후진 ───────────────────────────────────────────
        elif self.state == State.DRIVE_BACK:
            err_fwd = (
                (self.goal_x - self.odom_x) * math.cos(self.base_yaw)
               +(self.goal_y - self.odom_y) * math.sin(self.base_yaw)
            )
            self.get_logger().info(
                f'⬅️ [4/4] 후진중... {err_fwd:.3f}m',
                throttle_duration_sec=0.3)

            if abs(err_fwd) < self.goal_dist_thresh:
                self._pub(0.0, 0.0)
                self.get_logger().info('🏁 주차 성공!')
                self.state = State.COMPLETE
            else:
                rev_yaw = self._norm(self.base_yaw + math.pi)
                self._drive_straight(rev_yaw, -self.drive_speed, self.steer_kp)

    # ── 유틸 함수 ──────────────────────────────────────────────
    @staticmethod
    def _norm(angle: float) -> float:
        """각도를 -π ~ π 범위로 정규화"""
        return math.atan2(math.sin(angle), math.cos(angle))

    def _turn_to(self, target_yaw: float, speed_max: float, kp: float, thresh: float) -> bool:
        err = self._norm(target_yaw - self.odom_yaw)
        if abs(err) < thresh:
            self._pub(0.0, 0.0)
            return True
        ang = max(-speed_max, min(speed_max, err * kp))
        self._pub(0.0, ang)
        return False

    def _drive_straight(self, target_yaw: float, speed: float, kp: float):
        err = self._norm(target_yaw - self.odom_yaw)
        ang = max(-0.20, min(0.20, err * kp))
        self._pub(speed, ang)

    def _pub(self, lin: float, ang: float):
        t = Twist()
        t.linear.x  = float(lin)
        t.angular.z = float(ang)
        self._pub_vel.publish(t)


def main(args=None):
    rclpy.init(args=args)
    node = DockingControlNode()
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