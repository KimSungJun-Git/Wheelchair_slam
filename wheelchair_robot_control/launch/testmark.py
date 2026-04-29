#!/usr/bin/env python3

import math
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from tf2_ros import TransformException
from tf2_ros.buffer import Buffer
from tf2_ros.transform_listener import TransformListener

class State:
    ALIGN_MARKER  = 'ALIGN_MARKER'
    TURN_LATERAL  = 'TURN_LATERAL'  # 1. 옆으로 가기 위해 90도 회전
    DRIVE_LATERAL = 'DRIVE_LATERAL' # 2. 옆으로 직진
    TURN_BACK     = 'TURN_BACK'     # 3. 원래 방향으로 복귀
    COMPLETE      = 'COMPLETE'

class MarkerSequenceControlNode(Node):
    def __init__(self):
        super().__init__('marker_sequence_control_node')
        
        # 주행 속도 파라 선언
        self.declare_parameter('drive_speed', 0.12)
        
        # 상태 및 좌표 변수
        self.state = State.ALIGN_MARKER
        self.odom_x, self.odom_y, self.odom_yaw = 0.0, 0.0, 0.0
        
        self.goal_x, self.goal_y = 0.0, 0.0
        self.start_x, self.start_y = 0.0, 0.0
        self.base_yaw = 0.0  
        self.lat_yaw = 0.0   
        
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        
        self.create_subscription(Odometry, '/odom_refined', self._odom_cb, 10)
        self._pub_vel = self.create_publisher(Twist, '/cmd_vel', 10)
        
        self.stop_count = 0
        self.prev_dist = 999.0
        self.create_timer(0.1, self._loop)
        
        self.get_logger().info('🚀 [하드웨어 최적화] 마커 시퀀스 제어 시작!')

    def _odom_cb(self, msg: Odometry):
        self.odom_x = msg.pose.pose.position.x
        self.odom_y = msg.pose.pose.position.y
        q = msg.pose.pose.orientation
        self.odom_yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))

    def _normalize_angle(self, angle):
        """각도를 -pi ~ pi 사이로 보정하는 함수"""
        return math.atan2(math.sin(angle), math.cos(angle))

    def _loop(self):
        if self.state == State.COMPLETE: 
            return
            
        d_speed = self.get_parameter('drive_speed').value

        # ---------------------------------------------------------
        # 0. 마커 정렬 (초기 1자 맞추기)
        # ---------------------------------------------------------
        if self.state == State.ALIGN_MARKER:
            try:
                t = self.tf_buffer.lookup_transform('camera', 'tag16h5:0', rclpy.time.Time())
            except TransformException:
                self.get_logger().info('마커를 찾는 중...', throttle_duration_sec=1.0)
                self._pub(0.0, 0.0)
                return

            q = t.transform.rotation
            tilt_error = math.atan2(2.0 * (q.x * q.z + q.y * q.w), -(1.0 - 2.0 * (q.x * q.x + q.y * q.y)))

            if abs(tilt_error) > 0.05: # 약 2.8도 오차 허용
                self.stop_count = 0
                
                # ⭐️ 제일 처음 잘 작동했던 상태로 복구 (마이너스 제거, 속도 제한 정상화)
                self._pub(0.0, max(-0.25, min(0.25, tilt_error * 0.3)))
                
                self.get_logger().info(f'기울기 교정 중... 오차: {math.degrees(tilt_error):.1f}도')
            else:
                self._pub(0.0, 0.0)
                self.stop_count += 1
                
                if self.stop_count > 10:
                    self.get_logger().info('✅ 평행 정렬 완료! 90도 회전을 준비합니다.')
                    self.base_yaw = self.odom_yaw
                    
                    # 90도 회전 각도 계산 (왼쪽 방향)
                    self.lat_yaw = self._normalize_angle(self.base_yaw + (math.pi / 2.0))
                    
                    # 목표 절대 좌표(30cm 지점) 계산
                    #self.goal_x = self.odom_x + 0.10 * math.cos(self.lat_yaw)
                    #self.goal_y = self.odom_y + 0.10 * math.sin(self.lat_yaw)
                    
                    self.state = State.TURN_LATERAL

        # ---------------------------------------------------------
        # 1. 측면 90도 회전
        # ---------------------------------------------------------
        # ---------------------------------------------------------
        # 1. 측면 90도 회전
        # ---------------------------------------------------------
        elif self.state == State.TURN_LATERAL:
            remaining = abs(self._normalize_angle(self.lat_yaw - self.odom_yaw))
            self.get_logger().info(f'🔄 90도 회전 중... 남은 오차: {math.degrees(remaining):.1f}도', throttle_duration_sec=0.5)
            
            if self._turn_to(self.lat_yaw):
                self.get_logger().info('✅ 1단계: 측면 정렬 회전 완료')
                
                # ⭐️ 직진을 시작하기 직전의 위치를 기준점(0cm)으로 저장합니다.
                self.start_x = self.odom_x
                self.start_y = self.odom_y
                self.state = State.DRIVE_LATERAL

        # ---------------------------------------------------------
        # 2. 10cm 측면 직진 (순수 이동 거리 측정 방식)
        # ---------------------------------------------------------
        elif self.state == State.DRIVE_LATERAL:
            # 시작점으로부터 내가 얼마나 이동했는지 계산
            moved_dist = math.hypot(self.odom_x - self.start_x, self.odom_y - self.start_y)
            
            # 터미널에서 이동 거리를 실시간으로 확인할 수 있도록 로그 추가
            self.get_logger().info(f'➡️ 직진 중... 이동 거리: {moved_dist:.3f}m / 목표: 0.100m', throttle_duration_sec=0.2)
            
            if moved_dist >= 0.10: # 10cm (0.10m) 이상 이동했으면 즉시 정지
                self._pub(0.0, 0.0)
                self.get_logger().info('✅ 2단계: 10cm 이동 완료!')
                self.state = State.TURN_BACK
            else:
                self._drive_straight(self.lat_yaw, d_speed)

        # ---------------------------------------------------------
        # 3. 초기 방향으로 복귀
        # ---------------------------------------------------------
        elif self.state == State.TURN_BACK:
            remaining = abs(self._normalize_angle(self.base_yaw - self.odom_yaw))
            self.get_logger().info(f'🔄 원복 회전 중... 남은 오차: {math.degrees(remaining):.1f}도', throttle_duration_sec=0.5)
            
            if self._turn_to(self.base_yaw):
                self.get_logger().info('🏁 [성공] 모든 시퀀스 종료!')
                self.state = State.COMPLETE

    # ==========================================================
    # 하드웨어 최적화 헬퍼 함수
    # ==========================================================
    def _turn_to(self, target_yaw):
        err = self._normalize_angle(target_yaw - self.odom_yaw)
        
        if abs(err) < 0.1: # 약 5.7도 이내
            self._pub(0.0, 0.0)
            return True
            
        # 오도메트리 기반 제어에서는 모터 방향이 뒤집혀 있으므로 -err 유지
        self._pub(0.0, max(-0.25, min(0.25, -err * 0.4)))
        return False

    def _drive_straight(self, target_yaw, speed):
        err = self._normalize_angle(target_yaw - self.odom_yaw)
        # 직진 중 조향 보정도 방향 뒤집힘 유지
        self._pub(speed, max(-0.15, min(0.15, -err * 0.3)))

    def _pub(self, lin: float, ang: float):
        t = Twist()
        t.linear.x = float(lin)
        t.angular.z = float(ang)
        self._pub_vel.publish(t)

def main(args=None):
    rclpy.init(args=args)
    node = MarkerSequenceControlNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()