#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, LaserScan
from nav_msgs.msg import Odometry  # ⭐️ 오도메트리(IMU+엔코더) 추가!
from geometry_msgs.msg import Twist
from cv_bridge import CvBridge
import cv2
import numpy as np
import math  # ⭐️ 각도 계산용 수학 라이브러리 추가
from rclpy.qos import qos_profile_sensor_data

class PrecisionDockingNode(Node):
    def __init__(self):
        super().__init__('precision_docking_node')
        self.publisher_ = self.create_publisher(Twist, 'cmd_vel', 10)
        self.image_subscription = self.create_subscription(Image, '/camera/image_raw', self.image_callback, qos_profile_sensor_data)
        self.scan_subscription = self.create_subscription(LaserScan, '/scan', self.scan_callback, qos_profile_sensor_data)
        
        # ⭐️ 오도메트리 구독 추가! (로봇의 현재 각도 파악용)
        self.odom_subscription = self.create_subscription(Odometry, '/odom', self.odom_callback, 10)
        
        self.bridge = CvBridge()
        
        self.state = 0  
        self.state_start_time = self.get_clock().now()
        
        # ⭐️ 센서 퓨전 변수 초기화
        self.current_yaw = 0.0  # 현재 로봇의 각도 (라디안)
        self.target_yaw = 0.0   # State 1 도달 시 설정할 180도 회전 목표 각도
        
        # 트랙바 제어용 창 생성
        cv2.namedWindow("Tuning Panel", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Tuning Panel", 400, 300)
        
        # 트랙바 생성 (SDF 50% 압축 맵에 맞춘 초기값 튜닝)
        # 1. 색상 인식 튜닝 (HSV)
        cv2.createTrackbar("H_min", "Tuning Panel", 100, 179, self.nothing)
        cv2.createTrackbar("H_max", "Tuning Panel", 140, 179, self.nothing)
        cv2.createTrackbar("S_min", "Tuning Panel", 110, 255, self.nothing)
        cv2.createTrackbar("V_min", "Tuning Panel", 0, 255, self.nothing)
        
        # 2. 비주얼 오프셋 튜닝 (⭐️ 기본값 160: 파란색을 화면 왼쪽에 끼고 돌기!)
        cv2.createTrackbar("Target_CX", "Tuning Panel", 160, 640, self.nothing)
        
        # 3. 정지 거리 튜닝 (단위: cm) - 50% 맵이므로 정지 거리도 좁게 설정 권장 (예: 60cm)
        cv2.createTrackbar("Target_Dist(cm)", "Tuning Panel", 150, 200, self.nothing)

        self.get_logger().info("🎛️ [Tuning Mode: Sensor Fusion] 트랙바가 활성화되었습니다.")

    def nothing(self, x):
        pass

    def change_state(self, new_state, msg):
        self.state = new_state
        self.state_start_time = self.get_clock().now()
        self.get_logger().info(msg)

    def get_valid_dist(self, ranges, index):
        d = ranges[index]
        if np.isinf(d) or np.isnan(d) or d == 0.0:
            return 3.0
        return d

    # ⭐️ 쿼터니언(Quaternion) 좌표를 오일러 각도(Yaw)로 변환하는 수학 함수
    def euler_from_quaternion(self, x, y, z, w):
        t3 = +2.0 * (w * z + x * y)
        t4 = +1.0 - 2.0 * (y * y + z * z)
        return math.atan2(t3, t4)

    # ⭐️ 실시간 로봇 각도 업데이트 콜백
    def odom_callback(self, msg):
        q = msg.pose.pose.orientation
        # IMU 데이터를 기반으로 현재 로봇의 Yaw 각도(왼쪽+, 오른쪽-) 계산
        self.current_yaw = self.euler_from_quaternion(q.x, q.y, q.z, q.w)

    def scan_callback(self, msg):
        if self.state == 0: return

        twist = Twist()

        # 🟡 [State 1] ⭐️ 오도메트리 기반 180도 초정밀 회전! (타이머 삭제)
        if self.state == 1:
            # ⭐️ 오차 계산: 목표 각도 - 현재 각도
            yaw_error = self.target_yaw - self.current_yaw
            
            # ⭐️ 각도 오차를 -pi ~ pi 사이로 정규화 (가장 빠른 회전 방향 결정)
            while yaw_error > math.pi: yaw_error -= 2 * math.pi
            while yaw_error < -math.pi: yaw_error += 2 * math.pi
            
            # 오차가 0.05 라디안(약 2.8도)보다 크면 계속 회전 (P제어 적용)
            if abs(yaw_error) > 0.05:
                # 오차에 비례해서 부드럽게 감속하며 회전 (max 0.5 rad/s)
                twist.angular.z = max(-0.5, min(0.5, yaw_error * 1.5))
                self.get_logger().info(f"🔄 [회전 중] 각도 오차: {math.degrees(yaw_error):.2f}도", once=True)
            else:
                # ⭐️ 목표 각도 도달! 정지 후 다음 상태로 이동
                twist.angular.z = 0.0
                self.change_state(2, "📐 [State 2] 180도 각도 정밀 회전 완료! 라이다 수직 칼각 정렬 시작!")

        # 🟢 [State 2] 라이다 뒷벽 수직 정렬 (기둥 회피 좁은 시야각)
        elif self.state == 2:
            # ⭐️ 175, 185(좁은 간격)을 사용하여 기둥 간섭 회피
            dist_175 = self.get_valid_dist(msg.ranges, 175)
            dist_185 = self.get_valid_dist(msg.ranges, 185)
            error = dist_175 - dist_185
            
            if abs(error) < 0.03:  # 3cm 너그럽게 허용
                self.change_state(3, "🚙 [State 3] 칼각 정렬 완료! 엉덩이로 밀어 넣습니다!")
            else:
                angular_speed = float(error) * 1.5
                twist.angular.z = max(-0.2, min(0.2, angular_speed))

        # 🔵 [State 3] 후진 주차
        elif self.state == 3:
            dist_180 = self.get_valid_dist(msg.ranges, 180)
            
            # ⭐️ 후진 중에도 계속 175도와 185도를 비교해서 오차를 구합니다.
            dist_175 = self.get_valid_dist(msg.ranges, 175)
            dist_185 = self.get_valid_dist(msg.ranges, 185)
            error = dist_175 - dist_185
            
            if dist_180 > 0.8: # 벽까지 20cm 남을 때까지
                twist.linear.x = -0.15 # 뒤로 가면서
                
                # ⭐️ [핵심] 동시에 핸들도 미세하게 꺾어줍니다! (에러 보정)
                # 후진 중이므로 조향 속도는 조금 더 약하게(-0.1 ~ 0.1) 줍니다.
                twist.angular.z = max(-0.1, min(0.1, float(error) * 1.5)) 
            else:
                self.change_state(4, "🎉 [State 4] 완벽한 실시간 보정 평행주차 완료!!")

        self.publisher_.publish(twist)

    def image_callback(self, msg):
        cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")
        
        # 트랙바에서 실시간으로 값 읽어오기
        h_min = cv2.getTrackbarPos("H_min", "Tuning Panel")
        h_max = cv2.getTrackbarPos("H_max", "Tuning Panel")
        s_min = cv2.getTrackbarPos("S_min", "Tuning Panel")
        v_min = cv2.getTrackbarPos("V_min", "Tuning Panel")
        target_cx = cv2.getTrackbarPos("Target_CX", "Tuning Panel")
        target_dist_m = cv2.getTrackbarPos("Target_Dist(cm)", "Tuning Panel") / 100.0 

        # 화면에 목표 오프셋 기준선(파란색 세로선) 그리기
        cv2.line(cv_image, (target_cx, 0), (target_cx, 480), (255, 0, 0), 2)
        cv2.putText(cv_image, f"Target CX: {target_cx}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

        hsv = cv2.cvtColor(cv_image, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array([h_min, s_min, v_min]), np.array([h_max, 255, 255]))
        contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        twist = Twist()

        if self.state == 0:
            found_target = False 

            if len(contours) > 0:
                c = max(contours, key=cv2.contourArea)
                
                # 면적(Area) 필터로 노이즈 제거
                if cv2.contourArea(c) > 300: 
                    found_target = True
                    M = cv2.moments(c)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                        
                        error = target_cx - cx 
                        
                        x, y, w, h = cv2.boundingRect(c)
                        cv2.rectangle(cv_image, (x, y), (x + w, y + h), (0, 255, 0), 2)
                        cv2.circle(cv_image, (cx, cy), 5, (0, 0, 255), -1)
                        
                        camera_dist_m = 237.3 / w
                        
                        # 조향 제어 (비주얼 오프셋 유지)
                        if abs(error) > 10:  
                            angular_speed = float(error) * 0.002
                            twist.angular.z = max(-0.3, min(0.3, angular_speed))
                        else:               
                            twist.angular.z = 0.0
                        
                        # 목표 거리까지 비스듬히 전진
                        if camera_dist_m > target_dist_m:
                            twist.linear.x = 0.15
                        else:
                            # ⭐️ 도달 완료! 정지 후 센서 퓨전 회전 준비
                            twist.linear.x = 0.0
                            twist.angular.z = 0.0
                            
                            # ⭐️ [핵심] 180도 회전을 시작하기 전, 현재 각도(`self.current_yaw`)에 180도(`math.pi`)를 더해 목표 각도를 설정!
                            self.target_yaw = self.current_yaw + math.pi
                            
                            # 정규화: 각도가 pi ~ -pi 범위를 넘어가면 보정해줌
                            if self.target_yaw > math.pi: self.target_yaw -= 2 * math.pi
                            
                            self.get_logger().info(f"🎯 앵커 찍기! 현재각도: {math.degrees(self.current_yaw):.1f}도 -> 목표각도: {math.degrees(self.target_yaw):.1f}도")
                            
                            self.change_state(1, f"🔄 [State 1] 오도메트리 기반 180도 정밀 회전 시작!")

            if not found_target:
                twist.angular.z = 0.3 

            self.publisher_.publish(twist)

        # 마스크 및 영상 화면 출력
        cv2.imshow("Color Mask", mask)
        cv2.imshow("Blue Tracking Vision", cv_image)
        cv2.waitKey(1)

def main(args=None):
    rclpy.init(args=args)
    node = PrecisionDockingNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()