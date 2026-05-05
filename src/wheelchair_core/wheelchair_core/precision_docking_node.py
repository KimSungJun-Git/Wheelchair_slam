import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, LaserScan
from geometry_msgs.msg import Twist
from cv_bridge import CvBridge
import cv2
import numpy as np
from rclpy.qos import qos_profile_sensor_data

class PrecisionDockingNode(Node):
    def __init__(self):
        super().__init__('precision_docking_node')
        self.publisher_ = self.create_publisher(Twist, 'cmd_vel', 10)
        self.image_subscription = self.create_subscription(Image, '/camera/image_raw', self.image_callback, qos_profile_sensor_data)
        self.scan_subscription = self.create_subscription(LaserScan, '/scan', self.scan_callback, qos_profile_sensor_data)
        self.bridge = CvBridge()
        
        self.state = 0  
        self.state_start_time = self.get_clock().now()
        self.get_logger().info("🎯 [State 0] 파란색(침대 모서리)을 정중앙에 맞추며 0.8m 앞까지 접근합니다!")

    def change_state(self, new_state, msg):
        self.state = new_state
        self.state_start_time = self.get_clock().now()
        self.get_logger().info(msg)

    def get_valid_dist(self, ranges, index):
        d = ranges[index]
        if np.isinf(d) or np.isnan(d) or d == 0.0:
            return 3.0
        return d

    def scan_callback(self, msg):
        if self.state == 0: return

        twist = Twist()
        now = self.get_clock().now()
        elapsed = (now.nanoseconds - self.state_start_time.nanoseconds) / 1e9

        # 🟡 [State 1] 우측으로 90도 회전 (수직 만들기)
        if self.state == 1:
            # 0.5 rad/s 로 3.14초 돌면 정확히 90도(1.57 rad)
            if elapsed < 3.14:
                twist.angular.z = -0.5
            else:
                self.change_state(2, "➡️ [State 2] 수직 각도 형성! 침대 옆 빈 공간으로 0.5m 이동합니다.")

        # 🟢 [State 2] 침대 옆 빈 공간으로 0.5m 직진
        elif self.state == 2:
            if elapsed < 2.5: # 0.2 m/s 로 2.5초 = 0.5m
                twist.linear.x = 0.2
            else:
                self.change_state(3, "🔄 [State 3] 엉덩이를 침대 쪽으로 돌리기 위해 우측 90도 추가 회전!")

        # 🔵 [State 3] 우측으로 90도 추가 회전 (총 180도 뒤돌기 완료)
        elif self.state == 3:
            if elapsed < 3.14:
                twist.angular.z = -0.5
            else:
                self.change_state(4, "📐 [State 4] 라이다 수직 칼각 정렬 시작! (오차 확인 중)")

        # 🟠 [State 4] 라이다로 뒷벽(침대)과 완벽한 90도 맞추기
        elif self.state == 4:
            dist_165 = self.get_valid_dist(msg.ranges, 165)
            dist_195 = self.get_valid_dist(msg.ranges, 195)
            error = dist_165 - dist_195
            
            # ⭐️ 지워졌던 라이다 오차 로그 복구!
            self.get_logger().info(f"📐 [라이다] 수직 교정 중... 양쪽 오차: {error:.3f}m")
            
            if abs(error) < 0.015:  
                self.change_state(5, "🚙 [State 5] 칼각 정렬 완료! 엉덩이로 밀어 넣습니다!")
            else:
                # ⭐️ 조향 최고 속도 제한 (-0.2 ~ 0.2) -> 갑자기 확 도는 현상 방지!
                angular_speed = float(error) * 1.5
                twist.angular.z = max(-0.2, min(0.2, angular_speed))

        # 🔴 [State 5] 대망의 후진 주차
        elif self.state == 5:
            dist_180 = self.get_valid_dist(msg.ranges, 180)
            self.get_logger().info(f"🚙 [후진 중] 뒷벽까지 남은 거리: {dist_180:.2f}m")
            
            if dist_180 > 0.4: # 벽과 40cm 남을 때까지 후진
                twist.linear.x = -0.15
            else:
                self.change_state(6, "🎉 [State 6] 완벽한 평행주차 완료!! 사이드 브레이크 체결!")

        elif self.state == 6:
            twist.linear.x = 0.0
            twist.angular.z = 0.0

        self.publisher_.publish(twist)

    def image_callback(self, msg):
        cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")
        hsv = cv2.cvtColor(cv_image, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array([100, 150, 0]), np.array([140, 255, 255]))
        contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        twist = Twist()

        if self.state == 0:
            if len(contours) > 0:
                c = max(contours, key=cv2.contourArea)
                M = cv2.moments(c)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    
                    # 다시 파란색을 정중앙(320)에 맞춥니다!
                    error = 320 - cx 
                    
                    x, y, w, h = cv2.boundingRect(c)
                    cv2.rectangle(cv_image, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    camera_dist_m = 237.3 / w

                    # ⭐️ 지워졌던 카메라 오차 로그 복구!
                    self.get_logger().info(f"🟦 [카메라] 중앙 정렬 중... 픽셀오차: {error}px | 남은거리: {camera_dist_m:.2f}m")

                    # ⭐️ 조향 최고 속도 제한 (-0.3 ~ 0.3) -> 덜컹거림 방지!
                    if abs(error) > 10:  
                        angular_speed = float(error) * 0.002
                        twist.angular.z = max(-0.3, min(0.3, angular_speed))
                    else:               
                        twist.angular.z = 0.0
                    
                    # 거리가 0.8m가 될 때까지 서서히 다가갑니다.
                    if camera_dist_m > 0.8:
                        twist.linear.x = 0.15
                    else:
                        twist.linear.x = 0.0
                        twist.angular.z = 0.0
                        self.change_state(1, "🔄 [State 1] 0.8m 앞 도달! 수직을 만들기 위해 90도 우회전합니다!")
            else:
                twist.angular.z = 0.3 
                self.get_logger().info("👀 [카메라] 파란색 탐색 중...")

            self.publisher_.publish(twist)

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