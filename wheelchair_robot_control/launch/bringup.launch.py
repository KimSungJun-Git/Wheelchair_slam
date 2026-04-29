import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    # 실제 작업 공간 패키지 경로 가져오기
    desc_pkg = get_package_share_directory('wheelchair_robot_description')
    control_pkg = get_package_share_directory('wheelchair_robot_control')
    
    # 파일 경로 지정
    urdf_file = os.path.join(desc_pkg, 'urdf', 'wheelchair_robot.urdf')
    ekf_config = os.path.join(control_pkg, 'config', 'ekf.yaml')
    
    # URDF 파일 읽기
    with open(urdf_file, 'r') as infp:
        robot_desc = infp.read()
        
    return LaunchDescription([
        # 1. 로봇 상태 퍼블리셔 (URDF 뼈대 및 기본 TF 발행)
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='screen',
            parameters=[{'robot_description': robot_desc, 'use_sim_time': False}]
        ),
        
        # 2. EKF 노드 (/odom과 /imu/data를 융합하여 /odometry/filtered 발행)
        Node(
            package='robot_localization',
            executable='ekf_node',
            name='ekf_filter_node',
            output='screen',
            parameters=[ekf_config, {'use_sim_time': False}]
        )
    ])