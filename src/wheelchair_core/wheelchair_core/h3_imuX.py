#!/usr/bin/env python3
"""
=============================================================
  휠체어 자율주행 - 초정밀 후진 도킹 통합 노드
  Precision Docking Node (Integrated & Fixed)
=============================================================
  [시나리오 통합]
  - 시나리오 1 : 비전(카메라) 기반 파란색 마커 추적 → 목표 접근
  - 시나리오 2 : 초음파(가상 범퍼) 하이브리드 안전 정지
  - 시나리오 3 : 비전 + 라이다 융합 초정밀 후진 도킹

  [State 흐름]
  State 0  : 카메라로 파란색 기둥 탐색 → 정렬 & 목표 거리 접근
  State 5  : 추가 직진 (Extra Forward) → 기둥 옆에 올바른 위치로 이동
  State 1  : 오도메트리(IMU) 기반 정확한 180도 회전 (타이머 X)
  State 2  : 라이다 수직 칼각 정렬 (미세 보정)
  State 3  : 라이다 거리 피드백 후진 도킹
  State 4  : 주차 완료

  [핵심 수정 사항]
  1. target_cx : 오른쪽(bed_side=1) 진입 방향 수정 (580 → 120)
     - 기둥을 카메라 왼쪽에 두고 접근 → 휠체어가 기둥 오른편에 서서
       180도 회전 후 정확히 침대 방향으로 후진 가능
  2. 가상 방어막(Virtual Bed Zone) : 오른쪽 모드 y 범위 재조정
     - 후진 경로가 방어막에 걸려 State 3 중간에 멈추는 현상 수정
  3. 오도메트리 기반 Closed-loop 180도 회전 (State 1)
     - 타이머 의존 제거 → 바퀴 슬립에 무관하게 정확히 π 라디안 회전
  4. State 5 미세 조향 방향 검토 & 수정
=============================================================
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, LaserScan
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist
from cv_bridge import CvBridge
import cv2
import numpy as np
import math


class PrecisionDockingNode(Node):

    # =========================================================
    #  초기화
    # =========================================================
    def __init__(self):
        super().__init__('precision_docking_node')

        # ── Publisher / Subscriber ──────────────────────────
        self.publisher_ = self.create_publisher(Twist, 'cmd_vel', 10)

        self.image_sub = self.create_subscription(
            Image, '/camera/image_raw',
            self.image_callback, 10)

        self.scan_sub = self.create_subscription(
            LaserScan, '/scan',
            self.scan_callback, 10)

        self.odom_sub = self.create_subscription(
            Odometry, '/odom',
            self.odom_callback, 10)

        self.bridge = CvBridge()

        # ── 로봇 상태 변수 ──────────────────────────────────
        self.state = 0

        # 오도메트리
        self.robot_x   = 0.0
        self.robot_y   = 0.0
        self.current_yaw = 0.0

        # 회전 목표각 (State 1)
        self.target_yaw = 0.0

        # 가상 방어막
        self.virtual_bed_active = False
        self.pillar_x  = 0.0
        self.pillar_y  = 0.0
        self.bed_yaw   = 0.0    # 기둥을 발견했을 때의 로봇 방향
        self.park_side = 0      # 0=왼쪽 침대, 1=오른쪽 침대

        # 추가 직진 (State 5)
        self.start_x = 0.0
        self.start_y = 0.0
        self.extra_fwd_target = 0.0

        # ── OpenCV 튜닝 패널 ────────────────────────────────
        cv2.namedWindow("Tuning Panel", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Tuning Panel", 420, 380)

        # 파란색 HSV 범위
        cv2.createTrackbar("H_min",  "Tuning Panel", 100, 179, self.nothing)
        cv2.createTrackbar("H_max",  "Tuning Panel", 140, 179, self.nothing)
        cv2.createTrackbar("S_min",  "Tuning Panel", 110, 255, self.nothing)
        cv2.createTrackbar("V_min",  "Tuning Panel",   0, 255, self.nothing)

        # 침대 방향 & 목표 거리
        cv2.createTrackbar("Bed_Side(0:L,1:R)",  "Tuning Panel",  1,   1, self.nothing)
        cv2.createTrackbar("Target_Dist(cm)",    "Tuning Panel", 150, 200, self.nothing)

        # 추가 직진 거리 (왼쪽/오른쪽 각각)
        cv2.createTrackbar("Extra_Fwd_L(cm)",    "Tuning Panel",   0, 200, self.nothing)
        cv2.createTrackbar("Extra_Fwd_R(cm)",    "Tuning Panel",  80, 200, self.nothing)

        self.get_logger().info("✅ [통합 도킹 노드] 초기화 완료! 파란색 기둥을 카메라에 보여주세요.")

    # =========================================================
    #  유틸리티
    # =========================================================
    def nothing(self, x):
        pass

    def change_state(self, new_state, msg):
        self.state = new_state
        self.get_logger().info(msg)

    def get_valid_dist(self, ranges, index):
        """라이다 거리값 검증 (inf / nan / 0 → 3.0m 대체)"""
        d = ranges[index]
        return 3.0 if (np.isinf(d) or np.isnan(d) or d == 0.0) else d

    def euler_from_quaternion(self, x, y, z, w):
        """쿼터니언 → Yaw(rad) 변환"""
        t3 = +2.0 * (w * z + x * y)
        t4 = +1.0 - 2.0 * (y * y + z * z)
        return math.atan2(t3, t4)

    def normalize_angle(self, angle):
        """각도를 [-π, π] 범위로 정규화"""
        while angle >  math.pi: angle -= 2 * math.pi
        while angle < -math.pi: angle += 2 * math.pi
        return angle

    # =========================================================
    #  Odom 콜백 : 로봇 실시간 위치 & 방향 갱신
    # =========================================================
    def odom_callback(self, msg):
        self.robot_x = msg.pose.pose.position.x
        self.robot_y = msg.pose.pose.position.y
        q = msg.pose.pose.orientation
        self.current_yaw = self.euler_from_quaternion(q.x, q.y, q.z, q.w)

    # =========================================================
    #  가상 방어막 검사 & 모터 명령 발행
    # =========================================================
    def publish_safe_twist(self, twist):
        """
        가상 방어막(Virtual Bed Zone) 침범 시 강제 정지.
        State 5(추가 직진) 중에는 예외 처리하여 방어막에 걸리지 않게 함.
        """
        if self.virtual_bed_active and self.state != 5:
            # 기둥 좌표계(bed_yaw 기준)로 로봇 위치 변환
            dx = self.robot_x - self.pillar_x
            dy = self.robot_y - self.pillar_y
            local_x =  dx * math.cos(self.bed_yaw) + dy * math.sin(self.bed_yaw)
            local_y = -dx * math.sin(self.bed_yaw) + dy * math.cos(self.bed_yaw)

            # ── 방어막 범위 정의 ──────────────────────────
            # [수정] 오른쪽(park_side=1) 후진 경로가 방어막에 걸리지 않도록
            #        y 범위를 기존보다 5cm 안쪽으로 축소하여 후진 통로 확보
            if self.park_side == 0:   # 왼쪽 침대
                in_x = -0.10 < local_x < 1.60
                in_y = -0.10 < local_y < 0.85
            else:                     # 오른쪽 침대 (수정)
                in_x = -0.25 < local_x < 1.70
                in_y = -0.80 < local_y < 0.15   # ← y_min -0.95→-0.80 / y_max 0.2→0.15

            if in_x and in_y:
                self.get_logger().error(
                    f"🚨 [스마트 방어막] 영역 침범! 긴급 제동! "
                    f"(local_x={local_x:.2f}, local_y={local_y:.2f})")
                twist.linear.x  = 0.0
                twist.angular.z = 0.0

        self.publisher_.publish(twist)

    # =========================================================
    #  Scan(라이다) 콜백 : State 1~5 제어
    # =========================================================
    def scan_callback(self, msg):
        if self.state == 0:
            return

        twist = Twist()

        # ── State 5 : 추가 직진 ───────────────────────────
        if self.state == 5:
            dist_moved = math.hypot(
                self.robot_x - self.start_x,
                self.robot_y - self.start_y)

            self.get_logger().info(
                f"🚀 [추가 직진] 이동: {dist_moved:.2f}m / 목표: {self.extra_fwd_target:.2f}m")

            if dist_moved < self.extra_fwd_target:
                twist.linear.x = 0.15
                # [수정] 오른쪽 침대 : 기둥과 멀어지는 방향(오른쪽)으로 미세 조향
                #        왼쪽 침대  : 기둥과 멀어지는 방향(왼쪽)으로 미세 조향
                twist.angular.z = -0.05 if self.park_side == 1 else 0.05
            else:
                twist.linear.x  = 0.0
                twist.angular.z = 0.0

                # [수정] 왼쪽·오른쪽 모두 왼쪽 주차 지점으로 통일
                #        → 항상 반시계 방향 90도(-π/2) 회전
                self.target_yaw = self.normalize_angle(
                    self.current_yaw - math.pi / 2)

                self.change_state(1, "🔄 [State 1] 목표 지점 도달! 90도 회전 시작!")

        # ── State 1 : 오도메트리 기반 180도 회전 (Closed-loop) ──
        elif self.state == 1:
            yaw_error = self.normalize_angle(self.target_yaw - self.current_yaw)

            if abs(yaw_error) > 0.05:   # 약 3도 이상 오차 → 계속 회전
                twist.angular.z = max(-0.5, min(0.5, yaw_error * 1.5))
            else:                        # 오차 수렴 → 다음 State
                twist.angular.z = 0.0
                self.change_state(2, "📐 [State 2] 라이다 수직 칼각 정렬 시작!")

        # ── State 2 : 라이다 벽면 법선 탐색 정렬 ────────
        # 원리: 후방 120° 호(120°~240°) 전체를 스캔해서
        #       가장 거리가 짧은 인덱스 = 벽과 수직인 방향을 찾고,
        #       그 방향이 정확히 180°(정후방)가 되도록 회전한다.
        #       → 70° 같은 큰 오차도 한 번에 수렴 가능.
        elif self.state == 2:
            # 후방 120° 호에서 유효 거리 수집
            arc_start, arc_end = 120, 241   # 인덱스 120~240
            arc_dists = []
            for i in range(arc_start, arc_end):
                d = self.get_valid_dist(msg.ranges, i)
                arc_dists.append((i, d))

            # 최소 거리 인덱스 = 벽과 가장 수직인 방향
            min_idx, min_dist = min(arc_dists, key=lambda t: t[1])

            # 180°(정후방, 인덱스 180)에서 얼마나 벗어났는지
            # 양수 → 오른쪽으로 치우침(반시계 회전 필요)
            # 음수 → 왼쪽으로 치우침(시계 회전 필요)
            idx_error = min_idx - 180          # 단위: 인덱스(= 도)
            angle_error_rad = math.radians(idx_error)

            # 좌우 대칭 검증: 최소점 ±20° 범위 평균 비교로 2차 보정
            sym_offset = 20
            left_mean  = float(np.mean([
                self.get_valid_dist(msg.ranges, i)
                for i in range(max(arc_start, min_idx - sym_offset),
                               min_idx)]))
            right_mean = float(np.mean([
                self.get_valid_dist(msg.ranges, i)
                for i in range(min_idx + 1,
                               min(arc_end, min_idx + sym_offset + 1))]))
            sym_error = left_mean - right_mean  # 좌우 대칭 오차(m)

            self.get_logger().info(
                f"📐 [벽 정렬] 최소거리 인덱스:{min_idx}° ({min_dist:.3f}m)  "
                f"인덱스 오차:{idx_error}°  "
                f"좌우 대칭 오차:{sym_error:.3f}m")

            # ── 수렴 판단 ─────────────────────────────────
            # 1차: 최소거리 인덱스가 180±3° 이내
            # 2차: 좌우 대칭 오차가 0.01m 이내
            idx_ok = abs(idx_error) <= 3
            sym_ok = abs(sym_error) < 0.015

            if idx_ok and sym_ok:
                self.change_state(3, "🚙 [State 3] 후진 도킹 시작! (벽 수직 정렬 완료)")
            else:
                # 각도 오차(라디안)와 대칭 오차를 혼합하여 조향
                combined_error = angle_error_rad * 0.6 + sym_error * 0.4
                twist.angular.z = max(-0.3, min(0.3, combined_error * 2.0))

        # ── State 3 : 라이다 피드백 후진 도킹 ────────────
        elif self.state == 3:
            dist_180 = self.get_valid_dist(msg.ranges, 180)
            dist_175 = self.get_valid_dist(msg.ranges, 175)
            dist_185 = self.get_valid_dist(msg.ranges, 185)
            error = dist_175 - dist_185

            if dist_180 > 0.8:          # 아직 목표까지 거리 있음 → 후진
                twist.linear.x  = -0.15
                twist.angular.z = max(-0.1, min(0.1, float(error) * 1.5))
            else:                        # 목표 도달
                self.change_state(4, "🎉 [State 4] 주차 완료!!")

        # ── State 4 : 주차 완료 → 정지 ───────────────────
        # (이미 twist=Twist() 이므로 속도 0)

        self.publish_safe_twist(twist)

    # =========================================================
    #  Image 콜백 : State 0 – 비전 기반 마커 탐색 & 접근
    # =========================================================
    def image_callback(self, msg):
        cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")

        # 트랙바 값 읽기
        target_dist_m = cv2.getTrackbarPos("Target_Dist(cm)",   "Tuning Panel") / 100.0
        bed_side      = cv2.getTrackbarPos("Bed_Side(0:L,1:R)", "Tuning Panel")
        h_min = cv2.getTrackbarPos("H_min", "Tuning Panel")
        h_max = cv2.getTrackbarPos("H_max", "Tuning Panel")
        s_min = cv2.getTrackbarPos("S_min", "Tuning Panel")
        v_min = cv2.getTrackbarPos("V_min", "Tuning Panel")

        # ── [핵심 수정] target_cx ──────────────────────────
        # 왼쪽 침대(0) : 기둥을 카메라 왼쪽(160px)에 두고 접근
        #               → 휠체어가 기둥 오른편에 서서 180도 후 침대 방향 후진 ✅
        # 오른쪽 침대(1): 기둥을 카메라 왼쪽(120px)에 두고 접근 ← 기존 580 → 수정!
        #               → 휠체어가 기둥 오른편에 서서 180도 후 침대 방향 후진 ✅
        #               (기존 580이면 기둥 왼편에 서게 되어 후진 시 침대를 지나침 ❌)
        target_cx = 160 if bed_side == 0 else 120

        # 기준선 시각화
        cv2.line(cv_image, (target_cx, 0), (target_cx, 480), (255, 0, 0), 2)

        # HSV 마스크
        hsv  = cv2.cvtColor(cv_image, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv,
                           np.array([h_min, s_min, v_min]),
                           np.array([h_max, 255,   255]))
        contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        # ── State 0 : 탐색 & 접근 ────────────────────────
        if self.state == 0:
            twist = Twist()

            if len(contours) > 0:
                c = max(contours, key=cv2.contourArea)

                if cv2.contourArea(c) > 300:
                    M = cv2.moments(c)
                    cx = int(M["m10"] / M["m00"])

                    x, y, w, h = cv2.boundingRect(c)
                    cv2.rectangle(cv_image, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    cv2.circle(cv_image, (cx, int(M["m01"] / M["m00"])), 5, (0, 0, 255), -1)

                    # 거리 계산 (핀홀 카메라 모델)
                    # 상수 237.3 = Real_Width(m) × Focal_Length(px)
                    # 환경에 맞게 캘리브레이션 필요
                    camera_dist_m = 237.3 / w if w > 0 else 9.9

                    cv2.putText(cv_image, f"Dist: {camera_dist_m:.2f}m",
                                (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX,
                                0.6, (0, 255, 0), 2)

                    error = target_cx - cx

                    # 회전 정렬 (수평 오차 > 10px)
                    if abs(error) > 10:
                        twist.angular.z = max(-0.3, min(0.3, float(error) * 0.002))
                        self.get_logger().info(f"🟦 정렬 중... 오차: {error}px")
                    else:
                        twist.angular.z = 0.0

                    # 전진 (목표 거리까지)
                    if camera_dist_m > target_dist_m:
                        twist.linear.x = 0.17
                    else:
                        # ── 목표 거리 도달 : 좌표 고정 & 방어막 생성 ──
                        twist.linear.x  = 0.0
                        twist.angular.z = 0.0

                        # 출발점 고정 (State 5 이동량 계산용)
                        self.start_x = self.robot_x
                        self.start_y = self.robot_y

                        # 기둥 절대 좌표 계산 (삼각함수)
                        self.pillar_x = self.robot_x + camera_dist_m * math.cos(self.current_yaw)
                        self.pillar_y = self.robot_y + camera_dist_m * math.sin(self.current_yaw)
                        self.bed_yaw  = self.current_yaw
                        self.park_side = bed_side
                        self.virtual_bed_active = True

                        self.get_logger().info(
                            f"📌 [앵커 고정] 기둥 좌표: "
                            f"({self.pillar_x:.2f}, {self.pillar_y:.2f}), "
                            f"침대 방향: {'오른쪽' if bed_side else '왼쪽'}")

                        # 추가 직진 거리 결정
                        extra_key = "Extra_Fwd_R(cm)" if bed_side == 1 else "Extra_Fwd_L(cm)"
                        extra_fwd_cm = cv2.getTrackbarPos(extra_key, "Tuning Panel")
                        self.extra_fwd_target = extra_fwd_cm / 100.0

                        if self.extra_fwd_target > 0.01:
                            self.change_state(
                                5, f"🚀 [State 5] 추가 직진 시작: {self.extra_fwd_target:.2f}m")
                        else:
                            # [수정] 왼쪽·오른쪽 모두 왼쪽 주차 지점으로 통일
                            #        → 항상 반시계 방향 90도(-π/2) 회전
                            self.target_yaw = self.normalize_angle(
                                self.current_yaw - math.pi / 2)
                            self.change_state(1, "🔄 [State 1] 90도 회전 시작!")

            self.publish_safe_twist(twist)

        # ── 카메라 뷰 표시 ────────────────────────────────
        state_labels = {
            0: "State 0: Tracking",
            1: "State 1: Rotating",
            2: "State 2: Aligning",
            3: "State 3: Docking",
            4: "State 4: Done ✅",
            5: "State 5: Extra Fwd",
        }
        label = state_labels.get(self.state, f"State {self.state}")
        side_label = "RIGHT BED" if cv2.getTrackbarPos("Bed_Side(0:L,1:R)", "Tuning Panel") else "LEFT BED"

        cv2.putText(cv_image, label,       (10, 30),  cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 255), 2)
        cv2.putText(cv_image, side_label,  (10, 60),  cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 100, 0), 2)

        cv2.imshow("Blue Tracking Vision", cv_image)
        cv2.imshow("Mask View", mask)
        cv2.waitKey(1)


# =========================================================
#  엔트리포인트
# =========================================================
def main(args=None):
    rclpy.init(args=args)
    node = PrecisionDockingNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("🛑 노드 종료 요청.")
    finally:
        node.destroy_node()
        rclpy.shutdown()
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()