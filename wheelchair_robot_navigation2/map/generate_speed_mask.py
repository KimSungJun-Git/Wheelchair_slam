#!/usr/bin/env python3
# zone_checker.py
import rclpy
from rclpy.node import Node
from nav_msgs.msg import OccupancyGrid
from geometry_msgs.msg import PointStamped
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy


class ZoneChecker(Node):
    def __init__(self):
        super().__init__('zone_checker')

        # speed_filter_mask는 latched(TRANSIENT_LOCAL)로 발행됨
        qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )

        self.mask_data = None
        self.mask_sub = self.create_subscription(
            OccupancyGrid, '/speed_filter_mask', self.mask_cb, qos)

        self.point_sub = self.create_subscription(
            PointStamped, '/clicked_point', self.point_cb, 10)

        self.get_logger().info(
            'RViz의 "Publish Point"로 맵 위를 클릭하세요')

    def mask_cb(self, msg):
        self.mask_data = msg
        self.get_logger().info(
            f'Speed mask 로드됨: {msg.info.width} × {msg.info.height}, '
            f'resolution: {msg.info.resolution:.3f} m/px')

    def point_cb(self, msg):
        if self.mask_data is None:
            self.get_logger().warn('아직 mask 데이터 없음')
            return

        # 클릭한 map 좌표
        x, y = msg.point.x, msg.point.y

        # mask의 origin과 resolution
        ox = self.mask_data.info.origin.position.x
        oy = self.mask_data.info.origin.position.y
        res = self.mask_data.info.resolution
        w = self.mask_data.info.width
        h = self.mask_data.info.height

        # 픽셀 좌표 계산
        px = int((x - ox) / res)
        py = int((y - oy) / res)

        if not (0 <= px < w and 0 <= py < h):
            self.get_logger().warn(
                f'클릭 지점({x:.2f}, {y:.2f})이 mask 범위 밖')
            return

        # OccupancyGrid 데이터는 row-major, y는 아래에서 위로
        idx = py * w + px
        value = self.mask_data.data[idx]

        # 값 → 의미 변환
        # speed_filter는 0(통행)~99(서행) 또는 100(정지)
        # OccupancyGrid: -1=unknown, 0~100
        if value == -1:
            zone = '알 수 없음'
            speed = 'N/A'
        elif value == 0:
            zone = '일반 구역'
            speed = '100%'
        elif value >= 99:
            zone = '정지/장애물'
            speed = '0%'
        else:
            zone = '서행 구역'
            speed = f'{100 - value}%'

        self.get_logger().info(
            f'위치: ({x:.2f}, {y:.2f}) | 픽셀: ({px}, {py}) | '
            f'값: {value} | {zone} | 속도: {speed}')


def main():
    rclpy.init()
    rclpy.spin(ZoneChecker())


if __name__ == '__main__':
    main()