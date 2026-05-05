#!/usr/bin/env python3
"""
=============================================================
  휠체어 자율주행 - 초정밀 후진 도킹 통합 노드 v5 (하이브리드)
=============================================================
  [센서 융합]
  - 이동 거리(X, Y) : Odometry (/odom) 사용
  - 회전 각도(Yaw)  : IMU (/imu) 사용 → 바퀴 슬립에 의한 오차 완벽 차단!

  [State 흐름]
  State 0  : 카메라 파란색 마커 탐색 → 정렬 & 목표 거리 접근
  State 5  : 추가 직진 (Extra Forward)
  State 1  : IMU 기반 90도 회전 (Closed-loop)
  State 2  : 라이다 가중 무게중심(Weighted Mean) 수직 정렬
  State 3  : 라이다 거리 피드백 후진 도킹 (0.3m 지점에서 정지)
  State 4  : IMU 기반 90도 최종 평행 주차 회전
  State 6  : 최종 주차 완료
=============================================================
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, LaserScan, Imu  # 💡 Imu 추가!
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
    def __init__(self, target_bed_id=1):
        super().__init__('precision_docking_node')
        self.publisher_ = self.create_publisher(Twist, 'cmd_vel', 10)
        self.image_sub = self.create_subscription(Image, '/camera/image_raw', self.image_callback, 10)
        self.scan_sub = self.create_subscription(LaserScan, '/scan', self.scan_callback, 10)
        self.odom_sub = self.create_subscription(Odometry, '/odom', self.odom_callback, 10)
        self.imu_sub = self.create_subscription(Imu, '/imu', self.imu_callback, 10)
        self.bridge = CvBridge()

        # ── 로봇 상태 ────────────────────────────────────────
        self.state       = 0
        self.robot_x     = 0.0
        self.robot_y     = 0.0
        self.current_yaw = 0.0
        self.target_yaw  = 0.0

        # ── 가상 방어막 ──────────────────────────────────────
        self.virtual_bed_active = False
        self.pillar_x  = 0.0
        self.pillar_y  = 0.0
        self.bed_yaw   = 0.0
        self.park_side = 0
        # ⭐️ [추가] 라이다 정면 거리값을 저장할 변수
        self.front_dist_lidar = 0.0

        # ── 추가 직진 (State 5) ──────────────────────────────
        self.start_x          = 0.0
        self.start_y          = 0.0
        self.extra_fwd_target = 0.0

        # ── State 2 정렬용 이동평균 버퍼 ────────────────────
        self._align_buf = []
        
        # 🎨 성준님이 튜닝하신 4가지 색상 프로필 + ⭐️ 맞춤형 거리 상수(dist_const) 추가!
        self.color_profiles = {
            # 파랑: 2.52m * 93px = 약 234.3 (기존 237.3 유지해도 무방)
            1: {"name": "🟦 Blue",   "h_min": 100, "h_max": 140, "s_min": 110, "v_min": 0,  "dist_const": 237.3},
            # 노랑: 3.00m * 42px = 126.0
            2: {"name": "🟨 Yellow", "h_min": 23,  "h_max": 40,  "s_min": 110, "v_min": 0,  "dist_const": 126.0},
            # 보라: 3.00m * 46px = 138.0
            3: {"name": "🟪 Purple", "h_min": 130, "h_max": 160, "s_min": 110, "v_min": 0,  "dist_const": 138.0},
            # 빨강: 1.35m * 95px = 약 128.2 (양끝단 교차)
            4: {"name": "🟥 Red",    "h_min": 160, "h_max": 10,  "s_min": 150, "v_min": 50, "dist_const": 128.0}
        }
        
        # 선택된 색상 정보 가져오기
        selected_color = self.color_profiles[target_bed_id]
        # 0: Left, 1: Right
        default_side = 1 if target_bed_id == 1 else 0
        
        # ⭐️ [추가] 현재 선택된 침대 번호를 클래스 변수로 저장! (분기 처리를 위함)
        self.current_bed_id = target_bed_id
        # ⭐️ [추가] 현재 선택된 색상의 거리 상수를 클래스 변수로 저장
        self.current_dist_const = selected_color["dist_const"]
        
        self.get_logger().info(f"✅ [통합 도킹 노드 v6] {selected_color['name']} (상수: {self.current_dist_const}) 모드로 초기화 완료!")
        
        # ── OpenCV 튜닝 패널 ────────────────────────────────
        cv2.namedWindow("Tuning Panel", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Tuning Panel", 420, 380)
                                                               #blue                    # yellow # purple # red #blue
        cv2.createTrackbar("H_min",             "Tuning Panel", 100, 179, self.nothing) # 23     # 130    # 0   #100
        cv2.createTrackbar("H_max",             "Tuning Panel", 140, 179, self.nothing) # 140    # 145    # 179 #140
        cv2.createTrackbar("S_min",             "Tuning Panel", 110, 255, self.nothing) # 110    # 110    # 214 #110
        cv2.createTrackbar("V_min",             "Tuning Panel",   0, 255, self.nothing) # 0      # 0      # 80  #0
        cv2.createTrackbar("Bed_Side(0:L,1:R)", "Tuning Panel",   1,   1, self.nothing) #
        cv2.createTrackbar("Target_Dist(cm)",   "Tuning Panel", 150, 200, self.nothing) #
        cv2.createTrackbar("Extra_Fwd_L(cm)",   "Tuning Panel",  80, 200, self.nothing) #
        cv2.createTrackbar("Extra_Fwd_R(cm)",   "Tuning Panel",  80, 200, self.nothing) #
        # 2. ⭐️ [핵심] 선택한 색상 값으로 슬라이더 위치 강제 이동! (버그 원천 차단)
        cv2.setTrackbarPos("H_min", "Tuning Panel", selected_color["h_min"])
        cv2.setTrackbarPos("H_max", "Tuning Panel", selected_color["h_max"])
        cv2.setTrackbarPos("S_min", "Tuning Panel", selected_color["s_min"])
        cv2.setTrackbarPos("V_min", "Tuning Panel", selected_color["v_min"])
        
        # 나머지 설정값도 기본값으로 싹 강제 세팅해줍니다.
        cv2.setTrackbarPos("Bed_Side(0:L,1:R)", "Tuning Panel", default_side)
        cv2.setTrackbarPos("Target_Dist(cm)",   "Tuning Panel", 150)
        cv2.setTrackbarPos("Extra_Fwd_L(cm)",   "Tuning Panel", 80)
        cv2.setTrackbarPos("Extra_Fwd_R(cm)",   "Tuning Panel", 80)

        self.get_logger().info("✅ [통합 도킹 노드 v5] IMU 하이브리드 모드 초기화 완료!")
    # =========================================================
    def nothing(self, x): pass

    def change_state(self, new_state, msg):
        self.state = new_state
        self.get_logger().info(msg)

    def get_valid_dist(self, ranges, index):
        d = ranges[index]
        return 3.0 if (np.isinf(d) or np.isnan(d) or d == 0.0) else d

    def euler_from_quaternion(self, x, y, z, w):
        t3 = +2.0 * (w * z + x * y)
        t4 = +1.0 - 2.0 * (y * y + z * z)
        return math.atan2(t3, t4)

    def normalize_angle(self, angle):
        while angle >  math.pi: angle -= 2 * math.pi
        while angle < -math.pi: angle += 2 * math.pi
        return angle

    # =========================================================
    #  Odom & IMU 콜백 : 위치는 Odom, 회전각(Yaw)은 IMU!
    # =========================================================
    def odom_callback(self, msg):
        """직진 이동 거리 측정을 위한 오도메트리 데이터"""
        self.robot_x = msg.pose.pose.position.x
        self.robot_y = msg.pose.pose.position.y

    def imu_callback(self, msg):
        """정밀 회전을 위한 IMU 자이로스코프 데이터"""
        q = msg.orientation
        self.current_yaw = self.euler_from_quaternion(q.x, q.y, q.z, q.w)

    # =========================================================
    #  가상 방어막 검사 & 모터 명령 발행
    # =========================================================
    def publish_safe_twist(self, twist):
        if self.virtual_bed_active and self.state != 5:
            dx = self.robot_x - self.pillar_x
            dy = self.robot_y - self.pillar_y
            local_x =  dx * math.cos(self.bed_yaw) + dy * math.sin(self.bed_yaw)
            local_y = -dx * math.sin(self.bed_yaw) + dy * math.cos(self.bed_yaw)

            if self.park_side == 0:   # 왼쪽 침대
                in_x = -0.10 < local_x < 1.60
                in_y = -0.10 < local_y < 0.85
            else:                     # 오른쪽 침대
                in_x = -0.25 < local_x < 1.70
                in_y = -0.80 < local_y < 0.15

            if in_x and in_y:
                self.get_logger().error(
                    f"🚨 [방어막] 침범! 긴급 제동! (lx={local_x:.2f}, ly={local_y:.2f})")
                twist.linear.x  = 0.0
                twist.angular.z = 0.0

        self.publisher_.publish(twist)

    # =========================================================
    #  Scan 콜백 : State 1 ~ 6
    # =========================================================
    def scan_callback(self, msg):
        self.front_dist_lidar = self.get_valid_dist(msg.ranges, 0)
        
        if self.state == 0:
            return

        twist = Twist()

        # ── State 5 : 추가 직진 ───────────────────────────
        if self.state == 5:
            dist_moved = math.hypot(
                self.robot_x - self.start_x,
                self.robot_y - self.start_y)

            self.get_logger().info(
                f"🚀 [추가 직진] {dist_moved:.2f}m / {self.extra_fwd_target:.2f}m")

            if dist_moved < self.extra_fwd_target:
                twist.linear.x  = 0.15
                twist.angular.z = -0.05 if self.park_side == 1 else 0.05
            else:
                twist.linear.x  = 0.0
                twist.angular.z = 0.0
                # 💡 회전 목표: 침대를 등지기 위해 90도 회전
                turn_deg = 180
                turn_rad = math.radians(turn_deg)
                self.target_yaw = self.normalize_angle(self.current_yaw + turn_rad)
                self.change_state(1, f"🔄 [State 1] {turn_deg}도 회전 시작!")

        # ── State 1 : IMU 기반 90도 회전 ──────────────
        elif self.state == 1:
            yaw_error = self.normalize_angle(self.target_yaw - self.current_yaw)

            if abs(yaw_error) > 0.02:
                # 💡 [핵심 수정] P 제어 계산
                cmd_w = yaw_error * 2.0
                
                # 💡 데드밴드 보상: 계산된 속도가 너무 작더라도, 최소 0.15의 속도는 보장!
                min_w = 0.15
                if cmd_w > 0:
                    twist.angular.z = max(min_w, min(0.5, cmd_w))
                else:
                    twist.angular.z = min(-min_w, max(-0.5, cmd_w))
            else:
                twist.angular.z = 0.0
                self._align_buf.clear()
                if getattr(self, 'current_bed_id', 1) == 4:
                    self.start_x = self.robot_x
                    self.start_y = self.robot_y
                    #self.target_yaw = self.current_yaw # 현재 각도 그대로 유지!
                    self.change_state(6, "➡️ [State 6] 라이다 정렬 생략! 바로 최종 나란히 이동!")
                
                # 파란색(1번) 등 뒤에 벽이 있는 침대는 원래대로 라이다 정렬 진행
                else:
                    self.change_state(2, "📐 [State 2] 라이다 정렬 시작!")

        # ── State 2 : 라이다 벽면 법선 탐색 정렬 ────────
        # ── State 2 : 라이다 벽면 법선 탐색 정렬 ────────
        elif self.state == 2:
            arc_start, arc_end = 120, 241
            arc_dists = []
            for i in range(arc_start, arc_end):
                d = self.get_valid_dist(msg.ranges, i)
                arc_dists.append((i, d))

            min_idx, min_dist = min(arc_dists, key=lambda t: t[1])
            idx_error = min_idx - 180  # 후면 정중앙(180도)과의 차이
            
            # 좌우 대칭 검사 (정밀 정렬용)
            sym_offset = 20
            left_val = self.get_valid_dist(msg.ranges, min_idx - sym_offset)
            right_val = self.get_valid_dist(msg.ranges, min_idx + sym_offset)
            sym_error = left_val - right_val

            self.get_logger().info(
                f"📐 [벽 정렬 중] 오차:{idx_error}° | 대칭오차:{sym_error:.3f}m | 속도:{twist.angular.z:.2f}")

            idx_ok = abs(idx_error) <= 2  # 2도 이내면 합격
            sym_ok = abs(sym_error) < 0.03 # 3cm 이내면 합격

            if idx_ok and sym_ok:
                twist.angular.z = 0.0
                # ⭐️ [분기 처리] 빨간색 침대(4번)는 정렬 후 바로 종료 혹은 이동
                if getattr(self, 'current_bed_id', 1) == 4:
                    self.start_x = self.robot_x
                    self.start_y = self.robot_y
                    self.target_yaw = self.current_yaw
                    self.change_state(6, "➡️ [State 6] 빨간 침대 - 최종 위치 조정 시작!")
                else:
                    # 일반적인 경우: 90도 회전하여 침대와 나란히 서기
                    turn_rad = math.radians(90)
                    if self.park_side == 1: # 오른쪽 침대
                        self.target_yaw = self.normalize_angle(self.current_yaw + turn_rad)
                    else:                   # 왼쪽 침대
                        self.target_yaw = self.normalize_angle(self.current_yaw - turn_rad)
                    self.change_state(4, "🔄 [State 4] 90도 최종 회전 시작!")
            
            else:
                # 💡 [핵심 추가] 오차를 줄이기 위해 로봇을 회전시킴!
                # P-제어: 오차에 비례해서 회전 속도 결정
                cmd_w = float(idx_error) * 0.015 
                
                # 최소 회전 속도 보장 (마찰력 극복용 데드밴드)
                min_w = 0.12
                if cmd_w > 0:
                    twist.angular.z = max(min_w, min(0.4, cmd_w))
                else:
                    twist.angular.z = min(-min_w, max(-0.4, cmd_w))
       #── State 3 : 오도메트리 정량 후진 도킹 (벽이 없어도 OK!) ────────────
        elif self.state == 3:
            # 시작점으로부터 후진한 거리 계산
            dist_moved = math.hypot(self.robot_x - self.start_x, self.robot_y - self.start_y)
            
            # 💡 [튜닝 포인트] 뒤로 몇 미터 들어갈지 설정 (침대 길이에 맞춰 조절하세요!)
            target_back_dist = 1.2  
            
            # 뒤로 갈 때 삐뚤어지지 않게 IMU로 꽉 잡아주기 (헤딩 락)
            yaw_error = self.normalize_angle(self.docking_start_yaw - self.current_yaw)

            if dist_moved < target_back_dist:          
                twist.linear.x  = -0.15
                # 조향: 오차가 생기면 미세하게 핸들을 틀어서 똑바로 후진하게 만듦
                twist.angular.z = max(-0.2, min(0.2, yaw_error * 1.5))
                self.get_logger().info(f"🚙 [후진 중] {dist_moved:.2f}m / {target_back_dist:.2f}m 이동 완료")
            else:                        
                twist.linear.x = 0.0
                twist.angular.z = 0.0
                
                # 💡 최종 평행 주차를 위한 90도 회전
                turn_rad = math.radians(90)
                if self.park_side == 1: # 오른쪽 침대
                    self.target_yaw = self.normalize_angle(self.current_yaw + turn_rad)
                else:                   # 왼쪽 침대
                    self.target_yaw = self.normalize_angle(self.current_yaw - turn_rad)

                self.change_state(4, "🔄 [State 4] 침대와 나란히 서기 위해 90도 최종 회전 시작!")
         #── State 4 : IMU 기반 최종 주차 회전 ──────────
         #── State 4 : IMU 기반 최종 주차 회전 ──────────
        elif self.state == 4:
            yaw_error = self.normalize_angle(self.target_yaw - self.current_yaw)

            if abs(yaw_error) > 0.02:
                # 💡 [핵심 수정] P 제어 계산
                cmd_w = yaw_error * 2.0
                
                # 💡 데드밴드 보상: 최소 0.15 보장
                min_w = 0.15
                if cmd_w > 0:
                    twist.angular.z = max(min_w, min(0.5, cmd_w))
                else:
                    twist.angular.z = min(-min_w, max(-0.5, cmd_w))
            else:
                twist.angular.z = 0.0
                #self.change_state(6, "🎉 [State 6] 최종 주차 완료!!")
                self.start_x = self.robot_x
                self.start_y = self.robot_y
                self.change_state(6, "➡️ [State 6] 침대 안쪽으로 최종 위치 조정 시작!")
        # ── State 5 : 추가 직진 ───────────────────────────
        elif self.state == 5:
            dist_moved = math.hypot(
                self.robot_x - self.start_x,
                self.robot_y - self.start_y)

            self.get_logger().info(
                f"🚀 [추가 직진] {dist_moved:.2f}m / {self.extra_fwd_target:.2f}m")

            if dist_moved < self.extra_fwd_target:
                twist.linear.x  = 0.15
                # ⭐️ [수정 1] 침대 모서리로 파고드는 곡선 주행 삭제! 무조건 똑바로만 직진!
                twist.angular.z = 0.0 
            else:
                twist.linear.x  = 0.0
                twist.angular.z = 0.0
                
                # ⭐️ [수정 2] 현재의 삐딱한 대각선 각도를 무시하고, 절대 방위(bed_yaw) 기준으로 180도 평행 세팅!
                turn_rad = math.radians(180)
                if self.park_side == 1:
                    self.target_yaw = self.normalize_angle(self.bed_yaw + turn_rad)
                else:
                    self.target_yaw = self.normalize_angle(self.bed_yaw - turn_rad)
                    
                self.change_state(1, f"🔄 [State 1] 맵 축 기준 완벽한 180도 평행 회전 시작!")
        # ── State 6 : 진짜 주차 완료 ──────────
        # ── State 6 : 침대 옆 나란히 최종 이동 (새로 추가!) ──────────
        # ── State 6 : 침대 옆 나란히 최종 이동 (헤딩 락 적용!) ──────────
        # ── State 6 : 침대 옆 나란히 최종 이동 (헤딩 락 적용!) ──────────
        elif self.state == 6:
            final_dist_moved = math.hypot(
                self.robot_x - self.start_x,
                self.robot_y - self.start_y)
                
            final_move_dist = 0.3  # 💡 30cm 이동
            
            # 현재 목표 각도와 얼마나 틀어져 있는지 계산 (헤딩 락용)
            yaw_error = self.normalize_angle(self.target_yaw - self.current_yaw)

            # 💡 [로그 추가] 이동 거리와 현재 자세 오차(도 단위)를 실시간 출력!
            self.get_logger().info(
                f"➡️ [최종 이동] 거리: {final_dist_moved:.2f}m / {final_move_dist:.2f}m  |  "
                f"자세 오차: {math.degrees(yaw_error):.2f}°"
            )

            if final_dist_moved < final_move_dist:
                # 💡 직진/후진 속도 설정 (후진은 -0.1)
                twist.linear.x = -0.1  
                
                # 조향(핸들) 제어: 각도 오차를 이용해 미세하게 균형을 잡음
                twist.angular.z = max(-0.2, min(0.2, yaw_error * 1.5))
                
            else:
                twist.linear.x = 0.0
                twist.angular.z = 0.0
                self.change_state(7, "🎉 [State 7] 진짜 최종 주차 완벽 성공!!")

        # 모터 명령 발행 (중복 제거 완료!)
        self.publish_safe_twist(twist)

    # =========================================================
    #  Image 콜백 : State 0 – 마커 탐색 & 접근
    # =========================================================
    def image_callback(self, msg):
        cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")

        target_dist_m = cv2.getTrackbarPos("Target_Dist(cm)",   "Tuning Panel") / 100.0
        bed_side      = cv2.getTrackbarPos("Bed_Side(0:L,1:R)", "Tuning Panel")
        h_min = cv2.getTrackbarPos("H_min", "Tuning Panel")
        h_max = cv2.getTrackbarPos("H_max", "Tuning Panel")
        s_min = cv2.getTrackbarPos("S_min", "Tuning Panel")
        v_min = cv2.getTrackbarPos("V_min", "Tuning Panel")

        target_cx = 160 if bed_side == 0 else 120
        cv2.line(cv_image, (target_cx, 0), (target_cx, 480), (255, 0, 0), 2)
        hsv  = cv2.cvtColor(cv_image, cv2.COLOR_BGR2HSV)
        if h_min > h_max:
            # 1. 오른쪽 끝부분 (예: 160 ~ 179)
            upper_mask = cv2.inRange(hsv, np.array([h_min, s_min, v_min]), np.array([179, 255, 255]))
            # 2. 왼쪽 시작부분 (예: 0 ~ 10)
            lower_mask = cv2.inRange(hsv, np.array([0, s_min, v_min]), np.array([h_max, 255, 255]))
            # 3. 두 마스크 합치기
            mask = cv2.bitwise_or(lower_mask, upper_mask)
        else:
            # 파랑, 노랑, 보라 등 일반적인 색상 처리
            mask = cv2.inRange(hsv, np.array([h_min, s_min, v_min]), np.array([h_max, 255, 255]))
        contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        if self.state == 0:
            twist = Twist()

            if contours:
                c = max(contours, key=cv2.contourArea)

                if cv2.contourArea(c) > 300:
                    M  = cv2.moments(c)
                    cx = int(M["m10"] / M["m00"])
                    x, y, w, h = cv2.boundingRect(c)

                    cv2.rectangle(cv_image, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    cv2.circle(cv_image, (cx, int(M["m01"] / M["m00"])), 5, (0, 0, 255), -1)

                    camera_dist_m = self.current_dist_const / w if w > 0 else 9.9
                    cv2.putText(cv_image, f"Dist: {camera_dist_m:.2f}m",
                                (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX,
                                0.6, (0, 255, 0), 2)
                    self.get_logger().info(
                        f"📏 [거리 검증] 카메라(착각): {camera_dist_m:.2f}m | 라이다(진짜): {self.front_dist_lidar:.2f}m | Box너비(w): {w}px"
                    )
                    error = target_cx - cx
                    if abs(error) > 10:
                        twist.angular.z = max(-0.3, min(0.3, float(error) * 0.002))
                        self.get_logger().info(f"🟦 정렬 중... 오차: {error}px")
                    else:
                        twist.angular.z = 0.0

                    if camera_dist_m > target_dist_m:
                        twist.linear.x = 0.17
                    else:
                        twist.linear.x  = 0.0
                        twist.angular.z = 0.0

                        self.start_x = self.robot_x
                        self.start_y = self.robot_y

                        self.pillar_x = (self.robot_x + camera_dist_m * math.cos(self.current_yaw))
                        self.pillar_y = (self.robot_y + camera_dist_m * math.sin(self.current_yaw))
                        absolute_deg = round(math.degrees(self.current_yaw) / 90.0) * 90.0
                        self.bed_yaw = math.radians(absolute_deg)
                        self.park_side = bed_side
                        self.virtual_bed_active = True

                        self.get_logger().info(
                            f"📌 [앵커 고정] 기둥:({self.pillar_x:.2f},{self.pillar_y:.2f})  "
                            f"침대:{'오른쪽' if bed_side else '왼쪽'}")

                        extra_key    = "Extra_Fwd_R(cm)" if bed_side == 1 else "Extra_Fwd_L(cm)"
                        extra_fwd_cm = cv2.getTrackbarPos(extra_key, "Tuning Panel")
                        self.extra_fwd_target = extra_fwd_cm / 100.0

                        if self.extra_fwd_target > 0.01:
                            self.change_state(
                                5, f"🚀 [State 5] 추가 직진: {self.extra_fwd_target:.2f}m")
                        else:
                            # ⭐️ [수정 완료] 추가 직진 없이 바로 돌 때도 낡은 85도 코드 삭제! 
                            # 맵 축(bed_yaw) 기준 완벽한 180도 회전 적용!
                            turn_rad = math.radians(180)
                            if self.park_side == 1: # 오른쪽 침대일 때
                                self.target_yaw = self.normalize_angle(self.bed_yaw + turn_rad)
                            else:                   # 왼쪽 침대일 때
                                self.target_yaw = self.normalize_angle(self.bed_yaw - turn_rad)

                            self.change_state(1, f"🔄 [State 1] 맵 축 기준 완벽한 180도 평행 회전 시작!")
            self.publish_safe_twist(twist)

        # ── 화면 표시 ─────────────────────────────────────
        labels = {0: "Tracking", 1: "Rotating 90°", 2: "Aligning (Lidar)",
                  3: "Docking", 4: "Final Turn", 5: "Extra Fwd", 6: "Done ✅", 7: "Done ✅"}
        cv2.putText(cv_image,
                    f"State {self.state}: {labels.get(self.state, '')}",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 255), 2)
        cv2.putText(cv_image,
                    "RIGHT BED" if bed_side else "LEFT BED",
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 100, 0), 2)

        cv2.imshow("Blue Tracking Vision", cv_image)
        cv2.imshow("Mask View", mask)
        cv2.waitKey(1)


# =========================================================
#  엔트리포인트
# =========================================================#
#  엔트리포인트 (터미널 메뉴 추가!)
# =========================================================
def main(args=None):
    print("\n===========================================")
    print(" 🏥 자율주행 휠체어 병실 도킹 시스템")
    print("===========================================")
    print(" [1] 🟦 파란색 침대 (Blue)")
    print(" [2] 🟨 노란색 침대 (Yellow)")
    print(" [3] 🟪 보라색 침대 (Purple)")
    print(" [4] 🟥 빨간색 침대 (Red)")
    print("===========================================")
    
    try:
        choice = int(input("🎯 목적지 침대 번호를 입력하세요 (1~4): "))
        if choice not in [1, 2, 3, 4]:
            print("⚠️ 잘못된 입력입니다. 기본값(1: 파란색)으로 시작합니다.")
            choice = 1
    except ValueError:
        print("⚠️ 숫자가 아닙니다. 기본값(1: 파란색)으로 시작합니다.")
        choice = 1

    rclpy.init(args=args)
    
    # 선택한 침대 번호를 노드로 전달!
    node = PrecisionDockingNode(target_bed_id=choice)
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("🛑 노드 종료 요청.")
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    main()