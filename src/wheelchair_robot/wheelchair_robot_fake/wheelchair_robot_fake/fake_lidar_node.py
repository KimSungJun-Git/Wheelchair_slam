#!/usr/bin/env python3
"""
가짜 라이다 노드 (맵 지원 버전)
=================================
sensor_msgs/LaserScan을 /scan으로 발행한다. /cmd_vel을 자체 적분해 현재 위치를 알고,
그 위치에서 본 스캔을 생성한다.

두 가지 모드:
  - map_yaml 파라미터 비어있음 → 내장 가상 룸(직사각형 + 박스 두 개)에 레이캐스팅
  - map_yaml 파라미터 지정     → 해당 occupancy grid 맵을 읽어서 그 위에서 레이캐스팅
                                  (AMCL/Nav2 위치추정 테스트에 사용)

initial_map_x/y/yaw 파라미터로 맵 안에서의 시작 위치를 지정할 수 있다.
이 값은 RViz의 "2D Pose Estimate"로 AMCL에 알려준 값과 일치해야 한다.
"""
import math
import os
import random

try:
    import yaml
except ImportError:
    yaml = None

from rcl_interfaces.msg import ParameterDescriptor

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan


def load_pgm(path):
    """간단한 PGM (P5) 파서. (height, width) uint8 리스트 of 리스트 반환."""
    with open(path, 'rb') as f:
        magic = f.readline().strip()
        if magic not in (b'P5', b'P2'):
            raise ValueError(f'지원하지 않는 PGM 매직: {magic!r}')

        def read_token():
            while True:
                line = f.readline()
                if not line:
                    raise ValueError('PGM 헤더 종료')
                line = line.strip()
                if not line or line.startswith(b'#'):
                    continue
                return line

        size = read_token().split()
        while len(size) < 2:
            size += read_token().split()
        w, h = int(size[0]), int(size[1])
        max_val = int(read_token())

        if magic == b'P5':
            raw = f.read(w * h * (1 if max_val < 256 else 2))
            if max_val < 256:
                pixels = list(raw)
            else:
                # 2바이트 (big-endian per spec)
                pixels = [raw[i] * 256 + raw[i + 1] for i in range(0, len(raw), 2)]
        else:  # P2 (ASCII)
            tokens = []
            for line in f:
                tokens.extend(line.split())
            pixels = [int(t) for t in tokens[:w * h]]

        # 0~255로 정규화
        if max_val != 255:
            pixels = [int(p * 255 / max_val) for p in pixels]

        # row-major: pixels[row * w + col]
        grid = [pixels[r * w:(r + 1) * w] for r in range(h)]
        return grid, w, h


