#!/usr/bin/env python3
"""
가짜 엔코더 노드
================
/cmd_vel을 받아 가상 휠 엔코더가 측정한 듯한 nav_msgs/Odometry를 /odom으로 발행한다.
TF는 EKF가 odom -> base_footprint를 발행하므로 이 노드는 발행하지 않는다.

EKF가 읽는 필드: twist.linear.x, twist.angular.z (ekf.yaml의 odom0_config 기준)
"""
import math
import random

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry


class FakeEncoderNode(Node):
    def __init__(self):
        super().__init__('fake_encoder_node')

        # ── 파라미터 ────────────────────────────────────────────────────
        self.declare_parameter('publish_rate', 30.0)
        self.declare_parameter('odom_frame', 'odom')
        self.declare_parameter('base_frame', 'base_footprint')
        self.declare_parameter('noise_std_v', 0.01)   # 선속도 측정 노이즈 (m/s)
        self.declare_parameter('noise_std_w', 0.01)   # 각속도 측정 노이즈 (rad/s)
        self.declare_parameter('cmd_timeout', 0.5)    # cmd_vel이 끊기면 정지로 간주 (s)

        # rclpy의 get_parameter_value() 메서드를 사용하여 타입을 명확히 지정
        # double_value는 float를, string_value는 str을 반환하므로 Pylance가 인식할 수 있습니다.
        self.rate = self.get_parameter('publish_rate').get_parameter_value().double_value
        self.odom_frame = self.get_parameter('odom_frame').get_parameter_value().string_value
        self.base_frame = self.get_parameter('base_frame').get_parameter_value().string_value
        self.noise_v = self.get_parameter('noise_std_v').get_parameter_value().double_value
        self.noise_w = self.get_parameter('noise_std_w').get_parameter_value().double_value
        self.cmd_timeout = self.get_parameter('cmd_timeout').get_parameter_value().double_value

        # ── 상태 ─────────────────────────────────────────────────────
        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0
        self.v_cmd = 0.0
        self.w_cmd = 0.0
        self.last_cmd_time = self.get_clock().now()
        self.last_tick_time = self.get_clock().now()

        # ── 통신 ─────────────────────────────────────────────────────
        self.create_subscription(Twist, '/cmd_vel', self.cmd_cb, 10)
        self.odom_pub = self.create_publisher(Odometry, '/odom', 10)
        
        self.create_timer(1.0 / self.rate, self.tick)

        self.get_logger().info(
            f'Fake Encoder 시작 | rate={self.rate}Hz | frames: {self.odom_frame} → {self.base_frame}'
        )

    def cmd_cb(self, msg: Twist):
        self.v_cmd = float(msg.linear.x)
        self.w_cmd = float(msg.angular.z)
        self.last_cmd_time = self.get_clock().now()

    def tick(self):
        now = self.get_clock().now()
        delta_t = (now - self.last_tick_time).nanoseconds * 1e-9
        if delta_t <= 0.0:
            return
        self.last_tick_time = now

        # cmd_vel 끊기면 정지
        if (now - self.last_cmd_time).nanoseconds * 1e-9 > self.cmd_timeout:
            v_true, w_true = 0.0, 0.0
        else:
            v_true, w_true = self.v_cmd, self.w_cmd

        # ground truth 위치 적분
        self.x += v_true * math.cos(self.yaw) * delta_t
        self.y += v_true * math.sin(self.yaw) * delta_t
        self.yaw += w_true * delta_t
        self.yaw = math.atan2(math.sin(self.yaw), math.cos(self.yaw))

        # 측정값에 노이즈 추가
        v_meas = v_true + random.gauss(0.0, self.noise_v)
        w_meas = w_true + random.gauss(0.0, self.noise_w)

        # Odometry 메시지 작성
        odom = Odometry()
        odom.header.stamp = now.to_msg()
        odom.header.frame_id = self.odom_frame
        odom.child_frame_id = self.base_frame

        odom.pose.pose.position.x = self.x
        odom.pose.pose.position.y = self.y
        odom.pose.pose.position.z = 0.0
        odom.pose.pose.orientation.z = math.sin(self.yaw / 2.0)
        odom.pose.pose.orientation.w = math.cos(self.yaw / 2.0)

        # 사용 안 하는 차원은 큰 분산으로 (EKF가 무시하도록)
        odom.pose.covariance = [
            0.01, 0.0,  0.0,  0.0,  0.0,  0.0,
            0.0,  0.01, 0.0,  0.0,  0.0,  0.0,
            0.0,  0.0,  1e6,  0.0,  0.0,  0.0,
            0.0,  0.0,  0.0,  1e6,  0.0,  0.0,
            0.0,  0.0,  0.0,  0.0,  1e6,  0.0,
            0.0,  0.0,  0.0,  0.0,  0.0,  0.05,
        ]

        odom.twist.twist.linear.x = v_meas
        odom.twist.twist.angular.z = w_meas
        odom.twist.covariance = [
            0.01, 0.0,  0.0,  0.0,  0.0,  0.0,
            0.0,  1e6,  0.0,  0.0,  0.0,  0.0,
            0.0,  0.0,  1e6,  0.0,  0.0,  0.0,
            0.0,  0.0,  0.0,  1e6,  0.0,  0.0,
            0.0,  0.0,  0.0,  0.0,  1e6,  0.0,
            0.0,  0.0,  0.0,  0.0,  0.0,  0.05,
        ]

        self.odom_pub.publish(odom)


def main():
    rclpy.init()
    node = FakeEncoderNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()