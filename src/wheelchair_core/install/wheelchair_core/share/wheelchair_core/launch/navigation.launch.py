import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    pkg_share = get_package_share_directory('wheelchair_core')
    
    # 1. 경로 설정
    map_file = LaunchConfiguration('map', default=os.path.join(pkg_share, 'maps', 'wheelchair_map.yaml'))
    nav2_param_file = os.path.join(pkg_share, 'params', 'nav2_params.yaml')
    nav2_launch_dir = os.path.join(get_package_share_directory('nav2_bringup'), 'launch')

    # URDF 로드
    urdf_path = os.path.join(pkg_share, 'urdf', 'wheelchair_core.urdf')
    with open(urdf_path, 'r') as f:
        robot_desc = f.read()

    return LaunchDescription([
        DeclareLaunchArgument('map', default_value=map_file),

        # 2. 로봇 상태 발행 (우리 URDF 사용)
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            parameters=[{
                'robot_description': robot_desc,
                'use_sim_time': True
            }]
        ),

        # 3. Nav2 본체 실행
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(nav2_launch_dir, 'bringup_launch.py')),
            launch_arguments={
                'map': map_file,
                'use_sim_time': 'true',
                'params_file': nav2_param_file}.items(),
            remappings=[('/cmd_vel', '/cmd_vel_nav_internal')]
        ),

        # 4. RViz 실행 (Nav2 전용 설정)
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            arguments=['-d', os.path.join(get_package_share_directory('wheelchair_core'), 'rviz', 'nav.rviz')],
            parameters=[{'use_sim_time': True}],
            output='screen'
        ),
    ])
