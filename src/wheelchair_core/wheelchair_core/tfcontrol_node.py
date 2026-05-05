#!/usr/bin/env python3
import math
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, PointStamped
from std_msgs.msg import Float32
from nav_msgs.msg import Odometry

# ⭐️ TF2 라이브러리 추가
import tf2_ros
import tf2_geometry_msgs

class State:
    SEARCHING = 'SEARCHING'
    DOCKING   = 'DOCKING'
    COMPLETE  = 'COMPLETE'

class DockingControlNode(Node):
    def __init__(self):
        super().__init__('docking_control_node')
        
        # ⭐️ ROS2 파라미터 선언
        self.declare_parameter('tube_radius', 0.60)     # 가상 튜브 반경
        self.declare_parameter('drive_speed', 0.15)     # 주행 속도
        self.declare_parameter('arrive_dist', 0.40)     # 주차 완료 인정 거리
        self.declare_parameter('lidar_stop_dist', 0.25) # 긴급 정지 거리

        self.state = State.SEARCHING
        self.odom_x, self.odom_y, self.odom_yaw = 0.0, 0.0, 0.0
        self.front_dist = 999.0
        self.goal_x, self.goal_y = 0.0, 0.0
        self.obs_x, self.obs_y   = 0.0, 0.0
        self.target_locked = False

        # ⭐️ TF2 Buffer 및 Listener 초기화
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)

        self.create_subscription(Odometry, '/odom', self._odom_cb, 10)
        self.create_subscription(PointStamped, '/tag/parking_target', self._target_cb, 10)
        self.create_subscription(PointStamped, '/tag/raw_tag', self._tag_cb, 10)
        self.create_subscription(Float32, '/lidar/front_dist', self._front_cb, 10)
        
        self._pub_vel = self.create_publisher(Twist, 'cmd_vel', 10)
        self.create_timer(0.1, self._loop)

        self.get_logger().info('DockingControlNode 준비 완료 (TF2 & 파라미터 적용)')

    def _front_cb(self, msg: Float32): self.front_dist = msg.data

    def _odom_cb(self, msg: Odometry):
        self.odom_x = msg.pose.pose.position.x
        self.odom_y = msg.pose.pose.position.y
        q = msg.pose.pose.orientation
        siny_cosp = 2 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
        self.odom_yaw = math.atan2(siny_cosp, cosy_cosp)

    # ⭐️ TF2를 이용한 좌표계 자동 변환
    def _transform_point_to_odom(self, msg: PointStamped):
        try:
            # 카메라 프레임 -> odom 프레임 변환 정보 가져오기
            t = self.tf_buffer.lookup_transform(
                'odom', 
                msg.header.frame_id, 
                rclpy.time.Time(), 
                timeout=rclpy.duration.Duration(seconds=0.1)
            )
            # 수신한 PointStamped를 odom 좌표계로 변환
            return tf2_geometry_msgs.do_transform_point(msg, t)
        except tf2_ros.TransformException as ex:
            self.get_logger().debug(f'TF 변환 대기 중... : {ex}')
            return None

    def _target_cb(self, msg: PointStamped):
        odom_msg = self._transform_point_to_odom(msg)
        if odom_msg:
            self.goal_x = odom_msg.point.x
            self.goal_y = odom_msg.point.y
            self.target_locked = True

    def _tag_cb(self, msg: PointStamped):
        odom_msg = self._transform_point_to_odom(msg)
        if odom_msg:
            self.obs_x = odom_msg.point.x
            self.obs_y = odom_msg.point.y

    def _loop(self):
        if self.state == State.COMPLETE: return

        lidar_stop_dist = self.get_parameter('lidar_stop_dist').value
        if self.front_dist < lidar_stop_dist:
            self.get_logger().warn(f'⚠️ 전방 장애물 {self.front_dist:.2f}m → 정지')
            self._pub(0.0, 0.0)
            return

        if self.state == State.SEARCHING:
            if not self.target_locked:
                self._pub(0.0, 0.25)
            else:
                self.get_logger().info('🗺️ 가상 좌표계 도면 스캔 완료! 도킹 시작')
                self.state = State.DOCKING

        elif self.state == State.DOCKING:
            self._do_docking()

    def _do_docking(self):
        tube_radius = self.get_parameter('tube_radius').value
        arrive_dist = self.get_parameter('arrive_dist').value
        drive_speed = self.get_parameter('drive_speed').value

        gx, gy = self.goal_x - self.odom_x, self.goal_y - self.odom_y
        dist_goal = math.hypot(gx, gy)
        
        if dist_goal < arrive_dist:
            self._pub(0.0, 0.0)
            self.state = State.COMPLETE
            self.get_logger().info('🏁 주차 완료!')
            return

        ux_goal, uy_goal = gx / max(dist_goal, 0.01), gy / max(dist_goal, 0.01)

        ox, oy = self.odom_x - self.obs_x, self.odom_y - self.obs_y
        dist_obs = math.hypot(ox, oy)
        
        ux_repel, uy_repel = 0.0, 0.0
        if 0.05 < dist_obs < tube_radius:
            push_force = (tube_radius - dist_obs) / tube_radius
            ux_repel = (ox / dist_obs) * push_force * 2.0
            uy_repel = (oy / dist_obs) * push_force * 2.0

        vx = ux_goal + ux_repel
        vy = uy_goal + uy_repel
        
        desired_yaw = math.atan2(vy, vx)
        yaw_err = desired_yaw - self.odom_yaw
        yaw_err = (yaw_err + math.pi) % (2 * math.pi) - math.pi

        ang_vel = max(-0.5, min(0.5, yaw_err * 1.2))
        
        lin_vel = drive_speed
        if abs(yaw_err) > 0.4 or dist_goal < 0.8:
            lin_vel *= 0.5

        self._pub(lin_vel, ang_vel)

        status_msg = f'목표까지 {dist_goal:.2f}m'
        if ux_repel != 0:
            status_msg += f' | 🛡️ 반경 {tube_radius}m 튜브 회피 중'
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