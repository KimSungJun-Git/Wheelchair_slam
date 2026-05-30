#!/usr/bin/env python3
"""
가짜 라이다 노드 (제어 가능 버전)
====================================
sensor_msgs/LaserScan을 /scan으로 발행. /cmd_vel을 자체 적분해 현재 위치를 알고,
그 위치에서 본 스캔을 생성한다.

두 모드:
  - map_yaml 비어있음: 내장 가상 룸(직사각형 + 박스 두 개)에 raycasting
  - map_yaml 지정:    nav2 호환 occupancy grid 맵에 raycasting

scenario_runner와 연동되는 제어 토픽 /fake/lidar_control (std_msgs/String):
  "lost"            - /scan 발행 중단 (sensor_lost 시뮬)
  "restore"         - 발행 재개
  "obstacle_front"  - 전방 ±15도 거리를 0.3m로 강제 (lidar 기반 정지 트리거)
  "obstacle_back"   - 후방 ±15도 거리를 0.15m로 강제 (후진 시 정지)
  "clear_obstacle"  - 강제 장애물 해제
  "teleport"        - 가까운 자유 셀로 점프 (AMCL 분실 유도)
  "reset"           - 모든 강제 상태 해제 + 위치 초기화
"""
import math
import os
import random
from typing import List, Tuple

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan
from std_msgs.msg import String


def load_pgm(path):
    with open(path, 'rb') as f:
        magic = f.readline().strip()
        if magic not in (b'P5', b'P2'):
            raise ValueError(f'PGM 매직 오류: {magic!r}')

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
                pixels = [raw[i] * 256 + raw[i + 1] for i in range(0, len(raw), 2)]
        else:
            tokens = []
            for line in f:
                tokens.extend(line.split())
            pixels = [int(t) for t in tokens[:w * h]]

        if max_val != 255:
            pixels = [int(p * 255 / max_val) for p in pixels]

        grid = [pixels[r * w:(r + 1) * w] for r in range(h)]
        return grid, w, h


