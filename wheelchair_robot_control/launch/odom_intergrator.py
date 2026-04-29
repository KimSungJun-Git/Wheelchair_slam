#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
import math

class OdomIntegrator(Node):
    def __init__(self):
        super().__init__('odom_integrator')
        # Stella의 odom을 구독
        self.sub = self.create_subscription(Odometry, '/odom', self._cb, 10)
        # 새로 계산한 위치 정보를 발행
        self.pub = self.create_publisher(Odometry, '/odom_refined', 10)
        
        self.x, self.y, self.yaw = 0.0, 0.0, 0.0
        self.last_time = None

    def _cb(self, msg):
        curr_time = self.get_clock().now()
        if self.last_time is None:
            self.last_time = curr_time
            return

        # 시간 간격 계산 (dt)
        dt = (curr_time - self.last_time).nanoseconds / 1e9
        self.last_time = curr_time

        # 1. 속도 정보 가져오기
        vx = msg.twist.twist.linear.x
        v_yaw = msg.twist.twist.angular.z

        # 2. 각도 업데이트 (IMU 값이 들어오는 방향에 따라 조정 가능)
        # 만약 msg.pose.pose.orientation이 살아있다면 그걸 그대로 써도 됩니다.
        self.yaw += v_yaw * dt

        # 3. 현재 각도 방향으로 위치 적분 (이동 거리 계산)
        self.x += vx * math.cos(self.yaw) * dt
        self.y += vx * math.sin(self.yaw) * dt

        # 4. 새로운 Odometry 메시지 생성 및 발행
        new_msg = msg
        new_msg.header.frame_id = 'odom'
        new_msg.pose.pose.position.x = self.x
        new_msg.pose.pose.position.y = self.y
        # Quaternion 변환 생략 (기존 yaw 값 활용)
        
        self.pub.publish(new_msg)

def main():
    rclpy.init()
    rclpy.spin(OdomIntegrator())
    rclpy.shutdown()

if __name__ == '__main__':
    main()