class FakeLidarNode(Node):
    def __init__(self):
        super().__init__('fake_lidar_node')

        # ── 일반 파라미터 ──────────────────────────────────────────────
        self.declare_parameter('publish_rate', 10.0)
        self.declare_parameter('laser_frame', 'laser_frame')
        self.declare_parameter('num_samples', 360)
        self.declare_parameter('range_min', 0.12)
        self.declare_parameter('range_max', 10.0)
        self.declare_parameter('noise_std', 0.02)
        self.declare_parameter('cmd_timeout', 0.5)

        # ── 맵에서의 시작 위치 (월드 좌표) ─────────────────────────────
        # Launch에서 문자열로 넘어올 수 있으므로 동적 타이핑 허용
        self.declare_parameter('initial_map_x', 0.0, ParameterDescriptor(dynamic_typing=True))
        self.declare_parameter('initial_map_y', 0.0, ParameterDescriptor(dynamic_typing=True))
        self.declare_parameter('initial_map_yaw', 0.0, ParameterDescriptor(dynamic_typing=True))

        # ── 모드 1: 실제 맵 사용 ────────────────────────────────────
        # YAML 경로 지정 시 해당 점유 격자를 읽어 그 위에서 레이캐스팅
        self.declare_parameter('map_yaml', '')

        # ── 모드 2: 내장 가상 룸 (map_yaml 비어있을 때만 사용) ────────
        self.declare_parameter('room_x_min', -5.0)
        self.declare_parameter('room_x_max', 5.0)
        self.declare_parameter('room_y_min', -5.0)
        self.declare_parameter('room_y_max', 5.0)
        self.declare_parameter('obstacles', [
             2.0,  2.5, -1.0,  1.0,
            -2.0, -1.5,  1.0,  3.0,
        ])

        # 파라미터 읽기 (get_parameter_value()를 사용하여 명시적 타입 지정)
        self.rate = self.get_parameter('publish_rate').get_parameter_value().double_value
        self.laser_frame = self.get_parameter('laser_frame').get_parameter_value().string_value
        self.num_samples = int(self.get_parameter('num_samples').get_parameter_value().integer_value)
        self.range_min = self.get_parameter('range_min').get_parameter_value().double_value
        self.range_max = self.get_parameter('range_max').get_parameter_value().double_value
        self.noise = self.get_parameter('noise_std').get_parameter_value().double_value
        self.cmd_timeout = self.get_parameter('cmd_timeout').get_parameter_value().double_value

        # initial_map_* 파라미터는 dynamic_typing이 켜져 있으므로, 먼저 문자열 등으로 받아 float로 변환
        init_x_param = self.get_parameter('initial_map_x').value
        init_y_param = self.get_parameter('initial_map_y').value
        init_yaw_param = self.get_parameter('initial_map_yaw').value
        
        init_x = float(init_x_param) if init_x_param is not None else 0.0
        init_y = float(init_y_param) if init_y_param is not None else 0.0
        init_yaw = float(init_yaw_param) if init_yaw_param is not None else 0.0

        map_yaml_param = self.get_parameter('map_yaml').get_parameter_value().string_value
        self.map_yaml = map_yaml_param.strip() if map_yaml_param else ''

        # ── 모드 결정 ───────────────────────────────────────────────
        self.use_map = bool(self.map_yaml)
        if self.use_map:
            self._load_map(self.map_yaml)
        else:
            self._setup_virtual_room()

        # ── 상태 ───────────────────────────────────────────────────
        self.x = init_x
        self.y = init_y
        self.yaw = init_yaw
        self.v_cmd = 0.0
        self.w_cmd = 0.0
        self.last_cmd_time = self.get_clock().now()
        self.last_int_time = self.get_clock().now()

        # ── 통신 ───────────────────────────────────────────────────
        self.create_subscription(Twist, '/cmd_vel', self.cmd_cb, 10)
        self.scan_pub = self.create_publisher(LaserScan, '/scan', 10)
        
        # self.rate가 확실한 float가 되었으므로 에러 해결
        self.create_timer(1.0 / self.rate, self.publish_scan)
        self.create_timer(0.02, self.integrate)  # 50 Hz

        mode = '맵 기반' if self.use_map else '가상 룸'
        self.get_logger().info(
            f'Fake Lidar 시작 [{mode}] | {self.rate}Hz, {self.num_samples}샘플 | '
            f'frame: {self.laser_frame} | 시작 위치: ({init_x:.2f}, {init_y:.2f}, {init_yaw:.2f}rad)'
        )

    # ─── 모드별 환경 셋업 ─────────────────────────────────────────────
    def _load_map(self, yaml_path):
        """nav2 map_server 호환 YAML + PGM을 읽어 점유 격자 만들기."""
        if yaml is None:
            raise RuntimeError('PyYAML이 설치되어 있어야 합니다 (pip install pyyaml)')

        with open(yaml_path, 'r') as f:
            meta = yaml.safe_load(f)

        self.map_resolution = float(meta['resolution'])
        origin = meta['origin']
        self.map_origin_x = float(origin[0])
        self.map_origin_y = float(origin[1])
        negate = int(meta.get('negate', 0))
        occ_thresh = float(meta.get('occupied_thresh', 0.65))

        image_rel = meta['image']
        if not os.path.isabs(image_rel):
            image_path = os.path.join(os.path.dirname(os.path.abspath(yaml_path)), image_rel)
        else:
            image_path = image_rel

        pgm, w, h = load_pgm(image_path)
        self.map_w = w
        self.map_h = h

        # 점유 그리드 (True = 차단)
        # negate=0: 어두울수록 점유. occupancy = (255 - p) / 255
        # negate=1: 밝을수록 점유.
        thr = occ_thresh * 255.0
        if negate:
            self.occ_grid = [[(p >= thr) for p in row] for row in pgm]
        else:
            self.occ_grid = [[((255 - p) >= thr) for p in row] for row in pgm]

        self.get_logger().info(
            f'맵 로드 완료: {image_path} ({w}×{h}, res={self.map_resolution}, '
            f'origin=({self.map_origin_x:.2f}, {self.map_origin_y:.2f}))'
        )

    def _setup_virtual_room(self):
        # 파라미터를 double_value로 명확히 읽어옵니다.
        self.xmin = self.get_parameter('room_x_min').get_parameter_value().double_value
        self.xmax = self.get_parameter('room_x_max').get_parameter_value().double_value
        self.ymin = self.get_parameter('room_y_min').get_parameter_value().double_value
        self.ymax = self.get_parameter('room_y_max').get_parameter_value().double_value

        # 리스트 형태는 double_array_value로 읽어옵니다.
        obs_flat = list(self.get_parameter('obstacles').get_parameter_value().double_array_value)
        self.obstacles = []
        for i in range(0, len(obs_flat) - 3, 4):
            self.obstacles.append((
                float(obs_flat[i]),
                float(obs_flat[i + 1]),
                float(obs_flat[i + 2]),
                float(obs_flat[i + 3]),
            ))
        self.get_logger().info(
            f'가상 룸: ({self.xmin},{self.xmax})x({self.ymin},{self.ymax}), '
            f'박스 {len(self.obstacles)}개'
        )

    # ─── 상태 갱신 ───────────────────────────────────────────────────
    def cmd_cb(self, msg: Twist):
        self.v_cmd = float(msg.linear.x)
        self.w_cmd = float(msg.angular.z)
        self.last_cmd_time = self.get_clock().now()

    def integrate(self):
        now = self.get_clock().now()
        delta_t = (now - self.last_int_time).nanoseconds * 1e-9
        if delta_t <= 0.0:
            return
        self.last_int_time = now
        if (now - self.last_cmd_time).nanoseconds * 1e-9 > self.cmd_timeout:
            return
        self.x += self.v_cmd * math.cos(self.yaw) * delta_t
        self.y += self.v_cmd * math.sin(self.yaw) * delta_t
        self.yaw += self.w_cmd * delta_t

    # ─── 레이캐스팅 ──────────────────────────────────────────────────
    def raycast_map(self, angle_world):
        """점유 격자에 대한 ray-march. (self.x, self.y)에서 angle 방향으로
        가장 가까운 점유 셀까지 거리(미터)."""
        cos_a = math.cos(angle_world)
        sin_a = math.sin(angle_world)
        step = self.map_resolution * 0.5  # 셀의 절반씩
        max_t = self.range_max
        n_steps = int(max_t / step) + 1

        for i in range(1, n_steps + 1):
            t = i * step
            if t > max_t:
                return max_t
            wx = self.x + t * cos_a
            wy = self.y + t * sin_a
            col = int((wx - self.map_origin_x) / self.map_resolution)
            # ROS map: pgm row 0 = 이미지 top = 가장 큰 y
            image_row = self.map_h - 1 - int((wy - self.map_origin_y) / self.map_resolution)
            if 0 <= col < self.map_w and 0 <= image_row < self.map_h:
                if self.occ_grid[image_row][col]:
                    return t
            else:
                return max_t  # 맵 밖
        return max_t

    def raycast_room(self, angle_world):
        """가상 룸(벽 + AABB 박스)에 대한 ray-box intersection."""
        cos_a = math.cos(angle_world)
        sin_a = math.sin(angle_world)
        best = self.range_max

        # 벽 4개
        if abs(cos_a) > 1e-9:
            for wall_x in (self.xmin, self.xmax):
                t = (wall_x - self.x) / cos_a
                if 0.0 < t < best:
                    y_hit = self.y + t * sin_a
                    if self.ymin <= y_hit <= self.ymax:
                        best = t
        if abs(sin_a) > 1e-9:
            for wall_y in (self.ymin, self.ymax):
                t = (wall_y - self.y) / sin_a
                if 0.0 < t < best:
                    x_hit = self.x + t * cos_a
                    if self.xmin <= x_hit <= self.xmax:
                        best = t

        # AABB 박스
        for (x_min, x_max, y_min, y_max) in self.obstacles:
            t_enter, t_exit = 0.0, best
            if abs(cos_a) < 1e-9:
                if not (x_min <= self.x <= x_max):
                    continue
            else:
                t_x1 = (x_min - self.x) / cos_a
                t_x2 = (x_max - self.x) / cos_a
                t_lo, t_hi = (t_x1, t_x2) if t_x1 < t_x2 else (t_x2, t_x1)
                t_enter = max(t_enter, t_lo)
                t_exit = min(t_exit, t_hi)
                if t_enter > t_exit:
                    continue
            if abs(sin_a) < 1e-9:
                if not (y_min <= self.y <= y_max):
                    continue
            else:
                t_y1 = (y_min - self.y) / sin_a
                t_y2 = (y_max - self.y) / sin_a
                t_lo, t_hi = (t_y1, t_y2) if t_y1 < t_y2 else (t_y2, t_y1)
                t_enter = max(t_enter, t_lo)
                t_exit = min(t_exit, t_hi)
                if t_enter > t_exit:
                    continue
            if 0.0 < t_enter < best:
                best = t_enter
        return best

    # ─── 발행 ─────────────────────────────────────────────────────────
    def publish_scan(self):
        now = self.get_clock().now()
        scan = LaserScan()
        scan.header.stamp = now.to_msg()
        scan.header.frame_id = self.laser_frame
        scan.angle_min = -math.pi
        scan.angle_max = math.pi
        scan.angle_increment = (2.0 * math.pi) / self.num_samples
        scan.time_increment = 0.0
        scan.scan_time = 1.0 / self.rate
        scan.range_min = self.range_min
        scan.range_max = self.range_max

        raycast = self.raycast_map if self.use_map else self.raycast_room

        ranges = [0.0] * self.num_samples
        for i in range(self.num_samples):
            angle_local = scan.angle_min + i * scan.angle_increment
            angle_world = self.yaw + angle_local
            r = raycast(angle_world) + random.gauss(0.0, self.noise)
            if r < self.range_min or r > self.range_max:
                ranges[i] = float('inf')
            else:
                ranges[i] = float(r)
        scan.ranges = ranges

        self.scan_pub.publish(scan)


def main():
    rclpy.init()
    node = FakeLidarNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()