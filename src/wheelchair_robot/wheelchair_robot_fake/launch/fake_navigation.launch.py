"""
fake_navigation.launch.py
===========================
하드웨어 없이 프로젝트 전체 파이프라인을 실행하는 통합 런치.

기존 wheelchair_robot_navigation2/launch/navigation2.launch.py 를 그대로 include하므로,
다음이 자동으로 동작:
  - Nav2 풀 스택 (AMCL, Planner, Controller, BT Navigator, Behavior, Smoother)
  - safety_stop_node (LiDAR 거리 + AMCL zone 기반 감속/정지)
  - Keepout filter (접근 금지 구역)
  - Speed filter (서행 구역)
  - Nav2 → /cmd_vel_nav SetRemap
  - RViz2 (Nav2 설정)

fake 패키지가 추가로 띄우는 것:
  - URDF TF (robot_state_publisher)
  - fake_encoder_node       → /odom
  - fake_imu_node          → /imu/data
  - fake_lidar_node        → /scan (실제 맵 raycasting)
  - ekf_filter_node        → odom → base_footprint TF
  - mode_switch_node       → /cmd_vel_safe + /cmd_vel_teleop → /cmd_vel
  - localization_monitor_node
  - imu_safety_node
  - (옵션) cmd_vel relay   → mode_switch 대신 /cmd_vel_safe를 /cmd_vel로 직결
  - /initialpose 자동 발행

cmd_vel 흐름 (use_relay=false, 기본):
  Nav2 → /cmd_vel_nav → safety_stop → /cmd_vel_safe → mode_switch_node → /cmd_vel → fake_encoder

  mode_switch_node는 기본 manual 모드라 /cmd_vel을 발행하지 않는다.
  → 자동주행 테스트하려면:
     (a) ros2 topic pub /destination std_msgs/String "data: 'room_101'" --once
         (목적지 수신 시 mode_switch가 auto로 자동 전환 + Nav2 goal 보냄)
     (b) 또는 use_relay:=true 로 띄우면 mode_switch 우회하고 패스스루로 직결

cmd_vel 흐름 (use_relay=true):
  Nav2 → /cmd_vel_nav → safety_stop → /cmd_vel_safe → relay → /cmd_vel → fake_encoder
  RViz의 Nav2 Goal 버튼만으로도 즉시 동작.

사용:
  # 기본 (mode_switch 풀스택)
  ros2 launch wheelchair_robot_fake fake_navigation.launch.py

  # mode_switch 우회 (RViz Nav2 Goal로 바로 테스트)
  ros2 launch wheelchair_robot_fake fake_navigation.launch.py use_relay:=true

  # 다른 시작 위치
  ros2 launch wheelchair_robot_fake fake_navigation.launch.py \\
      initial_x:=1.8 initial_y:=1.2 initial_yaw:=0.0
"""
import math
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription,
    OpaqueFunction, TimerAction,
)
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _make_initial_pose_action(context, *args, **kwargs):
    """Nav2 라이프사이클 활성화 후 /initialpose 한 번 발행."""
    auto = LaunchConfiguration('auto_init').perform(context).lower() == 'true'
    if not auto:
        return []
    x = float(LaunchConfiguration('initial_x').perform(context))
    y = float(LaunchConfiguration('initial_y').perform(context))
    yaw = float(LaunchConfiguration('initial_yaw').perform(context))
    qz, qw = math.sin(yaw / 2.0), math.cos(yaw / 2.0)
    pose_yaml = (
        "{header: {frame_id: 'map'}, pose: {pose: "
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
            period=12.0,  # Nav2 부팅 + lifecycle 활성화 대기
            actions=[
                ExecuteProcess(
                    cmd=['ros2', 'topic', 'pub', '--once', '/initialpose',
                         'geometry_msgs/msg/PoseWithCovarianceStamped',
                         pose_yaml],
                    output='screen',
                ),
            ],
        )
    ]


