#!/usr/bin/env python3
"""
AprilTag 기반 침대 옆 주차 노드 (파란 기둥 / tag_0)
──────────────────────────────────────────────────
주차 위치: 기둥(태그) 오른쪽 옆 (침대 외부)

핵심 원칙: 픽셀 하드코딩 없이, 핀홀 카메라 모델로
           실제 미터 단위 거리·오프셋을 계산해 제어.

상태 흐름:
  SEARCHING → APPROACHING → LATERAL_ALIGN → PARKING → COMPLETE
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan
from apriltag_msgs.msg import AprilTagDetectionArray
import math


# ──────────────────────────────────────────────
# 상태 정의
# ──────────────────────────────────────────────
class State:
    SEARCHING     = 'SEARCHING'      # 태그 탐색 (회전)
    APPROACHING   = 'APPROACHING'    # 태그 방향으로 접근
    LATERAL_ALIGN = 'LATERAL_ALIGN'  # 측면 정렬 (주차 라인 맞추기)
    PARKING       = 'PARKING'        # 최종 진입
    COMPLETE      = 'COMPLETE'       # 완료


# ──────────────────────────────────────────────
# 메인 노드
# ──────────────────────────────────────────────
class PrecisionDockingNode(Node):

    # ── 카메라 파라미터 (실제 카메라에 맞게 조정) ──────────────
    IMAGE_WIDTH  = 640.0   # px
    IMAGE_HEIGHT = 480.0   # px

    # 초점 거리 (px): f = (W/2) / tan(FOV/2)
    # 기본 Gazebo 카메라 FOV ≈ 60° → f ≈ 640/(2*tan(30°)) ≈ 554
    FOCAL_PX = 554.0

    # ── 태그·침대 파라미터 ─────────────────────────────────────
    TAG_REAL_SIZE = 0.15   # 실제 AprilTag 한 변 길이 (m)

    # ── 주차 파라미터 ──────────────────────────────────────────
    # 기둥 중심으로부터 로봇 중심까지의 '측면 이격 거리' (m)
    # 양수 = 카메라 오른쪽 (파란 기둥 기준 침대 외부 방향)
    PARK_LATERAL_OFFSET = 0.35   # 기둥 옆 35 cm

    # 태그까지 도달 목표 깊이 (m): 이 거리에서 '주차 완료'
    PARK_DEPTH_TARGET   = 0.45    #0.45

    # 안전 거리 (라이다 전방)
    LIDAR_STOP_DIST     = 0.22    #0.22

    def __init__(self, target_bed_id: int = 0):
        super().__init__('precision_docking_node')
        self.target_id = target_bed_id
        self.state     = State.SEARCHING

        # ── ROS 인터페이스 ─────────────────────────────────────
        self.pub_vel  = self.create_publisher(Twist, 'cmd_vel', 10)
        self.sub_scan = self.create_subscription(
            LaserScan, '/scan', self._scan_cb, 10)
        self.sub_tag  = self.create_subscription(
            AprilTagDetectionArray, '/detections', self._tag_cb, 10)

        # ── 센서 데이터 ────────────────────────────────────────
        self.front_dist   = 999.0   # 전방 라이다 최소 거리 (m)

        # 태그 검출 결과 (tag_callback 에서 갱신)
        self.tag_found    = False
        self.tag_depth    = 999.0  # 태그까지 추정 깊이 (m)
        self.tag_lat_m    = 0.0    # 태그 중심의 횡방향 위치 (m, 오른쪽 +)

        self.timer = self.create_timer(0.1, self._control_loop)
        self.get_logger().info(
            f'🚀 Docking node ready | target bed ID: {self.target_id}')

    # ──────────────────────────────────────────────────────────
    # 콜백: 라이다
    # ──────────────────────────────────────────────────────────
    def _scan_cb(self, msg: LaserScan):
        """전방 ±15° 범위에서 유효한 최소 거리를 보관."""
        n      = len(msg.ranges)
        arc    = int(math.radians(15) / msg.angle_increment)
        front  = msg.ranges[:arc] + msg.ranges[max(0, n - arc):]
        valid  = [r for r in front if msg.range_min < r < msg.range_max]
        self.front_dist = min(valid) if valid else 999.0

    # ──────────────────────────────────────────────────────────
    # 콜백: AprilTag
    # ──────────────────────────────────────────────────────────
    def _tag_cb(self, msg: AprilTagDetectionArray):
        """
        핀홀 모델로 태그의 깊이(depth)와 횡방향 위치(lateral)를 계산.

        depth   = focal_px * tag_real_size / tag_pixel_width
        lateral = (pixel_error_from_center / focal_px) * depth
                  → 오른쪽이 +, 왼쪽이 -
        """
        self.tag_found = False

        for det in msg.detections:
            if det.id != self.target_id:
                continue

            corners = det.corners
            xs = [c.x for c in corners]

            px_width = max(xs) - min(xs)
            if px_width < 5.0:          # 너무 작으면 신뢰하지 않음
                break

            # 태그 픽셀 중심 (x)
            cx_px = sum(xs) / 4.0

            # ── 핀홀: 깊이 추정 ──────────────────────────────
            self.tag_depth = (self.FOCAL_PX * self.TAG_REAL_SIZE) / px_width

            # ── 핀홀: 횡방향 미터 환산 ──────────────────────
            px_err         = cx_px - (self.IMAGE_WIDTH / 2.0)
            self.tag_lat_m = (px_err / self.FOCAL_PX) * self.tag_depth

            self.tag_found = True
            self.get_logger().debug(
                f'tag depth={self.tag_depth:.2f}m  lat={self.tag_lat_m:.2f}m')
            break

    # ──────────────────────────────────────────────────────────
    # 제어 루프 (10 Hz)
    # ──────────────────────────────────────────────────────────
    def _control_loop(self):
        if self.state == State.COMPLETE:
            return

        # ── 전방 긴급 정지 ────────────────────────────────────
        if self.front_dist < self.LIDAR_STOP_DIST:
            self.get_logger().warn(
                f'⚠️  전방 장애물 {self.front_dist:.2f}m → 긴급 정지')
            self._publish(0.0, 0.0)
            return

        # ── 상태별 처리 ───────────────────────────────────────
        dispatch = {
            State.SEARCHING:     self._state_searching,
            State.APPROACHING:   self._state_approaching,
            State.LATERAL_ALIGN: self._state_lateral_align,
            State.PARKING:       self._state_parking,
        }
        dispatch[self.state]()

    # ──────────────────────────────────────────────────────────
    # 상태: SEARCHING
    # ──────────────────────────────────────────────────────────
    def _state_searching(self):
        if self.tag_found:
            self.get_logger().info('🔍 태그 발견 → APPROACHING')
            self.state = State.APPROACHING
            return
        self._publish(0.0, 0.25)   # 제자리 회전으로 탐색

    # ──────────────────────────────────────────────────────────
    # 상태: APPROACHING
    # 목표: 태그 '앞' 약 1.2 m 지점까지 전진
    # ──────────────────────────────────────────────────────────
    def _state_approaching(self):
        if not self.tag_found:
            self._publish(0.0, 0.15)   # 잠깐 놓쳤으면 느리게 탐색 회전
            return

        # 태그 중심을 화면 중앙에 맞추며 접근
        ang = self._angular_ctrl(target_lat_m=0.0, gain=0.8)
        lin = 0.12 if abs(self.tag_lat_m) < 0.15 else 0.06
        self._publish(lin, ang)

        if self.tag_depth < 1.2:
            self.get_logger().info(
                f'📐 {self.tag_depth:.2f}m 접근 완료 → LATERAL_ALIGN')
            self.state = State.LATERAL_ALIGN

    # ──────────────────────────────────────────────────────────
    # 상태: LATERAL_ALIGN
    # 목표: 로봇을 주차 타겟 측면 위치로 이동
    #
    # 주차 타겟 횡방향 위치 = tag_lat_m + PARK_LATERAL_OFFSET
    # (태그 중심 + 기둥 우측 35 cm)
    # ──────────────────────────────────────────────────────────
    def _state_lateral_align(self):
        if not self.tag_found:
            # 태그가 안 보일 정도로 측면으로 이동한 경우 → PARKING
            if self.tag_depth < 0.9:
                self.get_logger().info('🅿️  사각지대 진입 → PARKING')
                self.state = State.PARKING
            else:
                self._publish(0.0, 0.15)
            return

        # 현재 목표 횡방향 오차 (미터)
        target_lat   = self.tag_lat_m + self.PARK_LATERAL_OFFSET
        lat_err_abs  = abs(target_lat)

        ang = self._angular_ctrl(target_lat_m=(-self.PARK_LATERAL_OFFSET), gain=0.9)

        if lat_err_abs < 0.08:
            # 측면 정렬 완료 → 깊이도 확인
            lin = 0.08
            self.get_logger().info(
                f'✅ 측면 정렬 완료 (err={lat_err_abs:.3f}m) → PARKING')
            self.state = State.PARKING
        else:
            lin = 0.04   # 정렬 중에는 천천히

        self._publish(lin, ang)

    # ──────────────────────────────────────────────────────────
    # 상태: PARKING
    # 목표: 주차 라인을 유지하면서 기둥 옆까지 전진
    # ──────────────────────────────────────────────────────────
    def _state_parking(self):
        # 완료 조건
        if self.tag_found and self.tag_depth < self.PARK_DEPTH_TARGET:
            self._complete()
            return
        if not self.tag_found and self.front_dist < 0.45:
            self._complete()
            return

        if self.tag_found:
            # 주차 라인(오프셋) 유지하면서 전진
            ang = self._angular_ctrl(
                target_lat_m=(-self.PARK_LATERAL_OFFSET), gain=0.6)
            self._publish(0.08, ang)
        else:
            # 태그 사각지대: 직진으로 밀어 넣기
            self._publish(0.08, 0.0)

    # ──────────────────────────────────────────────────────────
    # 완료
    # ──────────────────────────────────────────────────────────
    def _complete(self):
        self._publish(0.0, 0.0)
        self.state = State.COMPLETE
        self.get_logger().info(
            f'🏁 주차 완료! 태그까지 최종 거리: {self.tag_depth:.2f}m')

    # ──────────────────────────────────────────────────────────
    # 헬퍼: 횡방향 오차 → 각속도
    # ──────────────────────────────────────────────────────────
    def _angular_ctrl(self, target_lat_m: float, gain: float = 1.0) -> float:
        """
        target_lat_m: 로봇 전방 축 기준 원하는 태그의 횡방향 위치 (m)
                      0 이면 태그를 정면으로, -OFFSET 이면 기둥 오른쪽 정렬
        """
        # 현재 태그가 있어야 의미 있음
        if not self.tag_found:
            return 0.0

        # 현재 태그 횡방향과 목표의 차이 → 각도 오차
        lat_err = self.tag_lat_m - target_lat_m  # + 면 태그가 오른쪽에 더 있음
        # 오른쪽에 치우쳐 있으면 우회전(angular.z 음수)
        raw = -lat_err * gain
        return float(max(min(raw, 0.40), -0.40))

    # ──────────────────────────────────────────────────────────
    # 헬퍼: 속도 발행
    # ──────────────────────────────────────────────────────────
    def _publish(self, linear: float, angular: float):
        t = Twist()
        t.linear.x  = float(linear)
        t.angular.z = float(angular)
        self.pub_vel.publish(t)


# ──────────────────────────────────────────────
# 엔트리 포인트
# ──────────────────────────────────────────────
def main(args=None):
    rclpy.init(args=args)
    node = PrecisionDockingNode(target_bed_id=0)   # 0 = 파란 기둥
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()