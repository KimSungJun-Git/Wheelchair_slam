import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch_ros.actions import Node
from launch.substitutions import LaunchConfiguration
from launch.launch_description_sources import PythonLaunchDescriptionSource

def generate_launch_description():
    # 1. 경로 설정 (우리 패키지 및 Nav2 공식 패키지)
    pkg_dir = get_package_share_directory('wheelchair_robot_navigation2')
    nav2_launch_dir = os.path.join(get_package_share_directory('nav2_bringup'), 'launch')

    rviz_config = os.path.join(pkg_dir, 'rviz', 'wheelchair_robot_navigation2.rviz')
    default_map = os.path.join(pkg_dir, 'map', 'wheelchair_robot_world.yaml')
    default_param = os.path.join(pkg_dir, 'param', 'wheelchair_robot.yaml')

    # 2. 실행 인자(Arguments) 정의
    use_sim_time = LaunchConfiguration('use_sim_time', default='false')
    map_path = LaunchConfiguration('map', default=default_map)
    param_path = LaunchConfiguration('params_file', default=default_param)

    return LaunchDescription([
        # 인자 선언 (간소화)
        DeclareLaunchArgument('map', default_value=map_path),
        DeclareLaunchArgument('params_file', default_value=param_path),
        DeclareLaunchArgument('use_sim_time', default_value='false'),

        # Nav2 공식 Bringup 런치 포함 (가장 중요한 부분)
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([nav2_launch_dir, '/bringup_launch.py']),
            launch_arguments={
                'map': map_path,
                'use_sim_time': use_sim_time,
                'params_file': param_path
            }.items()),

        # RViz2 실행
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            arguments=['-d', rviz_config],
            parameters=[{'use_sim_time': use_sim_time}],
            output='screen'),
    ])