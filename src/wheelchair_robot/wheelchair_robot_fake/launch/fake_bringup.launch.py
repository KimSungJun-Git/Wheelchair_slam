"""
fake_bringup.launch.py
========================
가짜 센서로 RViz에서 위치 추정을 띄우기 위한 가장 가벼운 통합 런치.

실행되는 노드:
  1. robot_state_publisher : URDF 기반 TF
  2. fake_encoder_node     : /cmd_vel 적분 → /odom
  3. fake_imu_node         : /cmd_vel 적분 → /imu/data
  4. fake_lidar_node       : 가상 룸 레이캐스팅 → /scan
  5. ekf_filter_node       : /odom + /imu/data 융합
  6. rviz2 (옵션)

기본은 fake_lidar 내장 가상 룸([-5,5]×[-5,5]m + 박스 2개)을 사용.

room_from_map:=<map.yaml> 옵션을 주면 그 맵의 크기/원점에 맞춰
가상 룸 외벽을 자동으로 맞춘다 (장애물 박스는 그대로 유지).
실제 맵 raycasting이 필요하면 fake_lidar의 map_yaml 파라미터를 직접 쓸 것.

실행:
  ros2 launch wheelchair_robot_fake fake_bringup.launch.py
  ros2 launch wheelchair_robot_fake fake_bringup.launch.py use_rviz:=false
  ros2 launch wheelchair_robot_fake fake_bringup.launch.py \\
      room_from_map:=$(ros2 pkg prefix wheelchair_robot_navigation2)/share/wheelchair_robot_navigation2/map/wheelchair_robot_world.yaml

운전 (별도 터미널):
  ros2 run teleop_twist_keyboard teleop_twist_keyboard
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _read_pgm_size(pgm_path):
    """PGM 헤더에서 (w, h)만 읽음."""
    with open(pgm_path, 'rb') as f:
        magic = f.readline().strip()
        if magic not in (b'P5', b'P2'):
            raise ValueError(f'PGM 매직 오류: {magic!r}')

        def next_tok():
            while True:
                line = f.readline()
                if not line:
                    raise ValueError('PGM 헤더 종료')
                line = line.strip()
                if line and not line.startswith(b'#'):
                    return line

        tokens = next_tok().split()
        while len(tokens) < 2:
            tokens += next_tok().split()
        return int(tokens[0]), int(tokens[1])


def _setup_fake_lidar(context, *args, **kwargs):
    """런타임에 room_from_map 평가해서 fake_lidar 노드 생성."""
    desc_pkg = get_package_share_directory('wheelchair_robot_description')
    rviz_config = os.path.join(desc_pkg, 'rviz', 'wheelchair_robot_model.rviz')

    room_from_map = LaunchConfiguration('room_from_map').perform(context).strip()
    use_rviz = LaunchConfiguration('use_rviz').perform(context).lower() == 'true'

    lidar_params = {}
    if room_from_map:
        # 맵 yaml에서 크기 추출 → 가상 룸 외벽 좌표로 사용
        try:
            import yaml
        except ImportError:
            print('⚠ PyYAML 없음. 기본 가상 룸 사용.')
            yaml = None

        if yaml is not None and os.path.exists(room_from_map):
            with open(room_from_map, 'r') as f:
                meta = yaml.safe_load(f)
            res = float(meta['resolution'])
            origin = meta['origin']
            img_rel = meta['image']
            img_path = img_rel if os.path.isabs(img_rel) else os.path.join(
                os.path.dirname(room_from_map), img_rel)
            w, h = _read_pgm_size(img_path)
            x_min = float(origin[0])
            y_min = float(origin[1])
            x_max = x_min + w * res
            y_max = y_min + h * res
            lidar_params = {
                'room_x_min': x_min,
                'room_x_max': x_max,
                'room_y_min': y_min,
                'room_y_max': y_max,
            }
            print(f'✓ 가상 룸 크기를 맵에 맞춤: X[{x_min:+.2f},{x_max:+.2f}] Y[{y_min:+.2f},{y_max:+.2f}]')
        else:
            print(f'⚠ room_from_map 경로 무효: {room_from_map}. 기본 룸 사용.')

    nodes = [
        Node(
            package='wheelchair_robot_fake',
            executable='fake_lidar_node',
            name='fake_lidar_node',
            output='screen',
            parameters=[lidar_params] if lidar_params else [],
        ),
    ]
    if use_rviz:
        nodes.append(Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            output='screen',
            arguments=['-d', rviz_config],
        ))
    return nodes


def generate_launch_description():
    desc_pkg = get_package_share_directory('wheelchair_robot_description')
    control_pkg = get_package_share_directory('wheelchair_robot_control')

    urdf_file = os.path.join(desc_pkg, 'urdf', 'wheelchair_robot.urdf')
    ekf_config = os.path.join(control_pkg, 'config', 'ekf.yaml')

    with open(urdf_file, 'r') as f:
        robot_desc = f.read()

    return LaunchDescription([
        DeclareLaunchArgument('use_rviz', default_value='true'),
        DeclareLaunchArgument(
            'room_from_map', default_value='',
            description='맵 yaml 경로 지정 시 가상 룸 외벽 크기를 그 맵에 맞춤'),

        # 1. URDF
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='screen',
            parameters=[{'robot_description': robot_desc, 'use_sim_time': False}],
        ),

        # 2~3. fake encoder/imu
        Node(
            package='wheelchair_robot_fake', executable='fake_encoder_node',
            name='fake_encoder_node', output='screen',
        ),
        Node(
            package='wheelchair_robot_fake', executable='fake_imu_node',
            name='fake_imu_node', output='screen',
        ),
        
        # 4. 안전 정지 노드(Safety Stop) 헬스체크 통과를 위한 가짜 초음파 센서
        Node(
            package='wheelchair_robot_fake', executable='fake_ultrasonic_node',
            name='fake_ultrasonic_node', output='screen',
        ),

        # 5. EKF
        Node(
            package='robot_localization', executable='ekf_node',
            name='ekf_filter_node', output='screen',
            parameters=[ekf_config, {'use_sim_time': False}],
        ),

        # 4 + 6. fake_lidar + RViz는 OpaqueFunction에서 (room_from_map 처리)
        OpaqueFunction(function=_setup_fake_lidar),
    ])
