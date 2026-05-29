"""
fake_bringup.launch.py
========================
가짜 센서로 RViz에서 위치 추정을 띄우기 위한 통합 런치.

실행되는 노드:
  1. robot_state_publisher : URDF 기반 TF (base_footprint → base_link → imu_link/laser_frame)
  2. fake_encoder_node     : /cmd_vel 적분 → /odom 발행
  3. fake_imu_node         : /cmd_vel 적분 → /imu/data 발행
  4. fake_lidar_node       : 가상 룸 레이캐스팅 → /scan 발행
  5. ekf_filter_node       : /odom + /imu/data 융합 → odom → base_footprint TF 발행
  6. rviz2 (옵션)          : 시각화

실행:
  ros2 launch wheelchair_robot_fake fake_bringup.launch.py
  # RViz 없이:
  ros2 launch wheelchair_robot_fake fake_bringup.launch.py use_rviz:=false

운전 (별도 터미널):
  ros2 run teleop_twist_keyboard teleop_twist_keyboard
"""
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    desc_pkg = get_package_share_directory('wheelchair_robot_description')
    control_pkg = get_package_share_directory('wheelchair_robot_control')

    urdf_file = os.path.join(desc_pkg, 'urdf', 'wheelchair_robot.urdf')
    ekf_config = os.path.join(control_pkg, 'config', 'ekf.yaml')
    rviz_config = os.path.join(desc_pkg, 'rviz', 'wheelchair_robot_model.rviz')

    with open(urdf_file, 'r') as f:
        robot_desc = f.read()

    use_rviz = LaunchConfiguration('use_rviz')

    return LaunchDescription([
        DeclareLaunchArgument(
            'use_rviz', default_value='true',
            description='RViz2를 함께 실행할지 여부'),

        # 1. URDF 기반 TF 발행
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='screen',
            parameters=[{'robot_description': robot_desc, 'use_sim_time': False}],
        ),

        # 2. 가짜 엔코더 → /odom
        Node(
            package='wheelchair_robot_fake',
            executable='fake_encoder_node',
            name='fake_encoder_node',
            output='screen',
        ),

        # 3. 가짜 IMU → /imu/data
        Node(
            package='wheelchair_robot_fake',
            executable='fake_imu_node',
            name='fake_imu_node',
            output='screen',
        ),

        # 4. 가짜 라이다 → /scan
        Node(
            package='wheelchair_robot_fake',
            executable='fake_lidar_node',
            name='fake_lidar_node',
            output='screen',
        ),

        # 5. EKF: /odom + /imu/data → odom → base_footprint TF
        Node(
            package='robot_localization',
            executable='ekf_node',
            name='ekf_filter_node',
            output='screen',
            parameters=[ekf_config, {'use_sim_time': False}],
        ),

        # 6. RViz2 (옵션)
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            output='screen',
            arguments=['-d', rviz_config],
            condition=IfCondition(use_rviz),
        ),
    ])
