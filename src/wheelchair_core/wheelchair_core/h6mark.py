#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan
from apriltag_msgs.msg import AprilTagDetectionArray
import math

class PrecisionDockingNode(Node):
    def __init__(self, target_bed_id=0):
        super().__init__('precision_docking_node')
        self.target_id = target_bed_id 
        self.publisher_ = self.create_publisher(Twist, 'cmd_vel', 10)
        self.scan_sub = self.create_subscription(LaserScan, '/scan', self.scan_callback, 10)
        self.tag_sub = self.create_subscription(AprilTagDetectionArray, '/detections', self.tag_callback, 10)
        
        self.front_distance = 999.0  
        self.tag_x = None            # 🌟 이제 타겟 X 좌표는 "마커 오른쪽 50cm" 입니다.
        self.tag_dist = 999.0        
        self.image_center_x = 320.0  
        self.is_docking_complete = False
        
        # 0.1초마다 주차 상태를 확인하고 운전하는 타이머
        self.timer = self.create_timer(0.1, self.control_loop)
        
        self.get_logger().info(f"🚀 AprilTag 오른쪽 평행 주차 시작! 타겟 ID: {self.target_id}")

    def scan_callback(self, msg):
        if msg.ranges[0] != float('inf'):
            self.front_distance = msg.ranges[0]

    def tag_callback(self, msg):
        found_target = False 
        for detection in msg.detections:
            if detection.id == self.target_id:
                # 🌟 [오른쪽 평행 주차 핵심 로직] 🌟
                c = detection.corners
                width_px = abs(c[1].x - c[0].x)
                if width_px > 0:
                    tag_right_edge_x = (c[1].x + c[2].x) / 2
                    offset_50cm_px = 0.50 * (width_px / 0.15) # 🌟 50cm 오프셋
                    self.tag_x = tag_right_edge_x + offset_50cm_px # 🌟 타겟 X 좌표 변경!
                    self.tag_dist = 45.0 / width_px 
                    found_target = True
                break
        if not found_target:
            self.tag_x = None

    def control_loop(self):
        if self.is_docking_complete: return
        twist = Twist()

        # 🛑 1. 최종 정지 조건 (더 깊숙이 들어가기)
        # 옆 기둥(마커)과의 거리가 0.4m(40cm)보다 가까워지거나, 
        # 라이다 센서가 앞의 장애물을 감지하면 정지
        if (self.tag_x is not None and self.tag_dist < 0.40) or self.front_distance < 0.25:
            self.get_logger().info(f"✅ 옆면 주차 완료! 거리: {self.tag_dist:.2f}m")
            twist.linear.x = 0.0
            twist.angular.z = 0.0
            self.publisher_.publish(twist)
            self.is_docking_complete = True
            return

        # 🔍 2. 마커를 놓쳤을 때 (옆으로 비껴가느라 마커가 시야에서 빨리 사라짐)
        if self.tag_x is None:
            # 이미 근처(1.2m)라면 멈추지 말고 '마지막 각도'로 1초 더 밀고 들어가기
            if self.front_distance < 1.2:
                self.get_logger().info("🙈 타겟 지점 진입 중... (사각지대)")
                twist.linear.x = 0.12  # 속도를 조금 더 올려서 확실히 진입
                twist.angular.z = 0.0
            else:
                twist.angular.z = 0.2 # 탐색 회전
            self.publisher_.publish(twist)
            return

        # 🎯 3. 유도 주행 (마커 옆 50cm 지점을 향해)
        error_x = self.image_center_x - self.tag_x 
        turn_speed = error_x * 0.0025
        
        # 방향이 어느 정도 맞으면(error_x가 작으면) 더 자신 있게 직진!
        if abs(error_x) < 50:
            twist.linear.x = 0.15  # 속도 업!
        else:
            twist.linear.x = 0.08  # 조심조심 정렬
            
        twist.angular.z = max(min(turn_speed, 0.4), -0.4)
        self.publisher_.publish(twist)

def main(args=None):
    rclpy.init(args=args)
    node = PrecisionDockingNode(target_bed_id=0)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()