class FakeLidarNode(Node):
    def __init__(self):
        super().__init__('fake_lidar_node')

        # 파라미터 선언
        self.declare_parameter('publish_rate', 10.0)
        self.declare_parameter('laser_frame', 'laser_frame')
        self.declare_parameter('num_samples', 360)
        self.declare_parameter('range_min', 0.12)
        self.declare_parameter('range_max', 10.0)
        self.declare_parameter('noise_std', 0.02)
        self.declare_parameter('cmd_timeout', 0.5)
        self.declare_parameter('initial_map_x', 0.0)
        self.declare_parameter('initial_map_y', 0.0)
        self.declare_parameter('initial_map_yaw', 0.0)
        self.declare_parameter('map_yaml', '')
        self.declare_parameter('room_x_min', -5.0)
        self.declare_parameter('room_x_max', 5.0)
        self.declare_parameter('room_y_min', -5.0)
        self.declare_parameter('room_y_max', 5.0)
        self.declare_parameter('obstacles', [
             2.0,  2.5, -1.0,  1.0,
            -2.0, -1.5,  1.0,  3.0,
        ])
        self.declare_parameter('extra_obstacle_polygon', [
            0.593,  0.308,   # P3
            0.901,  0.483,   # P1
            0.988,  0.103,   # P2
            0.732, -0.022,   # P4
        ])

        # 속도/가속도 제한 (휠체어 현실적 거동)
        self.declare_parameter('max_linear_velocity', 0.3)
        self.declare_parameter('max_angular_velocity', 1.0)
        self.declare_parameter('max_linear_accel', 0.4)
        self.declare_parameter('max_angular_accel', 2.0)

        # ── 파라미터 값 안전하게 가져오기 및 타입 명시 (Pylance 에러 해결) ──────────────────
        self.rate = float(self.get_parameter('publish_rate').value or 10.0)
        self.laser_frame = str(self.get_parameter('laser_frame').value or 'laser_frame')
        self.N = int(self.get_parameter('num_samples').value or 360)
        self.rmin = float(self.get_parameter('range_min').value or 0.12)
        self.rmax = float(self.get_parameter('range_max').value or 10.0)
        self.noise = float(self.get_parameter('noise_std').value or 0.02)
        self.cmd_timeout = float(self.get_parameter('cmd_timeout').value or 0.5)

        self.init_x = float(self.get_parameter('initial_map_x').value or 0.0)
        self.init_y = float(self.get_parameter('initial_map_y').value or 0.0)
        self.init_yaw = float(self.get_parameter('initial_map_yaw').value or 0.0)
        
        raw_map_yaml = self.get_parameter('map_yaml').value
        self.map_yaml = str(raw_map_yaml).strip() if raw_map_yaml is not None else ""

        # 초기 맵 해상도 및 원점 멤버 필드 사전 정의 (Pylance Type Narrowing 목적)
        self.map_resolution = 0.05
        self.map_origin_x = 0.0
        self.map_origin_y = 0.0
        self.map_w = 0
        self.map_h = 0
        self.occ_grid = []  # type: List[List[bool]]

        # 가상 룸 경계 및 사각형 장애물 전역 정의
        self.xmin, self.xmax, self.ymin, self.ymax = -5.0, 5.0, -5.0, 5.0
        self.obstacles = []  # type: List[Tuple[float, float, float, float]]

        self.use_map = bool(self.map_yaml)
        if self.use_map:
            self._load_map(self.map_yaml)
        else:
            self._setup_virtual_room()

        # 추가 폴리곤 장애물 파싱 및 Iterable 에러 예외 처리
        poly_param = self.get_parameter('extra_obstacle_polygon').value
        poly_flat = list(poly_param) if poly_param is not None else []
        self.extra_poly = []  # type: List[Tuple[float, float]]
        for i in range(0, len(poly_flat) - 1, 2):
            self.extra_poly.append((float(poly_flat[i]), float(poly_flat[i + 1])))
        if self.extra_poly and len(self.extra_poly) < 3:
            self.get_logger().warn(f'폴리곤은 3점 이상 필요. 현재 {len(self.extra_poly)}점 → 무시.')
            self.extra_poly = []

        # 속도 제한 파라미터 캐스팅
        self.max_v = float(self.get_parameter('max_linear_velocity').value or 0.3)
        self.max_w = float(self.get_parameter('max_angular_velocity').value or 1.0)
        self.max_a = float(self.get_parameter('max_linear_accel').value or 0.4)
        self.max_alpha = float(self.get_parameter('max_angular_accel').value or 2.0)

        # 상태
        self.x = self.init_x
        self.y = self.init_y
        self.yaw = self.init_yaw
        self.v_cmd = 0.0
        self.w_cmd = 0.0
        self.v_applied = 0.0   
        self.w_applied = 0.0
        self.v_prev = 0.0
        self.last_cmd_time = self.get_clock().now()
        self.last_int_time = self.get_clock().now()

        # 제어 상태 (scenario_runner가 변경)
        self.publishing_enabled = True
        self.force_obstacle_front = False
        self.force_obstacle_back = False

        # 통신
        self.create_subscription(Twist, '/cmd_vel', self.cmd_cb, 10)
        self.create_subscription(String, '/fake/lidar_control', self._control_cb, 10)
        self.scan_pub = self.create_publisher(LaserScan, '/scan', 10)
        self.create_timer(1.0 / self.rate, self.publish_scan)
        self.create_timer(0.02, self.integrate)

        mode = '맵 기반' if self.use_map else '가상 룸'
        extra_info = f' | 폴리곤 장애물 {len(self.extra_poly)}점' if self.extra_poly else ''
        self.get_logger().info(
            f'Fake Lidar 시작 [{mode}] | {self.rate}Hz, {self.N}샘플{extra_info} | '
            f'시작: ({self.init_x:.2f}, {self.init_y:.2f}, {self.init_yaw:.2f}) | '
            f'max_v={self.max_v}m/s, max_a={self.max_a}m/s²'
        )

    def _load_map(self, yaml_path):
        try:
            import yaml
        except ImportError:
            raise RuntimeError('PyYAML이 설치되어 있어야 합니다')

        with open(yaml_path, 'r') as f:
            meta = yaml.safe_load(f)

        self.map_resolution = float(meta['resolution'])
        origin = meta['origin']
        self.map_origin_x = float(origin[0])
        self.map_origin_y = float(origin[1])
        negate = int(meta.get('negate', 0))
        occ_thresh = float(meta.get('occupied_thresh', 0.65))

        image_rel = meta['image']
        image_path = image_rel if os.path.isabs(image_rel) else os.path.join(
            os.path.dirname(os.path.abspath(yaml_path)), image_rel)

        pgm, w, h = load_pgm(image_path)
        self.map_w = w
        self.map_h = h

        thr = occ_thresh * 255.0
        if negate:
            self.occ_grid = [[(p >= thr) for p in row] for row in pgm]
        else:
            self.occ_grid = [[((255 - p) >= thr) for p in row] for row in pgm]

        w_m = w * self.map_resolution
        h_m = h * self.map_resolution
        self.get_logger().info(
            f'\n========== 맵 로드 완료 ==========\n'
            f'  파일: {image_path}\n'
            f'  픽셀: {w} × {h} (해상도 {self.map_resolution} m/px)\n'
            f'  월드 크기: {w_m:.2f} m × {h_m:.2f} m\n'
            f'  X 범위: [{self.map_origin_x:+.2f}, {self.map_origin_x + w_m:+.2f}]\n'
            f'  Y 범위: [{self.map_origin_y:+.2f}, {self.map_origin_y + h_m:+.2f}]\n'
            f'================================'
        )

    def _setup_virtual_room(self):
        self.xmin = float(self.get_parameter('room_x_min').value or -5.0)
        self.xmax = float(self.get_parameter('room_x_max').value or 5.0)
        self.ymin = float(self.get_parameter('room_y_min').value or -5.0)
        self.ymax = float(self.get_parameter('room_y_max').value or 5.0)

        obs_param = self.get_parameter('obstacles').value
        obs_flat = list(obs_param) if obs_param is not None else []
        self.obstacles = []
        for i in range(0, len(obs_flat) - 3, 4):
            self.obstacles.append((
                float(obs_flat[i]), float(obs_flat[i + 1]),
                float(obs_flat[i + 2]), float(obs_flat[i + 3]),
            ))

    def cmd_cb(self, msg: Twist):
        self.v_cmd = float(msg.linear.x)
        self.w_cmd = float(msg.angular.z)
        self.last_cmd_time = self.get_clock().now()

    def _control_cb(self, msg: String):
        cmd = msg.data.strip().lower()

        if cmd == 'lost':
            self.publishing_enabled = False
            self.get_logger().info('🔌 LiDAR 발행 중단 (sensor_lost 시뮬)')
        elif cmd == 'restore':
            self.publishing_enabled = True
            self.get_logger().info('✓ LiDAR 발행 재개')
        elif cmd == 'obstacle_front':
            self.force_obstacle_front = True
            self.get_logger().info('⚠ 전방 장애물 강제 (raycasting 무시)')
        elif cmd == 'obstacle_back':
            self.force_obstacle_back = True
            self.get_logger().info('⚠ 후방 장애물 강제')
        elif cmd == 'clear_obstacle':
            self.force_obstacle_front = False
            self.force_obstacle_back = False
            self.get_logger().info('✓ 강제 장애물 해제')
        elif cmd == 'teleport':
            self.x += 1.5
            self.y += 1.5
            self.get_logger().info(f'🚀 위치 점프 → ({self.x:.2f}, {self.y:.2f}) (AMCL 분실 유도)')
        elif cmd == 'reset':
            self.publishing_enabled = True
            self.force_obstacle_front = False
            self.force_obstacle_back = False
            self.x = self.init_x
            self.y = self.init_y
            self.yaw = self.init_yaw
            self.get_logger().info('🔄 LiDAR 전체 리셋')
        else:
            self.get_logger().warn(f'알 수 없는 lidar 명령: "{cmd}"')

    def integrate(self):
        now = self.get_clock().now()
        dt = (now - self.last_int_time).nanoseconds * 1e-9
        if dt <= 0.0:
            return
        self.last_int_time = now

        if (now - self.last_cmd_time).nanoseconds * 1e-9 > self.cmd_timeout:
            v_target, w_target = 0.0, 0.0
        else:
            v_target, w_target = self.v_cmd, self.w_cmd

        v_target = max(-self.max_v, min(self.max_v, v_target))
        w_target = max(-self.max_w, min(self.max_w, w_target))

        max_dv = self.max_a * dt
        max_dw = self.max_alpha * dt
        dv = max(-max_dv, min(max_dv, v_target - self.v_applied))
        dw = max(-max_dw, min(max_dw, w_target - self.w_applied))
        self.v_applied += dv
        self.w_applied += dw

        self.x += self.v_applied * math.cos(self.yaw) * dt
        self.y += self.v_applied * math.sin(self.yaw) * dt
        self.yaw += self.w_applied * dt

    def raycast_map(self, angle_world: float) -> float:
        cos_a = math.cos(angle_world)
        sin_a = math.sin(angle_world)
        step = self.map_resolution * 0.5
        n_steps = int(self.rmax / step) + 1

        for i in range(1, n_steps + 1):
            t = i * step
            if t > self.rmax:
                return self.rmax
            wx = self.x + t * cos_a
            wy = self.y + t * sin_a
            col = int((wx - self.map_origin_x) / self.map_resolution)
            image_row = self.map_h - 1 - int((wy - self.map_origin_y) / self.map_resolution)
            if 0 <= col < self.map_w and 0 <= image_row < self.map_h:
                if self.occ_grid[image_row][col]:
                    return t
            else:
                return self.rmax
        return self.rmax

    def raycast_room(self, angle_world: float) -> float:
        cos_a = math.cos(angle_world)
        sin_a = math.sin(angle_world)
        best = self.rmax

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

        for (xmn, xmx, ymn, ymx) in self.obstacles:
            t_enter, t_exit = 0.0, best
            if abs(cos_a) < 1e-9:
                if not (xmn <= self.x <= xmx):
                    continue
            else:
                tx1 = (xmn - self.x) / cos_a
                tx2 = (xmx - self.x) / cos_a
                t_lo, t_hi = (tx1, tx2) if tx1 < tx2 else (tx2, tx1)
                t_enter = max(t_enter, t_lo)
                t_exit = min(t_exit, t_hi)
                if t_enter > t_exit:
                    continue
            if abs(sin_a) < 1e-9:
                if not (ymn <= self.y <= ymx):
                    continue
            else:
                ty1 = (ymn - self.y) / sin_a
                ty2 = (ymx - self.y) / sin_a
                t_lo, t_hi = (ty1, ty2) if ty1 < ty2 else (ty2, ty1)
                t_enter = max(t_enter, t_lo)
                t_exit = min(t_exit, t_hi)
                if t_enter > t_exit:
                    continue
            if 0.0 < t_enter < best:
                best = t_enter
        return best

    def _point_in_polygon(self, px: float, py: float) -> bool:
        n = len(self.extra_poly)
        if n < 3:
            return False
        inside = False
        j = n - 1
        for i in range(n):
            xi, yi = self.extra_poly[i]
            xj, yj = self.extra_poly[j]
            if ((yi > py) != (yj > py)):
                if (yj - yi) != 0.0:
                    x_intersect = (xj - xi) * (py - yi) / (yj - yi) + xi
                    if px < x_intersect:
                        inside = not inside
            j = i
        return inside

    def raycast_polygon(self, angle_world: float) -> float:
        if not self.extra_poly:
            return self.rmax
        cos_a = math.cos(angle_world)
        sin_a = math.sin(angle_world)
        step = 0.02  
        n_steps = int(self.rmax / step) + 1
        for i in range(1, n_steps + 1):
            t = i * step
            if t > self.rmax:
                return self.rmax
            wx = self.x + t * cos_a
            wy = self.y + t * sin_a
            if self._point_in_polygon(wx, wy):
                return t
        return self.rmax

    def publish_scan(self):
        if not self.publishing_enabled:
            return

        now = self.get_clock().now()
        scan = LaserScan()
        scan.header.stamp = now.to_msg()
        scan.header.frame_id = self.laser_frame
        scan.angle_min = -math.pi
        scan.angle_max = math.pi
        scan.angle_increment = (2.0 * math.pi) / self.N
        scan.time_increment = 0.0
        scan.scan_time = 1.0 / self.rate
        scan.range_min = self.rmin
        scan.range_max = self.rmax

        raycast = self.raycast_map if self.use_map else self.raycast_room
        force_ang_thresh = math.radians(15.0)

        ranges = [0.0] * self.N
        for i in range(self.N):
            angle_local = scan.angle_min + i * scan.angle_increment
            angle_world = self.yaw + angle_local

            if self.force_obstacle_front and abs(angle_local) < force_ang_thresh:
                r = 0.30
            elif self.force_obstacle_back and abs(abs(angle_local) - math.pi) < force_ang_thresh:
                r = 0.15
            else:
                r_main = float(raycast(angle_world))
                r_poly = float(self.raycast_polygon(angle_world))
                r = min(r_main, r_poly)

            r += random.gauss(0.0, self.noise)
            if r < self.rmin or r > self.rmax:
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