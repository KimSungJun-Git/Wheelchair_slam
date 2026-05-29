"""
fake_slam.launch.py
=====================
fake_bringup 위에 Cartographer까지 실행해서 실제로 가상 룸의 지도를 그려본다.

실행:
  ros2 launch wheelchair_robot_fake fake_slam.launch.py

운전 (별도 터미널):
  ros2 run teleop_twist_keyboard teleop_twist_keyboard

→ 가상 룸을 운전해서 돌아다니면 /map에 직사각형 룸 + 박스 두 개가 점점 그려진다.
  RViz에서 Fixed Frame을 map으로 바꾸고 Map (/map) 디스플레이를 추가하면 확인 가능.
"""
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    desc_pkg = get_package_share_directory('wheelchair_robot_description')
    control_pkg = get_package_share_directory('wheelchair_robot_control')
    carto_pkg = get_package_share_directory('wheelchair_robot_cartographer')

    urdf_file = os.path.join(desc_pkg, 'urdf', 'wheelchair_robot.urdf')
    ekf_config = os.path.join(control_pkg, 'config', 'ekf.yaml')
    carto_config_dir = os.path.join(carto_pkg, 'config')
    rviz_config = os.path.join(carto_pkg, 'rviz', 'wheelchair_robot_cartographer.rviz')
    occupancy_grid_launch = os.path.join(carto_pkg, 'launch', 'occupancy_grid.launch.py')

    with open(urdf_file, 'r') as f:
        robot_desc = f.read()

    use_rviz = LaunchConfiguration('use_rviz')

    return LaunchDescription([
        DeclareLaunchArgument('use_rviz', default_value='true'),

        # 1. URDF
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            parameters=[{'robot_description': robot_desc, 'use_sim_time': False}],
        ),

        # 2~4. 가짜 센서 3종
        Node(package='wheelchair_robot_fake', executable='fake_encoder_node',
             name='fake_encoder_node', output='screen'),
        Node(package='wheelchair_robot_fake', executable='fake_imu_node',
             name='fake_imu_node', output='screen'),
        Node(package='wheelchair_robot_fake', executable='fake_lidar_node',
             name='fake_lidar_node', output='screen'),

        # 5. EKF
        Node(
            package='robot_localization',
            executable='ekf_node',
            name='ekf_filter_node',
            parameters=[ekf_config, {'use_sim_time': False}],
        ),

        # 6. Cartographer
        Node(
            package='cartographer_ros',
            executable='cartographer_node',
            name='cartographer_node',
            parameters=[{'use_sim_time': False}],
            arguments=[
                '-configuration_directory', carto_config_dir,
                '-configuration_basename', 'wheelchair_robot.lua'
            ],
        ),

        # 7. Occupancy Grid 변환
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([occupancy_grid_launch]),
            launch_arguments={
                'use_sim_time': 'false',
                'resolution': '0.05',
                'publish_period_sec': '1.0'
            }.items()
        ),

        # 8. RViz (카토그라퍼 전용 뷰)
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            arguments=['-d', rviz_config],
            parameters=[{'use_sim_time': False}],
            condition=IfCondition(use_rviz),
        ),
    ])
