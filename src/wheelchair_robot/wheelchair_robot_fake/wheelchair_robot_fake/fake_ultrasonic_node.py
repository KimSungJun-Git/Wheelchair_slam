#!/usr/bin/env python3
"""
가짜 초음파 노드
=================
HC-SR04P 3개를 시뮬레이션. 기본은 안전한 거리(0.45m)를 20Hz로 발행.

/fake/ultrasonic_control (std_msgs/String) 토픽으로 동작을 제어할 수 있다:
  - "front_close" / "left_close" / "right_close" : 해당 센서 거리를 0.1m로 (위험)
  - "front_lost"  / "left_lost"  / "right_lost"  : 해당 센서 발행 중단 (sensor_lost)
  - "reset"                                       : 모든 센서 정상 복귀
"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Range
from std_msgs.msg import String


SENSORS = ('front', 'left', 'right')

# topic name & frame_id 매핑
TOPIC_NAMES = {
    'front': '/ultrasonic/range',
    'left':  '/ultrasonic/left',
    'right': '/ultrasonic/right',
}
FRAME_IDS = {
    'front': 'ultrasonic_front',
    'left':  'ultrasonic_left',
    'right': 'ultrasonic_right',
}


class FakeUltrasonicNode(Node):
    def __init__(self):
        super().__init__('fake_ultrasonic_node')

        # 파라미터
        self.declare_parameter('publish_rate', 20.0)
        self.declare_parameter('default_range', 0.45)
        self.declare_parameter('danger_range', 0.10)
        self.declare_parameter('min_range', 0.02)
        self.declare_parameter('max_range', 0.5)
        self.declare_parameter('field_of_view', 0.26)

        self.rate = float(self.get_parameter('publish_rate').value)
        self.default_range = float(self.get_parameter('default_range').value)
        self.danger_range = float(self.get_parameter('danger_range').value)
        self.min_range = float(self.get_parameter('min_range').value)
        self.max_range = float(self.get_parameter('max_range').value)
        self.fov = float(self.get_parameter('field_of_view').value)

        # 클램프
        self.default_range = max(self.min_range + 0.01,
                                  min(self.default_range, self.max_range - 0.01))

        # 센서별 상태: enabled, distance
        self.states = {
            s: {'enabled': True, 'distance': self.default_range} for s in SENSORS
        }

        # Publisher 3개
        self.pubs = {
            s: self.create_publisher(Range, TOPIC_NAMES[s], 10) for s in SENSORS
        }

        # 제어 토픽 구독
        self.create_subscription(
            String, '/fake/ultrasonic_control', self._control_cb, 10)

        self.create_timer(1.0 / self.rate, self._tick)

        self.get_logger().info(
            f'Fake Ultrasonic 시작 | rate={self.rate}Hz | '
            f'안전={self.default_range:.2f}m, 위험={self.danger_range:.2f}m\n'
            f'  제어: ros2 topic pub --once /fake/ultrasonic_control '
            f'std_msgs/String "data: \'front_close\'"'
        )

    def _make_msg(self, sensor, distance):
        msg = Range()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = FRAME_IDS[sensor]
        msg.radiation_type = Range.ULTRASOUND
        msg.field_of_view = self.fov
        msg.min_range = self.min_range
        msg.max_range = self.max_range
        msg.range = float(distance)
        return msg

    def _control_cb(self, msg: String):
        cmd = msg.data.strip().lower()

        if cmd == 'reset':
            for s in SENSORS:
                self.states[s]['enabled'] = True
                self.states[s]['distance'] = self.default_range
            self.get_logger().info('✅ 모든 초음파 정상 복귀')
            return

        # "front_close" / "left_lost" 형태 파싱
        if '_' not in cmd:
            self.get_logger().warn(f'알 수 없는 명령: "{cmd}"')
            return

        sensor, action = cmd.split('_', 1)
        if sensor not in SENSORS:
            self.get_logger().warn(f'알 수 없는 센서: "{sensor}"')
            return

        if action == 'close':
            self.states[sensor]['enabled'] = True
            self.states[sensor]['distance'] = self.danger_range
            self.get_logger().info(
                f'⚠ {sensor} 초음파 위험 거리 ({self.danger_range:.2f}m)')
        elif action == 'lost':
            self.states[sensor]['enabled'] = False
            self.get_logger().info(f'🔌 {sensor} 초음파 발행 중단 (sensor_lost 시뮬)')
        elif action == 'safe':
            self.states[sensor]['enabled'] = True
            self.states[sensor]['distance'] = self.default_range
            self.get_logger().info(f'✓ {sensor} 초음파 정상')
        else:
            self.get_logger().warn(f'알 수 없는 동작: "{action}"')

    def _tick(self):
        for s in SENSORS:
            st = self.states[s]
            if st['enabled']:
                self.pubs[s].publish(self._make_msg(s, st['distance']))


def main():
    rclpy.init()
    node = FakeUltrasonicNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
