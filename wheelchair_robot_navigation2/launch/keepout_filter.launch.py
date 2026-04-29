#keepout_filter.launch.py
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    # 패키지 경로 가져오기
    nav2_pkg_dir = get_package_share_directory('wheelchair_robot_navigation2')

    # 마스크 YAML 파일 경로 설정 (기존 /tmp/ 대신 패키지 내부에 있는 테스트 마스크 사용)
    # 만약 기존처럼 외부 경로를 쓰고 싶다면 '/tmp/keepout_test.yaml' 로 수정하시면 됩니다.
    mask_yaml_file = os.path.join(nav2_pkg_dir, 'map', 'test_mask.yaml')

    return LaunchDescription([
        # 1. 마스크 맵 서버 (Map Server)
        Node(
            package='nav2_map_server',
            executable='map_server',
            name='filter_mask_server',
            output='screen',
            parameters=[
                {'yaml_filename': mask_yaml_file},
                {'topic_name': 'filter_mask'},
                {'frame_id': 'map'}
            ]
        ),

        # 2. 코스트맵 필터 정보 서버 (Costmap Filter Info Server)
        Node(
            package='nav2_map_server',
            executable='costmap_filter_info_server',
            name='costmap_filter_info_server',
            output='screen',
            parameters=[
                {'type': 0}, # 0: Keepout (진입 금지 구역)
                {'filter_info_topic': 'costmap_filter_info'},
                {'mask_topic': 'filter_mask'}
            ]
        ),

        # 3. 라이프사이클 매니저 (위 두 노드를 자동으로 켜주는 마법사 역할)
        Node(
            package='nav2_lifecycle_manager',
            executable='lifecycle_manager',
            name='lifecycle_manager_filter',
            output='screen',
            parameters=[
                {'use_sim_time': False},
                {'autostart': True},
                {'node_names': ['filter_mask_server', 'costmap_filter_info_server']}
            ]
        )
    ])