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
        # 속도/가속도 제한 (실제 휠체어처럼 부드러운 거동)
        self.declare_parameter('max_linear_velocity', 0.3)
        self.declare_parameter('max_angular_velocity', 1.0)
        self.declare_parameter('max_linear_accel', 0.4)
        self.declare_parameter('max_angular_accel', 2.0)

        self.rate = self.get_parameter('publish_rate').value
        self.odom_frame = self.get_parameter('odom_frame').value
        self.base_frame = self.get_parameter('base_frame').value
        self.nv = self.get_parameter('noise_std_v').value
        self.nw = self.get_parameter('noise_std_w').value
        self.cmd_timeout = self.get_parameter('cmd_timeout').value
        self.max_v = float(self.get_parameter('max_linear_velocity').value)
        self.max_w = float(self.get_parameter('max_angular_velocity').value)
        self.max_a = float(self.get_parameter('max_linear_accel').value)
        self.max_alpha = float(self.get_parameter('max_angular_accel').value)

        # ── 상태 ─────────────────────────────────────────────────────
        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0
        self.v_cmd = 0.0
        self.w_cmd = 0.0
        self.v_applied = 0.0
        self.w_applied = 0.0
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
        dt = (now - self.last_tick_time).nanoseconds * 1e-9
        if dt <= 0.0:
            return
        self.last_tick_time = now

        # cmd_vel 끊기면 정지
        if (now - self.last_cmd_time).nanoseconds * 1e-9 > self.cmd_timeout:
            v_target, w_target = 0.0, 0.0
        else:
            v_target, w_target = self.v_cmd, self.w_cmd

        # 속도 캡
        v_target = max(-self.max_v, min(self.max_v, v_target))
        w_target = max(-self.max_w, min(self.max_w, w_target))

        # 가속도 제한 (slew rate)
        max_dv = self.max_a * dt
        max_dw = self.max_alpha * dt
        dv = max(-max_dv, min(max_dv, v_target - self.v_applied))
        dw = max(-max_dw, min(max_dw, w_target - self.w_applied))
        self.v_applied += dv
        self.w_applied += dw

        v_true = self.v_applied
        w_true = self.w_applied

        # ground truth 위치 적분
        self.x += v_true * math.cos(self.yaw) * dt
        self.y += v_true * math.sin(self.yaw) * dt
        self.yaw += w_true * dt
        self.yaw = math.atan2(math.sin(self.yaw), math.cos(self.yaw))

        # 측정값에 노이즈 추가
        v_meas = v_true + random.gauss(0.0, self.nv)
        w_meas = w_true + random.gauss(0.0, self.nw)

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