def generate_launch_description():
    # ── 패키지 경로 ──────────────────────────────────────────────
    desc_pkg = get_package_share_directory('wheelchair_robot_description')
    control_pkg = get_package_share_directory('wheelchair_robot_control')
    nav2_pkg = get_package_share_directory('wheelchair_robot_navigation2')

    urdf_file = os.path.join(desc_pkg, 'urdf', 'wheelchair_robot.urdf')
    ekf_config = os.path.join(control_pkg, 'config', 'ekf.yaml')
    default_map = os.path.join(nav2_pkg, 'map', 'wheelchair_robot_world.yaml')
    nav2_launch_file = os.path.join(nav2_pkg, 'launch', 'navigation2.launch.py')

    with open(urdf_file, 'r') as f:
        robot_desc = f.read()

    # ── 런치 인자 ──────────────────────────────────────────────
    map_yaml = LaunchConfiguration('map')
    initial_x = LaunchConfiguration('initial_x')
    initial_y = LaunchConfiguration('initial_y')
    initial_yaw = LaunchConfiguration('initial_yaw')
    use_relay = LaunchConfiguration('use_relay')
    enable_imu_safety = LaunchConfiguration('enable_imu_safety')
    enable_loc_monitor = LaunchConfiguration('enable_loc_monitor')

    return LaunchDescription([
        # ── 인자 선언 ──────────────────────────────────────────
        DeclareLaunchArgument('map', default_value=default_map,
                              description='로딩할 맵 YAML 절대경로'),
        DeclareLaunchArgument('initial_x', default_value='0.0',
                              description='맵 안 시작 X (m)'),
        DeclareLaunchArgument('initial_y', default_value='0.0',
                              description='맵 안 시작 Y (m)'),
        DeclareLaunchArgument('initial_yaw', default_value='0.0',
                              description='맵 안 시작 yaw (rad)'),
        DeclareLaunchArgument('auto_init', default_value='true',
                              description='12초 후 /initialpose 자동 발행'),
        DeclareLaunchArgument('use_relay', default_value='false',
                              description='true면 mode_switch 대신 /cmd_vel_safe→/cmd_vel 직결'),
        DeclareLaunchArgument('enable_imu_safety', default_value='true'),
        DeclareLaunchArgument('enable_loc_monitor', default_value='true'),

        # ── 1. URDF → TF ───────────────────────────────────────
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='screen',
            parameters=[{'robot_description': robot_desc, 'use_sim_time': False}],
        ),

        # ── 2~4. fake 센서 3종 ─────────────────────────────────
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

        # 4'. 가짜 초음파 3종 (safety_stop의 sensor_health 통과시키기 위함)
        Node(
            package='wheelchair_robot_fake',
            executable='fake_ultrasonic_node',
            name='fake_ultrasonic_node',
            output='screen',
        ),

        # ── 5. EKF (odom → base_footprint TF) ──────────────────
        Node(
            package='robot_localization',
            executable='ekf_node',
            name='ekf_filter_node',
            output='screen',
            parameters=[ekf_config, {'use_sim_time': False}],
        ),

        # ── 6. Nav2 풀스택 + safety_stop + 필터 + RViz ─────────
        # navigation2.launch.py 안에서 모두 설정됨
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(nav2_launch_file),
            launch_arguments={
                'map': map_yaml,
                'use_sim_time': 'false',
            }.items(),
        ),

        # ── 7a. mode_switch_node (use_relay=false 일 때만) ────
        # 키 입력은 fake 런치 환경에서 어렵지만 /destination 토픽으로 제어 가능
        Node(
            package='wheelchair_robot_control',
            executable='mode_switch_node',
            name='mode_switch_node',
            output='screen',
            condition=UnlessCondition(use_relay),
        ),

        # ── 7b. cmd_vel relay (use_relay=true 일 때만) ────────
        # mode_switch 우회: /cmd_vel_safe → /cmd_vel 직결
        Node(
            package='topic_tools',
            executable='relay',
            name='cmd_vel_relay',
            arguments=['/cmd_vel_safe', '/cmd_vel'],
            output='screen',
            condition=IfCondition(use_relay),
        ),

        # ── 8. localization_monitor_node ──────────────────────
        Node(
            package='wheelchair_robot_control',
            executable='localization_monitor_node',
            name='localization_monitor_node',
            output='screen',
            condition=IfCondition(enable_loc_monitor),
        ),

        # ── 9. imu_safety_node ────────────────────────────────
        Node(
            package='wheelchair_robot_control',
            executable='imu_safety_node',
            name='imu_safety_node',
            output='screen',
            condition=IfCondition(enable_imu_safety),
        ),

        # ── 10. /initialpose 자동 발행 ────────────────────────
        OpaqueFunction(function=_make_initial_pose_action),
    ])
