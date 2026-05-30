#!/usr/bin/env python3
"""
가짜 IMU 노드 (제어 가능 버전)
================================
sensor_msgs/Imu를 /imu/data로 발행. /cmd_vel을 적분해 합성 데이터를 만든다.

scenario_runner와 연동되는 제어 토픽 /fake/imu_control (std_msgs/String):
  "lost"     - /imu/data 발행 중단
  "restore"  - 발행 재개
  "shock"    - 큰 linear_acceleration 한 차례 (충격 시뮬, ~3초)
  "tilt"     - pitch/roll을 크게 설정 (기울기 시뮬, 지속)
  "clear"    - shock/tilt 해제
  "reset"    - 전체 리셋
"""
import math
import random

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Imu
from std_msgs.msg import String


GRAVITY = 9.81


class FakeImuNode(Node):
    def __init__(self):
        super().__init__('fake_imu_node')

        self.declare_parameter('publish_rate', 50.0)
        self.declare_parameter('imu_frame', 'imu_link')
        self.declare_parameter('noise_std_w', 0.005)
        self.declare_parameter('noise_std_a', 0.05)
        self.declare_parameter('noise_std_yaw', 0.005)
        self.declare_parameter('cmd_timeout', 0.5)
        # 속도/가속도 제한 (다른 fake 노드와 동일하게 유지)
        self.declare_parameter('max_linear_velocity', 0.3)
        self.declare_parameter('max_angular_velocity', 1.0)
        self.declare_parameter('max_linear_accel', 0.4)
        self.declare_parameter('max_angular_accel', 2.0)

        self.rate = self.get_parameter('publish_rate').value
        self.imu_frame = self.get_parameter('imu_frame').value
        self.nw = self.get_parameter('noise_std_w').value
        self.na = self.get_parameter('noise_std_a').value
        self.nyaw = self.get_parameter('noise_std_yaw').value
        self.cmd_timeout = self.get_parameter('cmd_timeout').value
        self.max_v = float(self.get_parameter('max_linear_velocity').value)
        self.max_w = float(self.get_parameter('max_angular_velocity').value)
        self.max_a = float(self.get_parameter('max_linear_accel').value)
        self.max_alpha = float(self.get_parameter('max_angular_accel').value)

        self.yaw = 0.0
        self.v_cmd = 0.0
        self.w_cmd = 0.0
        self.v_applied = 0.0
        self.w_applied = 0.0
        self.v_prev = 0.0
        self.last_cmd_time = self.get_clock().now()
        self.last_tick_time = self.get_clock().now()

        # 제어 상태
        self.publishing_enabled = True
        self.shock_until = None        # rclpy Time
        self.tilt_active = False       # pitch=30도, roll=20도 강제

        self.create_subscription(Twist, '/cmd_vel', self.cmd_cb, 10)
        self.create_subscription(String, '/fake/imu_control', self._control_cb, 10)
        self.imu_pub = self.create_publisher(Imu, '/imu/data', 10)
        self.create_timer(1.0 / self.rate, self.tick)

        self.get_logger().info(
            f'Fake IMU 시작 | rate={self.rate}Hz | frame: {self.imu_frame}')

    def cmd_cb(self, msg: Twist):
        self.v_cmd = float(msg.linear.x)
        self.w_cmd = float(msg.angular.z)
        self.last_cmd_time = self.get_clock().now()

    def _control_cb(self, msg: String):
        cmd = msg.data.strip().lower()
        now = self.get_clock().now()

        if cmd == 'lost':
            self.publishing_enabled = False
            self.get_logger().info('🔌 IMU 발행 중단')
        elif cmd == 'restore':
            self.publishing_enabled = True
            self.get_logger().info('✓ IMU 발행 재개')
        elif cmd == 'shock':
            # 3초 동안 충격 인젝션
            self.shock_until = now + rclpy.duration.Duration(seconds=3.0)
            self.get_logger().info('💥 IMU 충격 시뮬 (3초)')
        elif cmd == 'tilt':
            self.tilt_active = True
            self.get_logger().info('📐 IMU 기울기 시뮬 (pitch 30°, roll 20°)')
        elif cmd == 'clear':
            self.shock_until = None
            self.tilt_active = False
            self.get_logger().info('✓ IMU shock/tilt 해제')
        elif cmd == 'reset':
            self.publishing_enabled = True
            self.shock_until = None
            self.tilt_active = False
            self.yaw = 0.0
            self.get_logger().info('🔄 IMU 전체 리셋')
        else:
            self.get_logger().warn(f'알 수 없는 imu 명령: "{cmd}"')

    def tick(self):
        if not self.publishing_enabled:
            return

        now = self.get_clock().now()
        dt = (now - self.last_tick_time).nanoseconds * 1e-9
        if dt <= 0.0:
            return
        self.last_tick_time = now

        if (now - self.last_cmd_time).nanoseconds * 1e-9 > self.cmd_timeout:
            v_target, w_target = 0.0, 0.0
        else:
            v_target, w_target = self.v_cmd, self.w_cmd

        # 속도 캡 + 가속도 제한 (다른 fake 노드와 동일)
        v_target = max(-self.max_v, min(self.max_v, v_target))
        w_target = max(-self.max_w, min(self.max_w, w_target))
        max_dv = self.max_a * dt
        max_dw = self.max_alpha * dt
        dv = max(-max_dv, min(max_dv, v_target - self.v_applied))
        dw = max(-max_dw, min(max_dw, w_target - self.w_applied))
        self.v_applied += dv
        self.w_applied += dw
        v_true = self.v_applied
        w_true = self.w_applied

        self.yaw += w_true * dt
        self.yaw = math.atan2(math.sin(self.yaw), math.cos(self.yaw))

        ax_true = (v_true - self.v_prev) / dt if dt > 0 else 0.0
        self.v_prev = v_true

        w_meas = w_true + random.gauss(0.0, self.nw)
        ax_meas = ax_true + random.gauss(0.0, self.na)
        ay_meas = random.gauss(0.0, self.na)
        az_meas = GRAVITY + random.gauss(0.0, self.na)
        yaw_meas = self.yaw + random.gauss(0.0, self.nyaw)

        # 충격 인젝션: 임계 초과 가속도
        shock_active = (self.shock_until is not None and now < self.shock_until)
        if shock_active:
            ax_meas += 15.0  # imu_safety_node 임계값을 넘기 위해
            ay_meas += random.gauss(0.0, 5.0)
            az_meas += random.gauss(0.0, 5.0)
        elif self.shock_until is not None and now >= self.shock_until:
            self.shock_until = None  # 자동 해제

        # 기울기 인젝션: pitch/roll을 강제
        if self.tilt_active:
            pitch = math.radians(30.0)
            roll = math.radians(20.0)
        else:
            pitch = 0.0
            roll = 0.0

        # quaternion from roll/pitch/yaw (Z-Y-X)
        cy = math.cos(yaw_meas * 0.5)
        sy = math.sin(yaw_meas * 0.5)
        cp = math.cos(pitch * 0.5)
        sp = math.sin(pitch * 0.5)
        cr = math.cos(roll * 0.5)
        sr = math.sin(roll * 0.5)

        imu = Imu()
        imu.header.stamp = now.to_msg()
        imu.header.frame_id = self.imu_frame
        imu.orientation.x = sr * cp * cy - cr * sp * sy
        imu.orientation.y = cr * sp * cy + sr * cp * sy
        imu.orientation.z = cr * cp * sy - sr * sp * cy
        imu.orientation.w = cr * cp * cy + sr * sp * sy

        # 기울기 활성화 시 roll/pitch 분산 낮춤
        rp_cov = 0.005 if self.tilt_active else 1e6
        imu.orientation_covariance = [
            rp_cov, 0.0, 0.0,
            0.0, rp_cov, 0.0,
            0.0, 0.0, 0.01,
        ]

        imu.angular_velocity.x = 0.0
        imu.angular_velocity.y = 0.0
        imu.angular_velocity.z = w_meas
        imu.angular_velocity_covariance = [
            1e6, 0.0, 0.0,
            0.0, 1e6, 0.0,
            0.0, 0.0, 0.005,
        ]

        imu.linear_acceleration.x = ax_meas
        imu.linear_acceleration.y = ay_meas
        imu.linear_acceleration.z = az_meas
        imu.linear_acceleration_covariance = [
            0.05, 0.0, 0.0,
            0.0, 0.05, 0.0,
            0.0, 0.0, 0.05,
        ]

        self.imu_pub.publish(imu)


def main():
    rclpy.init()
    node = FakeImuNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
