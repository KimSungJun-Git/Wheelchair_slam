#!/usr/bin/env python3
# imu_safety_node.py
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Imu
from std_msgs.msg import Bool, String
import math


class ImuSafetyNode(Node):
    def __init__(self):
        super().__init__('imu_safety_node')

        # ===== 임계값 =====
        self.tilt_threshold_deg = 45.0       # 기울기 한계 (roll/pitch)
        self.impact_threshold = 45.0          # 충격 가속도 (m/s²) — 약 1.5G
        self.recovery_time_sec = 2.0          # 정상 복귀 후 대기 시간

        # ===== 상태 =====
        self.in_emergency = False
        self.last_trigger_time = None

        # IMU에 sensor_data QoS 적용 (드라이버와 매칭)
        self.create_subscription(Imu, '/imu/data', self.imu_cb, qos_profile_sensor_data)

        # 전용 토픽으로 분리 — safety_stop_node가 /emergency_stop/imu 구독
        self.emergency_pub = self.create_publisher(Bool, '/emergency_stop/imu', 10)
        self.sos_pub = self.create_publisher(String, '/sos_trigger', 10)

        self.create_timer(0.1, self.publish_state)
        self.get_logger().info(
            f'IMU Safety 시작 | 기울기≤{self.tilt_threshold_deg}°, 충격≤{self.impact_threshold}m/s² | '
            f'토픽: /emergency_stop/imu')

    def imu_cb(self, msg: Imu):
        q = msg.orientation
        sinr = 2.0 * (q.w * q.x + q.y * q.z)
        cosr = 1.0 - 2.0 * (q.x * q.x + q.y * q.y)
        roll = math.degrees(math.atan2(sinr, cosr))

        sinp = 2.0 * (q.w * q.y - q.z * q.x)
        pitch = math.degrees(math.asin(max(-1.0, min(1.0, sinp))))

        roll = roll - 1.17
        pitch = pitch - 5.50

        spin_rate = abs(msg.angular_velocity.z)
        is_spinning = spin_rate > 0.3 

        # 2. 충격 (선형 가속도 크기)
        a = msg.linear_acceleration
        accel_mag = math.sqrt(a.x**2 + a.y**2 + a.z**2)

        # 3. 위험 판정
        if is_spinning:
            tilt_danger = False
        else:
            tilt_danger = abs(roll) > self.tilt_threshold_deg or abs(pitch) > self.tilt_threshold_deg
        self.get_logger().info(f'실시간 각도 -> Roll: {roll:.2f}°, Pitch: {pitch:.2f}° | 회전중: {is_spinning}')
        
        impact_danger = accel_mag > self.impact_threshold

        if tilt_danger or impact_danger:
            if not self.in_emergency:
                reason = '기울기' if tilt_danger else '충격'
                detail = f'roll={roll:.1f}° pitch={pitch:.1f}°' if tilt_danger else f'accel={accel_mag:.1f}m/s²'
                self.get_logger().error(f'⚠️ IMU 위험 감지 ({reason}): {detail}')

                self.in_emergency = True
                self.last_trigger_time = self.get_clock().now()

                self.sos_pub.publish(String(data=f'imu_{reason}:{detail}'))
        else:
            # 일정 시간 안정 시 자동 해제
            if self.in_emergency and self.last_trigger_time is not None:
                elapsed = (self.get_clock().now() - self.last_trigger_time).nanoseconds / 1e9
                if elapsed > self.recovery_time_sec:
                    self.in_emergency = False
                    self.get_logger().info('✅ IMU 정상 복귀')

    def publish_state(self):
        self.emergency_pub.publish(Bool(data=self.in_emergency))


def main():
    rclpy.init()
    node = ImuSafetyNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()