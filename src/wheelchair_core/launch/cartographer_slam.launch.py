#!/usr/bin/env python3

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    pkg_name = 'wheelchair_core'
    pkg_share = get_package_share_directory(pkg_name)
    
    # 1. URDF 파일 로드
    urdf_path = os.path.join(pkg_share, 'urdf', 'wheelchair_core.urdf')
    with open(urdf_path, 'r') as f:
        robot_desc = f.read()

    # ⭐️ RViz2 설정 파일 경로 지정
    rviz_config_path = os.path.join(pkg_share, 'rviz', 'slam.rviz')

    return LaunchDescription([
        # 1. robot_state_publisher
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher', 
            parameters=[{
                'robot_description': robot_desc,
                'use_sim_time': True
            }]
        ),

        # 2. Cartographer 노드
        Node(
            package='cartographer_ros',
            executable='cartographer_node',
            name='cartographer_node',
            parameters=[{'use_sim_time': True}],
            arguments=[
                '-configuration_directory', os.path.join(pkg_share, 'config'),
                '-configuration_basename', 'turtlebot3_lds_2d.lua'
            ],
            remappings=[('scan', '/scan')]
        ),

        # 3. 점유 격자 지도 노드
        Node(
            package='cartographer_ros',
            executable='cartographer_occupancy_grid_node',
            name='cartographer_occupancy_grid_node',
            parameters=[{'use_sim_time': True}],
            arguments=['-resolution', '0.05']
        ),

        # ⭐️ 4. RViz2 (저장된 토픽 설정 파일 불러오기)
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            arguments=['-d', rviz_config_path], # 이 줄이 핵심입니다!
            parameters=[{'use_sim_time': True}],
            output='screen'
        ),
    ])