#cartographer.launch.py
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch_ros.actions import Node
from launch.launch_description_sources import PythonLaunchDescriptionSource

def generate_launch_description():

    # 1. 실제 트리 구조에 맞춘 패키지 경로들
    desc_pkg = get_package_share_directory('wheelchair_robot_description')
    control_pkg = get_package_share_directory('wheelchair_robot_control')
    carto_pkg = get_package_share_directory('wheelchair_robot_cartographer')

    # 2. 파일 경로 설정 
    urdf_file = os.path.join(desc_pkg, 'urdf', 'wheelchair_robot.urdf')
    ekf_config = os.path.join(control_pkg, 'config', 'ekf.yaml')
    carto_config_dir = os.path.join(carto_pkg, 'config')
    rviz_config = os.path.join(carto_pkg, 'rviz', 'wheelchair_robot_cartographer.rviz')
    occupancy_grid_launch = os.path.join(carto_pkg, 'launch', 'occupancy_grid.launch.py')

    # 3. 로봇 형태(URDF) 파일 읽기
    with open(urdf_file, 'r') as f:
        robot_desc = f.read()

    return LaunchDescription([
        
        # [1] 로봇 뼈대 (TF) 발행
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            parameters=[{'robot_description': robot_desc, 'use_sim_time': False}]
        ),
        
        # [2] 위치 추정 (EKF) 실행 (control의 yaml 사용)
        Node(
            package='robot_localization',
            executable='ekf_node',
            name='ekf_filter_node',
            parameters=[ekf_config, {'use_sim_time': False}]
        ),

        # [3] 지도 작성 (Cartographer) 실행
        Node(
            package='cartographer_ros',
            executable='cartographer_node',
            name='cartographer_node',
            parameters=[{'use_sim_time': False}],
            arguments=[
                '-configuration_directory', carto_config_dir,
                '-configuration_basename', 'wheelchair_robot.lua'
            ]
        ),

        # [4] 2D 맵 변환 (Occupancy Grid) 포함
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([occupancy_grid_launch]),
            launch_arguments={
                'use_sim_time': 'false', 
                'resolution': '0.05',
                'publish_period_sec': '1.0'
            }.items()
        ),

        # [5] 시각화 (RViz2) 실행
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            arguments=['-d', rviz_config],
            parameters=[{'use_sim_time': False}]
        )
    ])