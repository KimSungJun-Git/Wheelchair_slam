#bringup_cartographer.launch.py

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node
#bringup_cartographer.launch.py
def generate_launch_description():

    # 1. 패키지 경로
    desc_pkg = get_package_share_directory('wheelchair_robot_description')
    control_pkg = get_package_share_directory('wheelchair_robot_control')

    # 2. 파일 경로 설정
    urdf_file = os.path.join(desc_pkg, 'urdf', 'wheelchair_robot.urdf')
    ekf_config = os.path.join(control_pkg, 'config', 'ekf.yaml')

    # 3. URDF 파일 읽기
    with open(urdf_file, 'r') as f:
        robot_desc = f.read()

    return LaunchDescription([

        # [1] 로봇 뼈대 (TF) 발행
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            parameters=[{'robot_description': robot_desc, 'use_sim_time': False}]
        ),

        # [2] 위치 추정 (EKF) 실행
        Node(
            package='robot_localization',
            executable='ekf_node',
            name='ekf_filter_node',
            parameters=[ekf_config, {'use_sim_time': False}]
        ),
        
    ])