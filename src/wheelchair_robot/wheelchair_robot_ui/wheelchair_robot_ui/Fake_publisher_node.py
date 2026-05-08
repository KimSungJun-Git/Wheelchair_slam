#!/usr/bin/env python3
"""로봇 없이 UI 테스트용 가짜 토픽 발행 노드"""
import math
import random
import time
import json
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy

from std_msgs.msg import String, Bool
from sensor_msgs.msg import LaserScan, Range
from geometry_msgs.msg import PoseWithCovarianceStamped, Twist
from nav_msgs.msg import Odometry, OccupancyGrid


class FakePublisher(Node):
    def __init__(self):
        super().__init__('fake_publisher')

        # Publishers
        self.scan_pub = self.create_publisher(LaserScan, '/scan', 10)
        self.ultra_front_pub = self.create_publisher(Range, '/ultrasonic/range', 10)
        self.ultra_left_pub  = self.create_publisher(Range, '/ultrasonic/left',  10)
        self.ultra_right_pub = self.create_publisher(Range, '/ultrasonic/right', 10)
        self.amcl_pub = self.create_publisher(PoseWithCovarianceStamped, '/amcl_pose', 10)
        self.odom_pub = self.create_publisher(Odometry, '/odometry/filtered', 10)
        map_qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                             durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.map_pub = self.create_publisher(OccupancyGrid, '/map', map_qos)
        self.mode_pub = self.create_publisher(String, '/robot_mode', 10)
        self.safety_alert_pub = self.create_publisher(String, '/safety_alert', 10)
        self.sensor_health_pub = self.create_publisher(String, '/sensor_health', 10)
        self.imu_emergency_pub = self.create_publisher(Bool, '/emergency_stop/imu', 10)
        self.loc_emergency_pub = self.create_publisher(Bool, '/emergency_stop/localization', 10)
        self.loc_status_pub = self.create_publisher(String, '/localization_status', 10)
        self.sos_pub = self.create_publisher(String, '/sos_trigger', 10)
        self.avoid_pub = self.create_publisher(String, '/avoidance_direction', 10)
        self.safety_action_pub = self.create_publisher(String, '/safety_action', 10)
        self.zone_pub = self.create_publisher(String, '/current_zone', 10)
        self.nav_status_pub = self.create_publisher(String, '/nav_status', 10)

        # Subscribers
        self.create_subscription(String, '/destination', self.on_destination, 10)
        self.create_subscription(String, '/mode_switch', self.on_mode_switch, 10)
        self.create_subscription(Twist, '/cmd_vel_teleop', self.on_cmd_vel, 10)

        self.start_time = time.time()
        self.last_scenario = None
        self.robot_x = 0.0
        self.robot_y = 0.0
        self.robot_yaw = 0.0
        self.cycle_seconds = 40

        self.publish_map_once()
        self.create_timer(0.1, self.tick_fast)
        self.create_timer(1.0, self.tick_slow)

        self.get_logger().info('🤖 가짜 발행 노드 시작. UI에서 동작 확인하세요.')
        self.get_logger().info('   시나리오는 40초 주기로 자동 순환됩니다.')

    def current_scenario(self):
        elapsed = (time.time() - self.start_time) % self.cycle_seconds
        if elapsed < 10: return 'normal'
        elif elapsed < 15: return 'obstacle_left'
        elif elapsed < 20: return 'obstacle_front'
        elif elapsed < 25: return 'imu_emergency'
        elif elapsed < 30: return 'localization_lost'
        elif elapsed < 35: return 'sensor_lost'
        else: return 'arrived'

    def tick_slow(self):
        sc = self.current_scenario()
        if sc != self.last_scenario:
            self.last_scenario = sc
            self.get_logger().info(f'▶ 시나리오 전환: {sc}')
            if sc == 'normal':
                self.safety_alert_pub.publish(String(data='obstacle_cleared'))
                self.imu_emergency_pub.publish(Bool(data=False))
                self.loc_emergency_pub.publish(Bool(data=False))
                self.loc_status_pub.publish(String(data='ok'))
                self.zone_pub.publish(String(data='일반구역'))
                self.publish_health(all_ok=True)
            elif sc == 'obstacle_left':
                self.zone_pub.publish(String(data='위험구역(주의)'))
                self.avoid_pub.publish(String(data='right'))
            elif sc == 'obstacle_front':
                self.safety_alert_pub.publish(String(data='obstacle_too_close'))
                self.zone_pub.publish(String(data='비상정지(전방 장애물)'))
                self.safety_action_pub.publish(String(
                    data=json.dumps({'source': 'lidar', 'action': 'blocked', 'reason': 'front_obstacle'})))
                self.avoid_pub.publish(String(data='blocked'))
            elif sc == 'imu_emergency':
                self.imu_emergency_pub.publish(Bool(data=True))
                self.sos_pub.publish(String(data='imu_기울기:roll=35.2,pitch=12.1'))
            elif sc == 'localization_lost':
                self.imu_emergency_pub.publish(Bool(data=False))
                self.loc_emergency_pub.publish(Bool(data=True))
                self.loc_status_pub.publish(String(data='lost'))
                self.sos_pub.publish(String(data='localization_lost'))
            elif sc == 'sensor_lost':
                self.loc_emergency_pub.publish(Bool(data=False))
                self.loc_status_pub.publish(String(data='ok'))
                self.publish_health(all_ok=False)
            elif sc == 'arrived':
                self.publish_health(all_ok=True)
                self.nav_status_pub.publish(String(data='arrived'))
                self.get_logger().info('🎉 /nav_status: arrived → UI에 도착 모달이 떠야 함')
        self.mode_pub.publish(String(data='auto'))

    def tick_fast(self):
        sc = self.current_scenario()
        if sc == 'normal':
            front, fl, fr, left, right = 2.5, 3.0, 3.0, 2.8, 2.8
        elif sc == 'obstacle_left':
            front, fl, fr, left, right = 2.0, 0.7, 2.5, 0.45, 2.5
        elif sc == 'obstacle_front':
            front, fl, fr, left, right = 0.35, 0.6, 0.6, 1.5, 1.5
        elif sc == 'sensor_lost':
            front, fl, fr, left, right = None, None, None, None, None
        else:
            front, fl, fr, left, right = 2.0, 2.5, 2.5, 2.5, 2.5
        def noise(v):
            return None if v is None else max(0.1, v + random.uniform(-0.05, 0.05))
        self.publish_scan(noise(front), noise(fl), noise(fr), noise(left), noise(right))
        self.publish_range(self.ultra_front_pub, noise(front))
        self.publish_range(self.ultra_left_pub,  noise(left))
        self.publish_range(self.ultra_right_pub, noise(right))
        elapsed = time.time() - self.start_time
        self.robot_x = 0.5 + 1.5 * math.sin(elapsed * 0.1)
        self.robot_y = 0.5 + 1.5 * math.cos(elapsed * 0.1)
        self.robot_yaw = elapsed * 0.1
        self.publish_amcl()
        self.publish_odom()

    def publish_scan(self, front, fl, fr, left, right):
        msg = LaserScan()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'laser'
        msg.angle_min = -math.pi
        msg.angle_max = math.pi
        msg.angle_increment = 2 * math.pi / 360
        msg.range_min = 0.1
        msg.range_max = 10.0
        ranges = []
        for i in range(360):
            angle_deg = -180 + i
            if -20 <= angle_deg <= 20: d = front
            elif 20 < angle_deg <= 60: d = fl
            elif 60 < angle_deg <= 100: d = left
            elif -60 <= angle_deg < -20: d = fr
            elif -100 <= angle_deg < -60: d = right
            else: d = 5.0
            ranges.append(float('inf') if d is None else float(d + random.uniform(-0.02, 0.02)))
        msg.ranges = ranges
        self.scan_pub.publish(msg)

    def publish_range(self, pub, d):
        msg = Range()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.radiation_type = Range.ULTRASOUND
        msg.field_of_view = 0.5
        msg.min_range = 0.05
        msg.max_range = 4.0
        msg.range = float(d) if d is not None else -1.0
        pub.publish(msg)

    def publish_amcl(self):
        msg = PoseWithCovarianceStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'map'
        msg.pose.pose.position.x = float(self.robot_x)
        msg.pose.pose.position.y = float(self.robot_y)
        msg.pose.pose.orientation.z = math.sin(self.robot_yaw / 2)
        msg.pose.pose.orientation.w = math.cos(self.robot_yaw / 2)
        self.amcl_pub.publish(msg)

    def publish_odom(self):
        msg = Odometry()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'odom'
        msg.child_frame_id = 'base_link'
        msg.pose.pose.position.x = float(self.robot_x)
        msg.pose.pose.position.y = float(self.robot_y)
        msg.pose.pose.orientation.z = math.sin(self.robot_yaw / 2)
        msg.pose.pose.orientation.w = math.cos(self.robot_yaw / 2)
        self.odom_pub.publish(msg)

    def publish_map_once(self):
        msg = OccupancyGrid()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'map'
        msg.info.resolution = 0.05
        msg.info.width = 200
        msg.info.height = 200
        msg.info.origin.position.x = -5.0
        msg.info.origin.position.y = -5.0
        msg.info.origin.orientation.w = 1.0
        msg.data = [0] * (200 * 200)
        self.map_pub.publish(msg)
        self.get_logger().info('🗺️  /map 발행됨 (10×10m 빈 맵)')

    def publish_health(self, all_ok=True):
        if all_ok:
            health = {'lidar': 'ok', 'imu': 'ok', 'odom': 'ok',
                      'ultrasonic_front': 'ok', 'ultrasonic_left': 'ok', 'ultrasonic_right': 'ok'}
        else:
            health = {'lidar': 'lost(2.3s)', 'imu': 'ok', 'odom': 'ok',
                      'ultrasonic_front': 'ok', 'ultrasonic_left': 'never', 'ultrasonic_right': 'ok'}
        self.sensor_health_pub.publish(String(data=json.dumps(health)))

    def on_destination(self, msg):
        self.get_logger().info(f'📍 UI → /destination: {msg.data}')

    def on_mode_switch(self, msg):
        self.get_logger().info(f'🎛️  UI → /mode_switch: {msg.data}')

    def on_cmd_vel(self, msg):
        if abs(msg.linear.x) > 0.001 or abs(msg.angular.z) > 0.001:
            self.get_logger().info(
                f'🕹️  UI → /cmd_vel_teleop: linear={msg.linear.x:.2f}, angular={msg.angular.z:.2f}')


def main():
    rclpy.init()
    node = FakePublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()