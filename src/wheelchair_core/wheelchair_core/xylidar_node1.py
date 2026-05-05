#!/usr/bin/env python3
"""
lidar_proc_node.py
─────────────────────────────────────────────────────────────────
LaserScan → 전방/측면 거리 처리 후 발행

발행 토픽:
  /lidar/front_dist  (std_msgs/Float32)  : 전방 ±15° 최소 거리 (m)
  /lidar/side_dist   (geometry_msgs/Vector3)
    .x : 왼쪽 90° ± 20° 최소 거리 (m)
    .y : 오른쪽 270° ± 20° 최소 거리 (m)
"""

import math
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Float32
from geometry_msgs.msg import Vector3


class LidarProcNode(Node):

    def __init__(self):
        super().__init__('lidar_proc_node')

        self._sub = self.create_subscription(
            LaserScan, '/scan', self._scan_cb, 10)

        self._pub_front = self.create_publisher(Float32,  '/lidar/front_dist', 10)
        self._pub_sides = self.create_publisher(Vector3, '/lidar/side_dist',  10)

        self.get_logger().info('LidarProcNode 준비')

    # ──────────────────────────────────────────────────────────
    def _scan_cb(self, msg: LaserScan):
        n   = len(msg.ranges)
        inc = msg.angle_increment

        def sector_min(center_deg: float, half_deg: float) -> float:
            """center_deg 기준 ±half_deg 범위의 최솟값 반환."""
            c_idx = int(math.radians(center_deg) / inc) % n
            h_idx = int(math.radians(half_deg)   / inc)
            idxs  = [(c_idx + i) % n for i in range(-h_idx, h_idx + 1)]
            vals  = [
                msg.ranges[i] for i in idxs
                if msg.range_min < msg.ranges[i] < msg.range_max
            ]
            return float(min(vals)) if vals else 999.0

        front = sector_min(  0.0, 15.0)
        left  = sector_min( 90.0, 20.0)
        right = sector_min(270.0, 20.0)

        f_msg = Float32()
        f_msg.data = front
        self._pub_front.publish(f_msg)

        s_msg = Vector3()
        s_msg.x = left
        s_msg.y = right
        self._pub_sides.publish(s_msg)


# ──────────────────────────────────────────────────────────────
def main(args=None):
    rclpy.init(args=args)
    node = LidarProcNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()