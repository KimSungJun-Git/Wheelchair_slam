#!/usr/bin/env python3
"""
맵 정보 출력 유틸
==================
nav2 map_server 호환 YAML 파일에서 맵 크기/원점/해상도를 읽어 출력한다.
가짜 라이다의 가상 룸 크기를 진짜 맵에 맞추고 싶을 때 사용한다.

사용:
  ros2 run wheelchair_robot_fake map_inspector ~/wheelchair_ws/src/.../wheelchair_robot_world.yaml
"""
import os
import sys


def _read_pgm_header(path):
    """PGM 파일에서 width, height만 빠르게 추출."""
    with open(path, 'rb') as f:
        magic = f.readline().strip()
        if magic not in (b'P5', b'P2'):
            raise ValueError(f'지원하지 않는 PGM 매직: {magic!r}')

        def next_token_line():
            while True:
                line = f.readline()
                if not line:
                    raise ValueError('PGM 헤더 종료')
                line = line.strip()
                if not line or line.startswith(b'#'):
                    continue
                return line

        tokens = next_token_line().split()
        while len(tokens) < 2:
            tokens += next_token_line().split()
        return int(tokens[0]), int(tokens[1])


def main():
    if len(sys.argv) < 2:
        print('사용법: ros2 run wheelchair_robot_fake map_inspector <map.yaml>')
        sys.exit(1)

    yaml_path = os.path.abspath(sys.argv[1])
    if not os.path.exists(yaml_path):
        print(f'❌ 파일 없음: {yaml_path}')
        sys.exit(1)

    try:
        import yaml
    except ImportError:
        print('❌ PyYAML 필요: pip install pyyaml')
        sys.exit(1)

    with open(yaml_path, 'r') as f:
        meta = yaml.safe_load(f)

    res = float(meta['resolution'])
    origin = meta['origin']
    img_rel = meta['image']
    img_path = img_rel if os.path.isabs(img_rel) else os.path.join(
        os.path.dirname(yaml_path), img_rel)

    if not os.path.exists(img_path):
        print(f'❌ PGM 이미지 없음: {img_path}')
        sys.exit(1)

    w, h = _read_pgm_header(img_path)
    w_m = w * res
    h_m = h * res
    x_min = float(origin[0])
    y_min = float(origin[1])
    x_max = x_min + w_m
    y_max = y_min + h_m

    print()
    print('=' * 60)
    print(f'  맵 파일: {os.path.basename(yaml_path)}')
    print('=' * 60)
    print(f'  YAML:       {yaml_path}')
    print(f'  이미지:     {img_path}')
    print(f'  픽셀 크기:  {w} × {h}')
    print(f'  해상도:     {res} m/픽셀')
    print(f'  월드 크기:  {w_m:.2f} m × {h_m:.2f} m')
    print(f'  X 범위:     [{x_min:+.2f}, {x_max:+.2f}]')
    print(f'  Y 범위:     [{y_min:+.2f}, {y_max:+.2f}]')
    print(f'  Origin:     ({x_min:+.2f}, {y_min:+.2f})')
    print()
    print('  → fake_lidar 가상 룸 파라미터로 그대로 사용:')
    print(f'    -p room_x_min:={x_min:.2f} -p room_x_max:={x_max:.2f} \\')
    print(f'    -p room_y_min:={y_min:.2f} -p room_y_max:={y_max:.2f}')
    print()
    print('  → 또는 실제 맵 raycasting 사용 (권장):')
    print(f'    -p map_yaml:={yaml_path}')
    print()


if __name__ == '__main__':
    main()
