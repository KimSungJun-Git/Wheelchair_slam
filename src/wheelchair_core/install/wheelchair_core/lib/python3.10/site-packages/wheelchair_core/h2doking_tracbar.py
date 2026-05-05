#!/usr/bin/env python3
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
    def __init__(self):
        super().__init__('precision_docking_node')
        self.publisher_ = self.create_publisher(Twist, 'cmd_vel', 10)
        self.image_subscription = self.create_subscription(Image, '/camera/image_raw', self.image_callback, 10)
        self.scan_subscription = self.create_subscription(LaserScan, '/scan', self.scan_callback, 10)
        self.odom_subscription = self.create_subscription(Odometry, '/odom', self.odom_callback, 10)
        
        self.bridge = CvBridge()
        
        self.state = 0  
        self.current_yaw = 0.0  
        self.target_yaw = 0.0   
        self.robot_x = 0.0      
        self.robot_y = 0.0      
        
        self.virtual_bed_active = False
        self.pillar_x = 0.0
        self.pillar_y = 0.0
        self.bed_yaw = 0.0  
        self.park_side = 0
        
        self.start_x = 0.0
        self.start_y = 0.0
        self.extra_fwd_target = 0.0
        
        cv2.namedWindow("Tuning Panel", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Tuning Panel", 400, 350)
        
        cv2.createTrackbar("H_min", "Tuning Panel", 100, 179, self.nothing)
        cv2.createTrackbar("H_max", "Tuning Panel", 140, 179, self.nothing)
        cv2.createTrackbar("S_min", "Tuning Panel", 110, 255, self.nothing)
        cv2.createTrackbar("V_min", "Tuning Panel", 0, 255, self.nothing)
        
        cv2.createTrackbar("Bed_Side(0:L,1:R)", "Tuning Panel", 1, 1, self.nothing)
        cv2.createTrackbar("Target_Dist(cm)", "Tuning Panel", 150, 200, self.nothing)
        
        cv2.createTrackbar("Extra_Fwd_L(cm)", "Tuning Panel", 0, 200, self.nothing)
        cv2.createTrackbar("Extra_Fwd_R(cm)", "Tuning Panel", 80, 200, self.nothing)

        self.get_logger().info("🎛️ [Master Mode] 궤적 보정 및 무한직진 방지 코드 활성화!")

    def nothing(self, x): pass

    def change_state(self, new_state, msg):
        self.state = new_state
        self.get_logger().info(msg)

    def get_valid_dist(self, ranges, index):
        d = ranges[index]
        return 3.0 if np.isinf(d) or np.isnan(d) or d == 0.0 else d

    def euler_from_quaternion(self, x, y, z, w):
        t3 = +2.0 * (w * z + x * y)
        t4 = +1.0 - 2.0 * (y * y + z * z)
        return math.atan2(t3, t4)

    def odom_callback(self, msg):
        self.robot_x = msg.pose.pose.position.x
        self.robot_y = msg.pose.pose.position.y
        q = msg.pose.pose.orientation
        self.current_yaw = self.euler_from_quaternion(q.x, q.y, q.z, q.w)

    def publish_safe_twist(self, twist):
        # 🛡️ 추가 직진(State 5) 중에는 방어막에 걸려 멈추지 않도록 예외 처리
        if self.virtual_bed_active and self.state != 5:
            dx = self.robot_x - self.pillar_x
            dy = self.robot_y - self.pillar_y
            local_x = dx * math.cos(self.bed_yaw) + dy * math.sin(self.bed_yaw)   
            local_y = -dx * math.sin(self.bed_yaw) + dy * math.cos(self.bed_yaw)  
            
            if self.park_side == 0:  
                in_x = -0.1 < local_x < 1.6   
                in_y = -0.1 < local_y < 0.85  
            else:                    
                in_x = -0.2 < local_x < 1.7
                in_y = -0.95 < local_y < 0.2  

            if in_x and in_y:
                self.get_logger().error("🚨 [스마트 방어막] 영역 침범! 긴급 제동!")
                twist.linear.x = 0.0
                twist.angular.z = 0.0

        self.publisher_.publish(twist)

    def scan_callback(self, msg):
        if self.state == 0: return
        twist = Twist()

        # 🚀 [State 5] 궤적 보정: 정밀 추가 직진
        if self.state == 5:
            dist_moved = math.hypot(self.robot_x - self.start_x, self.robot_y - self.start_y)
            
            # 실시간 거리 로그 출력 (멈추지 않는 원인 파악용)
            self.get_logger().info(f"🚀 [추가 직진] 이동: {dist_moved:.2f}m / 목표: {self.extra_fwd_target:.2f}m")

            if dist_moved < self.extra_fwd_target:
                twist.linear.x = 0.15 
                # ⭐️ 오른쪽 침대(1)일 때 가다가 박으면, 왼쪽으로 살짝 조향을 줘서 침대와 멀어지게 함
                if self.park_side == 1:
                    twist.angular.z = 0.05  # 미세 왼쪽 조향
                else:
                    twist.angular.z = -0.05 # 미세 오른쪽 조향
            else:
                twist.linear.x = 0.0
                twist.angular.z = 0.0
                
                bed_side = cv2.getTrackbarPos("Bed_Side(0:L,1:R)", "Tuning Panel")
                turn_angle = -math.pi if bed_side == 0 else math.pi
                self.target_yaw = self.current_yaw + turn_angle
                
                while self.target_yaw > math.pi: self.target_yaw -= 2 * math.pi
                while self.target_yaw < -math.pi: self.target_yaw += 2 * math.pi
                
                self.change_state(1, "🔄 [State 1] 목표 지점 도달! 180도 회전 시작!")

        elif self.state == 1:
            yaw_error = self.target_yaw - self.current_yaw
            while yaw_error > math.pi: yaw_error -= 2 * math.pi
            while yaw_error < -math.pi: yaw_error += 2 * math.pi
            
            if abs(yaw_error) > 0.05:
                twist.angular.z = max(-0.5, min(0.5, yaw_error * 1.5))
            else:
                twist.angular.z = 0.0
                self.change_state(2, "📐 [State 2] 라이다 수직 칼각 정렬 시작!")

        elif self.state == 2:
            dist_175 = self.get_valid_dist(msg.ranges, 175)
            dist_185 = self.get_valid_dist(msg.ranges, 185)
            error = dist_175 - dist_185
            if abs(error) < 0.03:  
                self.change_state(3, "🚙 [State 3] 후진 도킹 시작!")
            else:
                twist.angular.z = max(-0.2, min(0.2, float(error) * 1.5))

        elif self.state == 3:
            dist_180 = self.get_valid_dist(msg.ranges, 180)
            dist_175 = self.get_valid_dist(msg.ranges, 175)
            dist_185 = self.get_valid_dist(msg.ranges, 185)
            error = dist_175 - dist_185
            
            if dist_180 > 0.8: 
                twist.linear.x = -0.15 
                twist.angular.z = max(-0.1, min(0.1, float(error) * 1.5)) 
            else:
                self.change_state(4, "🎉 [State 4] 주차 완료!!")

        self.publish_safe_twist(twist)

    def image_callback(self, msg):
        cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")
        target_dist_m = cv2.getTrackbarPos("Target_Dist(cm)", "Tuning Panel") / 100.0 
        bed_side = cv2.getTrackbarPos("Bed_Side(0:L,1:R)", "Tuning Panel")
        
        # ⭐️ 오른쪽 모드일 때 침대와 더 멀리 떨어져서 진입하도록 CX 값을 더 크게 설정
        target_cx = 160 if bed_side == 0 else 580 

        h_min = cv2.getTrackbarPos("H_min", "Tuning Panel")
        h_max = cv2.getTrackbarPos("H_max", "Tuning Panel")
        s_min = cv2.getTrackbarPos("S_min", "Tuning Panel")
        v_min = cv2.getTrackbarPos("V_min", "Tuning Panel")

        cv2.line(cv_image, (target_cx, 0), (target_cx, 480), (255, 0, 0), 2)
        hsv = cv2.cvtColor(cv_image, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array([h_min, s_min, v_min]), np.array([h_max, 255, 255]))
        contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        if self.state == 0:
            twist = Twist()
            if len(contours) > 0:
                c = max(contours, key=cv2.contourArea)
                if cv2.contourArea(c) > 300: 
                    M = cv2.moments(c)
                    cx = int(M["m10"] / M["m00"])
                    error = target_cx - cx 
                    x, y, w, h = cv2.boundingRect(c)
                    camera_dist_m = 237.3 / w
                    
                    twist.angular.z = max(-0.3, min(0.3, float(error) * 0.002)) if abs(error) > 10 else 0.0
                    
                    if camera_dist_m > target_dist_m:
                        twist.linear.x = 0.17
                    else:
                        twist.linear.x = 0.0
                        twist.angular.z = 0.0
                        
                        # ⭐️ [중요] State 5 진입 전 현재 위치를 딱 한 번만 고정!
                        self.start_x = self.robot_x
                        self.start_y = self.robot_y
                        
                        self.pillar_x = self.robot_x + (camera_dist_m * math.cos(self.current_yaw))
                        self.pillar_y = self.robot_y + (camera_dist_m * math.sin(self.current_yaw))
                        self.bed_yaw = self.current_yaw  
                        self.park_side = bed_side        
                        self.virtual_bed_active = True   
                        
                        extra_fwd_cm = cv2.getTrackbarPos("Extra_Fwd_L(cm)", "Tuning Panel") if bed_side == 0 else cv2.getTrackbarPos("Extra_Fwd_R(cm)", "Tuning Panel")
                        self.extra_fwd_target = extra_fwd_cm / 100.0
                        
                        if self.extra_fwd_target > 0.01:
                            self.change_state(5, f"🚀 [State 0.5] 추가 직진 시작: {self.extra_fwd_target}m")
                        else:
                            self.change_state(1, "🔄 [State 1] 회전 시작!")

            self.publish_safe_twist(twist)

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