"""
fake_localization.launch.py
=============================
가짜 센서로 기존 맵에 AMCL 위치추정을 띄운다 (지도 작성 X, 위치추정 O).

실행 흐름:
  1. robot_state_publisher : URDF 기반 TF
  2. fake_encoder_node     : /cmd_vel 적분 → /odom
  3. fake_imu_node         : /cmd_vel 적분 → /imu/data
  4. fake_lidar_node       : 기존 맵(wheelchair_robot_world.yaml)에 레이캐스팅 → /scan
  5. ekf_filter_node       : /odom + /imu/data → odom → base_footprint TF
  6. map_server            : 기존 맵을 /map으로 발행
  7. amcl                  : /scan + /map → map → odom TF, /amcl_pose 발행
  8. lifecycle_manager     : 위 둘 자동 활성화
  9. (auto) /initialpose   : 5초 후 자동 발행 → AMCL 입자 수렴 (RViz 클릭 불필요)
 10. rviz2

사용:
  ros2 launch wheelchair_robot_fake fake_localization.launch.py

별도 터미널에서:
  ros2 run teleop_twist_keyboard teleop_twist_keyboard

런치 인자:
  initial_x:=1.0 initial_y:=0.5 initial_yaw:=0.0     # 맵 안에서 시작 위치
  map:=/path/to/custom_map.yaml                       # 다른 맵 쓰고 싶을 때
  use_rviz:=false                                     # RViz 끄기
  auto_init:=false                                    # 자동 initial pose 발행 끄기
"""
import math
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument, ExecuteProcess, OpaqueFunction, TimerAction,
)
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _make_initial_pose_action(context, *args, **kwargs):
    """런치 인자(initial_x/y/yaw)를 읽어 /initialpose 발행 명령을 만든다.
    auto_init=true 일 때만 5초 후 한 번 발행."""
    auto = LaunchConfiguration('auto_init').perform(context).lower() == 'true'
    if not auto:
        return []

    x = float(LaunchConfiguration('initial_x').perform(context))
    y = float(LaunchConfiguration('initial_y').perform(context))
    yaw = float(LaunchConfiguration('initial_yaw').perform(context))

    qz = math.sin(yaw / 2.0)
    qw = math.cos(yaw / 2.0)

    pose_yaml = (
        "{header: {frame_id: 'map'}, "
        "pose: {pose: "
        f"{{position: {{x: {x}, y: {y}, z: 0.0}}, "
        f"orientation: {{x: 0.0, y: 0.0, z: {qz}, w: {qw}}}}}, "
        "covariance: ["
        "0.25, 0.0, 0.0, 0.0, 0.0, 0.0, "
        "0.0, 0.25, 0.0, 0.0, 0.0, 0.0, "
        "0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "
        "0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "
        "0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "
        "0.0, 0.0, 0.0, 0.0, 0.0, 0.068]}}"
    )

    return [
        TimerAction(
            period=5.0,
            actions=[
                ExecuteProcess(
                    cmd=[
                        'ros2', 'topic', 'pub', '--once', '/initialpose',
                        'geometry_msgs/msg/PoseWithCovarianceStamped',
                        pose_yaml,
                    ],
                    output='screen',
                )
            ],
        )
    ]


def generate_launch_description():
    desc_pkg = get_package_share_directory('wheelchair_robot_description')
    control_pkg = get_package_share_directory('wheelchair_robot_control')
    nav2_pkg = get_package_share_directory('wheelchair_robot_navigation2')

    urdf_file = os.path.join(desc_pkg, 'urdf', 'wheelchair_robot.urdf')
    ekf_config = os.path.join(control_pkg, 'config', 'ekf.yaml')
    default_map = os.path.join(nav2_pkg, 'map', 'wheelchair_robot_world.yaml')
    nav2_params = os.path.join(nav2_pkg, 'param', 'wheelchair_robot.yaml')
    rviz_config = os.path.join(nav2_pkg, 'rviz', 'wheelchair_robot_navigation2.rviz')

    with open(urdf_file, 'r') as f:
        robot_desc = f.read()

    map_yaml = LaunchConfiguration('map')
    initial_x = LaunchConfiguration('initial_x')
    initial_y = LaunchConfiguration('initial_y')
    initial_yaw = LaunchConfiguration('initial_yaw')
    use_rviz = LaunchConfiguration('use_rviz')

    return LaunchDescription([
        # ── 인자 ───────────────────────────────────────────────────
        DeclareLaunchArgument('map', default_value=default_map,
                              description='로딩할 맵 YAML 절대경로'),
        DeclareLaunchArgument('initial_x', default_value='0.0',
                              description='맵 안 시작 X (m)'),
        DeclareLaunchArgument('initial_y', default_value='0.0',
                              description='맵 안 시작 Y (m)'),
        DeclareLaunchArgument('initial_yaw', default_value='0.0',
                              description='맵 안 시작 yaw (rad)'),
        DeclareLaunchArgument('use_rviz', default_value='true'),
        DeclareLaunchArgument('auto_init', default_value='true',
                              description='5초 후 /initialpose 자동 발행 여부'),

        # 1. URDF → TF
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='screen',
            parameters=[{'robot_description': robot_desc, 'use_sim_time': False}],
        ),

        # 2~4. 가짜 센서 3종
        Node(
            package='wheelchair_robot_fake',
            executable='fake_encoder_node',
            name='fake_encoder_node',
            output='screen',
        ),
        Node(
            package='wheelchair_robot_fake',
            executable='fake_imu_node',
            name='fake_imu_node',
            output='screen',
        ),
        Node(
            package='wheelchair_robot_fake',
            executable='fake_lidar_node',
            name='fake_lidar_node',
            output='screen',
            parameters=[{
                'map_yaml': map_yaml,
                'initial_map_x': initial_x,
                'initial_map_y': initial_y,
                'initial_map_yaw': initial_yaw,
            }],
        ),

        # 4'. 가짜 초음파 (선택적, safety_stop과 함께 사용 시 필요)
        Node(
            package='wheelchair_robot_fake',
            executable='fake_ultrasonic_node',
            name='fake_ultrasonic_node',
            output='screen',
        ),

        # 5. EKF
        Node(
            package='robot_localization',
            executable='ekf_node',
            name='ekf_filter_node',
            output='screen',
            parameters=[ekf_config, {'use_sim_time': False}],
        ),

        # 6. Map Server
        Node(
            package='nav2_map_server',
            executable='map_server',
            name='map_server',
            output='screen',
            parameters=[{
                'yaml_filename': map_yaml,
                'topic_name': 'map',
                'frame_id': 'map',
                'use_sim_time': False,
            }],
        ),

        # 7. AMCL
        Node(
            package='nav2_amcl',
            executable='amcl',
            name='amcl',
            output='screen',
            parameters=[nav2_params, {'use_sim_time': False}],
        ),

        # 8. Lifecycle Manager
        Node(
            package='nav2_lifecycle_manager',
            executable='lifecycle_manager',
            name='lifecycle_manager_localization',
            output='screen',
            parameters=[{
                'use_sim_time': False,
                'autostart': True,
                'node_names': ['map_server', 'amcl'],
            }],
        ),

        # 9. 자동 initial pose
        OpaqueFunction(function=_make_initial_pose_action),

        # 10. RViz
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            output='screen',
            arguments=['-d', rviz_config],
            condition=IfCondition(use_rviz),
        ),
    ])
