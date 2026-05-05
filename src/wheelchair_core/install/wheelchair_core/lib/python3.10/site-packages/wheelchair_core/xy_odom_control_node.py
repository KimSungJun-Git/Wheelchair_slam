#cococo.py
#!/usr/bin/env python3
import math
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, PointStamped
from std_msgs.msg import Float32
from nav_msgs.msg import Odometry

class State:
    SEARCHING     = 'SEARCHING'
    TURN_LATERAL  = 'TURN_LATERAL'  # 1. 옆으로 가기 위해 90도 회전
    DRIVE_LATERAL = 'DRIVE_LATERAL' # 2. 옆으로 직진
    TURN_REVERSE  = 'TURN_REVERSE'  # 3. ⭐️ 후진을 위해 마커를 등지도록 180도 회전
    DRIVE_BACK    = 'DRIVE_BACK'    # 4. ⭐️ 최종 후진 진입
    COMPLETE      = 'COMPLETE'

class DockingControlNode(Node):
    def __init__(self):
        super().__init__('docking_control_node')
        self.create_subscription(Odometry, '/odom', self._odom_cb, 10)
        self.create_subscription(PointStamped, '/tag/raw_tag', self._tag_cb, 10)
        self.create_subscription(PointStamped, '/tag/forward_dir', self._fwd_cb, 10)
        self.create_subscription(PointStamped, '/tag/parking_target', self._target_cb, 10)
        self.create_subscription(Float32, '/lidar/front_dist', self._front_cb, 10)
        
        self._pub_vel = self.create_publisher(Twist, 'cmd_vel', 10)
        self.create_timer(0.1, self._loop)

        self.get_logger().info('DockingControlNode: 📐 0번(파랑) 기준 후진 직각 주차 시작')
        
        # 파라미터 선언
        self.declare_parameter('drive_speed', 0.12)       # 후진은 조금 더 천천히
        self.declare_parameter('lidar_stop_dist', 0.20)

        self.state = State.SEARCHING
        self.odom_x, self.odom_y, self.odom_yaw = 0.0, 0.0, 0.0
        self.front_dist = 999.0

        self.goal_x, self.goal_y = 0.0, 0.0
        self.tag_world_x, self.tag_world_y = 0.0, 0.0
        self.fwd_world_x, self.fwd_world_y = 0.0, 0.0
        
        self.got_tag = False
        self.got_fwd = False
        self.target_locked = False
        
        self.base_yaw = 0.0  # 벽면 정면(마커 방향) 각도
        self.lat_yaw = 0.0   # 측면 이동 각도


    def _front_cb(self, msg: Float32): 
        self.front_dist = msg.data

    def _odom_cb(self, msg: Odometry):
        self.odom_x = msg.pose.pose.position.x
        self.odom_y = msg.pose.pose.position.y
        q = msg.pose.pose.orientation
        self.odom_yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))

    def _tag_cb(self, msg: PointStamped):
        bx, by = msg.point.z, -msg.point.x
        self.tag_world_x = self.odom_x + bx * math.cos(self.odom_yaw) - by * math.sin(self.odom_yaw)
        self.tag_world_y = self.odom_y + bx * math.sin(self.odom_yaw) + by * math.cos(self.odom_yaw)
        self.got_tag = True

    def _fwd_cb(self, msg: PointStamped):
        fx, fy = msg.point.z, -msg.point.x
        self.fwd_world_x = self.odom_x + fx * math.cos(self.odom_yaw) - fy * math.sin(self.odom_yaw)
        self.fwd_world_y = self.odom_y + fx * math.sin(self.odom_yaw) + fy * math.cos(self.odom_yaw)
        self.got_fwd = True

    def _target_cb(self, msg: PointStamped):
        bx, by = msg.point.z, -msg.point.x
        # ⭐️ goal은 카메라 노드가 준 위치(30cm 지점)를 그대로 사용
        self.goal_x = self.odom_x + bx * math.cos(self.odom_yaw) - by * math.sin(self.odom_yaw)
        self.goal_y = self.odom_y + bx * math.sin(self.odom_yaw) + by * math.cos(self.odom_yaw)
        
        if not self.target_locked and self.got_tag and self.got_fwd:
            self.target_locked = True
            marker_yaw = math.atan2(self.fwd_world_y - self.tag_world_y, self.fwd_world_x - self.tag_world_x)
            self.base_yaw = (marker_yaw + math.pi) % (2 * math.pi) - math.pi
            
            # 파란색 0번 기준으로 옆으로 얼마나 갈지 판별
            dx, dy = self.goal_x - self.tag_world_x, self.goal_y - self.tag_world_y
            target_angle = math.atan2(dy, dx)
            diff = (target_angle - marker_yaw + math.pi) % (2 * math.pi) - math.pi
            
            if diff > 0: self.lat_yaw = self.base_yaw + (math.pi / 2.0)
            else:        self.lat_yaw = self.base_yaw - (math.pi / 2.0)
            self.get_logger().info(f'✅ 마커 각도 확인: {math.degrees(self.base_yaw):.1f}도')

    def _loop(self):
        if self.state == State.COMPLETE: return
        
        d_speed = self.get_parameter('drive_speed').value
        stop_dist = self.get_parameter('lidar_stop_dist').value

        # 후진 중에는 라이다가 앞을 보므로 긴급 정지 로직을 상황에 맞춰 조정 (현재는 유지)
        if self.front_dist < stop_dist:
            self._pub(0.0, 0.0)
            return

        if self.state == State.SEARCHING:
            if not self.target_locked: self._pub(0.0, 0.25)
            else: self.state = State.TURN_LATERAL

        elif self.state == State.TURN_LATERAL:
            if self._turn_to(self.lat_yaw):
                self.get_logger().info('✅ 1단계: 측면 정렬 회전 완료')
                self.state = State.DRIVE_LATERAL

        elif self.state == State.DRIVE_LATERAL:
            err_lat = -(self.goal_x - self.odom_x) * math.sin(self.base_yaw) + (self.goal_y - self.odom_y) * math.cos(self.base_yaw)
            if abs(err_lat) < 0.05:
                self._pub(0.0, 0.0)
                self.state = State.TURN_REVERSE
            else:
                self._drive_straight(self.lat_yaw, d_speed)

        elif self.state == State.TURN_REVERSE:
            # ⭐️ 마커를 등지도록 180도 회전 (base_yaw + 180도)
            rev_yaw = (self.base_yaw + math.pi) % (2 * math.pi) - math.pi
            if self._turn_to(rev_yaw):
                self.get_logger().info('✅ 2단계: 후진 준비(180도 회전) 완료')
                self.state = State.DRIVE_BACK

        elif self.state == State.DRIVE_BACK:
            # base_yaw(마커 방향) 기준으로 앞뒤 거리 계산
            err_fwd = (self.goal_x - self.odom_x) * math.cos(self.base_yaw) + (self.goal_y - self.odom_y) * math.sin(self.base_yaw)
            
            if abs(err_fwd) < 0.05:
                self._pub(0.0, 0.0)
                self.get_logger().info('🏁 [성공] 0번 마커 30cm 지점 후진 주차 완료!')
                self.state = State.COMPLETE
            else:
                # ⭐️ 마이너스 속도로 후진! 각도는 마커 반대 방향(rev_yaw) 유지
                rev_yaw = (self.base_yaw + math.pi) % (2 * math.pi) - math.pi
                self._drive_straight(rev_yaw, -d_speed)

    def _turn_to(self, target_yaw):
        err = (target_yaw - self.odom_yaw + math.pi) % (2 * math.pi) - math.pi
        if abs(err) < 0.05:
            self._pub(0.0, 0.0)
            return True
        self._pub(0.0, max(-0.4, min(0.4, err * 1.5)))
        return False

    def _drive_straight(self, target_yaw, speed):
        err = (target_yaw - self.odom_yaw + math.pi) % (2 * math.pi) - math.pi
        self._pub(speed, max(-0.2, min(0.2, err * 1.0)))

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