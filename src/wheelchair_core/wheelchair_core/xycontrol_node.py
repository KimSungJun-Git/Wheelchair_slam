#!/usr/bin/env python3
import math
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, PointStamped
from std_msgs.msg import Float32
from nav_msgs.msg import Odometry

class State:
    SEARCHING = 'SEARCHING'
    DOCKING   = 'DOCKING'
    COMPLETE  = 'COMPLETE'

class DockingControlNode(Node):
    ARRIVE_DIST      = 0.40   # 주차 완료 거리
    LIDAR_STOP_DIST  = 0.25   # 전방 긴급 정지
    TUBE_RADIUS      = 0.90   # ⭐️ 가상 튜브 반경 (60cm 내로 접근하면 밀어냄)
    DRIVE_SPEED      = 0.15

    def __init__(self):
        super().__init__('docking_control_node')
        self.state = State.SEARCHING
        
        # 로봇의 가상 좌표계(Odometry) 현재 위치
        self.odom_x, self.odom_y, self.odom_yaw = 0.0, 0.0, 0.0
        self.front_dist = 999.0

        # 기억해둘 절대 좌표 (목표점과 장애물 튜브 중심)
        self.goal_x, self.goal_y = 0.0, 0.0
        self.obs_x, self.obs_y   = 0.0, 0.0
        self.target_locked = False

        self.create_subscription(Odometry, '/odom', self._odom_cb, 10)
        self.create_subscription(PointStamped, '/tag/parking_target', self._target_cb, 10)
        self.create_subscription(PointStamped, '/tag/raw_tag', self._tag_cb, 10)
        self.create_subscription(Float32, '/lidar/front_dist', self._front_cb, 10)
        
        self._pub_vel = self.create_publisher(Twist, 'cmd_vel', 10)
        self.create_timer(0.1, self._loop)

        self.get_logger().info('DockingControlNode 준비 (가상 좌표계 & 튜브 회피 모드)')

    def _front_cb(self, msg: Float32): self.front_dist = msg.data

    # ⭐️ 로봇의 현재 절대 좌표 업데이트
    def _odom_cb(self, msg: Odometry):
        self.odom_x = msg.pose.pose.position.x
        self.odom_y = msg.pose.pose.position.y
        q = msg.pose.pose.orientation
        # 쿼터니언을 Euler Yaw 각도로 변환
        siny_cosp = 2 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
        self.odom_yaw = math.atan2(siny_cosp, cosy_cosp)

    # 카메라 좌표(상대)를 오도메트리 좌표(절대)로 변환해 메모리에 저장
    def _target_cb(self, msg: PointStamped):
        bx, by = msg.point.z, -msg.point.x  # 카메라 프레임 -> 로봇 베이스 프레임 변환
        self.goal_x = self.odom_x + bx * math.cos(self.odom_yaw) - by * math.sin(self.odom_yaw)
        self.goal_y = self.odom_y + bx * math.sin(self.odom_yaw) + by * math.cos(self.odom_yaw)
        self.target_locked = True

    def _tag_cb(self, msg: PointStamped):
        bx, by = msg.point.z, -msg.point.x
        self.obs_x = self.odom_x + bx * math.cos(self.odom_yaw) - by * math.sin(self.odom_yaw)

    def _loop(self):
        if self.state == State.COMPLETE: return

        if self.front_dist < self.LIDAR_STOP_DIST:
            self.get_logger().warn(f'⚠️ 전방 장애물 {self.front_dist:.2f}m → 정지')
            self._pub(0.0, 0.0)
            return

        if self.state == State.SEARCHING:
            if not self.target_locked:
                self._pub(0.0, 0.25) # 탐색 회전
            else:
                self.get_logger().info('🗺️ 가상 좌표계 도면 스캔 완료! 도킹 시작')
                self.state = State.DOCKING

        elif self.state == State.DOCKING:
            self._do_docking()

    def _do_docking(self):
        # 1. 목표가 당기는 힘 (Attractive Vector)
        gx, gy = self.goal_x - self.odom_x, self.goal_y - self.odom_y
        dist_goal = math.hypot(gx, gy)
        
        if dist_goal < self.ARRIVE_DIST:
            self._pub(0.0, 0.0)
            self.state = State.COMPLETE
            self.get_logger().info(f'🏁 가상 좌표계 목표 지점 도달! 주차 완료')
            return

        ux_goal, uy_goal = gx / max(dist_goal, 0.01), gy / max(dist_goal, 0.01)

        # 2. 기둥(마커)의 가상 튜브가 밀어내는 힘 (Repulsive Vector)
        ox, oy = self.odom_x - self.obs_x, self.odom_y - self.obs_y
        dist_obs = math.hypot(ox, oy)
        
        ux_repel, uy_repel = 0.0, 0.0
        # 로봇이 튜브 반경(60cm) 안으로 들어오면 강하게 밀어냄
        if dist_obs < self.TUBE_RADIUS and dist_obs > 0.05:
            push_force = (self.TUBE_RADIUS - dist_obs) / self.TUBE_RADIUS
            ux_repel = (ox / dist_obs) * push_force * 2.0  # 밀어내는 강도 증폭
            uy_repel = (oy / dist_obs) * push_force * 2.0

        # 3. 힘 합산 및 조향각 계산
        vx = ux_goal + ux_repel
        vy = uy_goal + uy_repel
        
        desired_yaw = math.atan2(vy, vx)
        yaw_err = desired_yaw - self.odom_yaw
        yaw_err = (yaw_err + math.pi) % (2 * math.pi) - math.pi # -180~180 정규화

        # 4. 주행 명령 하달
        ang_vel = max(-0.5, min(0.5, yaw_err * 1.2))
        
        # 커브를 강하게 틀어야 하거나 목표 지점에 거의 다 왔으면 속도 감속
        lin_vel = self.DRIVE_SPEED
        if abs(yaw_err) > 0.4 or dist_goal < 0.8:
            lin_vel *= 0.5

        self._pub(lin_vel, ang_vel)

        status_msg = f'목표까지 {dist_goal:.2f}m'
        if ux_repel != 0:
            status_msg += f' | 🛡️ 튜브 회피 중 (거리 {dist_obs:.2f}m)'
        self.get_logger().info(status_msg)

    def _pub(self, lin: float, ang: float):
        t = Twist()
        t.linear.x, t.angular.z = float(lin), float(ang)
        self._pub_vel.publish(t)

def main(args=None):
    rclpy.init(args=args)
    rclpy.spin(DockingControlNode())
    rclpy.shutdown()

if __name__ == '__main__':
    main()