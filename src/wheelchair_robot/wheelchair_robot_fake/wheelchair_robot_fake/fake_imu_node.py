#!/usr/bin/env python3
"""
가짜 IMU 노드
==============
/cmd_vel을 받아 IMU에서 측정될 법한 angular_velocity, orientation, linear_acceleration을 합성해
sensor_msgs/Imu 형태로 /imu/data에 발행한다.

EKF가 실제로 읽는 필드는 angular_velocity.z (yaw rate) 한 가지뿐이지만,
RViz 시각화와 향후 확장을 위해 orientation과 linear_acceleration도 채워준다.

ekf.yaml의 imu0_remove_gravitational_acceleration: true 설정에 맞춰
linear_acceleration.z에는 중력(9.81)을 포함시킨다.
"""
import math
import random

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Imu


GRAVITY = 9.81


class FakeImuNode(Node):
    def __init__(self):
        super().__init__('fake_imu_node')

        self.declare_parameter('publish_rate', 50.0)
        self.declare_parameter('imu_frame', 'imu_link')
        self.declare_parameter('noise_std_w', 0.005)   # gyro 노이즈 (rad/s)
        self.declare_parameter('noise_std_a', 0.05)    # accel 노이즈 (m/s²)
        self.declare_parameter('noise_std_yaw', 0.005) # 방향 노이즈 (rad)
        self.declare_parameter('cmd_timeout', 0.5)

        # rclpy의 get_parameter_value() 메서드를 사용하여 타입을 명확히 지정
        self.rate = self.get_parameter('publish_rate').get_parameter_value().double_value
        self.imu_frame = self.get_parameter('imu_frame').get_parameter_value().string_value
        self.noise_w = self.get_parameter('noise_std_w').get_parameter_value().double_value
        self.noise_a = self.get_parameter('noise_std_a').get_parameter_value().double_value
        self.noise_yaw = self.get_parameter('noise_std_yaw').get_parameter_value().double_value
        self.cmd_timeout = self.get_parameter('cmd_timeout').get_parameter_value().double_value

        # 상태
        self.yaw = 0.0
        self.v_cmd = 0.0
        self.w_cmd = 0.0
        self.v_prev = 0.0
        self.last_cmd_time = self.get_clock().now()
        self.last_tick_time = self.get_clock().now()

        self.create_subscription(Twist, '/cmd_vel', self.cmd_cb, 10)
        self.imu_pub = self.create_publisher(Imu, '/imu/data', 10)
        self.create_timer(1.0 / self.rate, self.tick)

        self.get_logger().info(
            f'Fake IMU 시작 | rate={self.rate}Hz | frame: {self.imu_frame}'
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

        # cmd_vel 끊김 처리
        if (now - self.last_cmd_time).nanoseconds * 1e-9 > self.cmd_timeout:
            v_true, w_true = 0.0, 0.0
        else:
            v_true, w_true = self.v_cmd, self.w_cmd

        # yaw 적분
        self.yaw += w_true * delta_t
        self.yaw = math.atan2(math.sin(self.yaw), math.cos(self.yaw))

        # 선가속도 추정 (수치 미분)
        ax_true = (v_true - self.v_prev) / delta_t if delta_t > 0 else 0.0
        self.v_prev = v_true

        # 측정값 + 노이즈
        w_meas = w_true + random.gauss(0.0, self.noise_w)
        ax_meas = ax_true + random.gauss(0.0, self.noise_a)
        ay_meas = random.gauss(0.0, self.noise_a)
        az_meas = GRAVITY + random.gauss(0.0, self.noise_a)
        yaw_meas = self.yaw + random.gauss(0.0, self.noise_yaw)

        imu = Imu()
        imu.header.stamp = now.to_msg()
        imu.header.frame_id = self.imu_frame

        # orientation: roll=pitch=0, yaw=yaw_meas
        imu.orientation.x = 0.0
        imu.orientation.y = 0.0
        imu.orientation.z = math.sin(yaw_meas / 2.0)
        imu.orientation.w = math.cos(yaw_meas / 2.0)
        # roll/pitch는 신뢰도 낮음 → 큰 분산
        imu.orientation_covariance = [
            1e6, 0.0, 0.0,
            0.0, 1e6, 0.0,
            0.0, 0.0, 0.01,
        ]

        imu.angular_velocity.x = 0.0
        imu.angular_velocity.y = 0.0
        imu.angular_velocity.z = w_meas
        imu.angular_velocity_covariance = [
            1e6, 0.0,   0.0,
            0.0, 1e6,   0.0,
            0.0, 0.0,   0.005,
        ]

        imu.linear_acceleration.x = ax_meas
        imu.linear_acceleration.y = ay_meas
        imu.linear_acceleration.z = az_meas   # EKF가 중력을 빼줌
        imu.linear_acceleration_covariance = [
            0.05, 0.0,  0.0,
            0.0,  0.05, 0.0,
            0.0,  0.0,  0.05,
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