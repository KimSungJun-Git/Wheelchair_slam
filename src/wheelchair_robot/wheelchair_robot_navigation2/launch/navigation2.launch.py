#navigation2.launch.py
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.substitutions import LaunchConfiguration
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, GroupAction
from launch_ros.actions import Node, SetRemap  
def generate_launch_description():
    # ===== 경로 설정 =====
    pkg_dir = get_package_share_directory('wheelchair_robot_navigation2')
    nav2_launch_dir = os.path.join(
        get_package_share_directory('nav2_bringup'), 'launch')

    rviz_config = os.path.join(pkg_dir, 'rviz', 'wheelchair_robot_navigation2.rviz')
    default_map = os.path.join(pkg_dir, 'map', 'wheelchair_robot_world.yaml')
    default_param = os.path.join(pkg_dir, 'param', 'wheelchair_robot.yaml')
    keepout_mask_yaml = os.path.join(pkg_dir, 'map', 'keepout_mask.yaml')
    speed_mask_yaml = os.path.join(pkg_dir, 'map', 'speed_mask.yaml') 
    # ===== 실행 인자 =====
    use_sim_time = LaunchConfiguration('use_sim_time', default='false')
    map_path = LaunchConfiguration('map', default=default_map)
    param_path = LaunchConfiguration('params_file', default=default_param)

    return LaunchDescription([
        # ===== 인자 선언 =====
        DeclareLaunchArgument('map', default_value=default_map),
        DeclareLaunchArgument('params_file', default_value=default_param),
        DeclareLaunchArgument('use_sim_time', default_value='false'),

        # ===== Safety Stop Node =====
        Node(
            package='wheelchair_robot_control',
            executable='safety_stop_node',
            name='safety_stop_node',
            output='screen',
            parameters=[{
                'stop_distance': 0.5,
                'slowdown_distance': 0.8,
                'front_angle_range': 5.0,
            }],
        ),

        # ===== 🚫 1. 접근 금지 구역 (Keepout) 세트 =====
        Node(
            package='nav2_map_server',
            executable='costmap_filter_info_server',
            name='keepout_filter_info_server',
            output='screen',
            parameters=[param_path],
        ),
        Node(
            package='nav2_map_server',
            executable='map_server',
            name='keepout_mask_server',
            output='screen',
            parameters=[{
                'yaml_filename': keepout_mask_yaml,
                'topic_name': 'keepout_filter_mask', 
                'frame_id': 'map',
                'use_sim_time': use_sim_time,
            }],
        ),

        # ===== 🐢 2. 서행 구역 (Speed Limit) 세트 =====
        Node(
            package='nav2_map_server',
            executable='costmap_filter_info_server',
            name='speed_filter_info_server',
            output='screen',
            parameters=[{
                'use_sim_time': use_sim_time,
                'type': 1,                                    # ⭐ 1 = SpeedLimit
                'filter_info_topic': '/speed_filter_info',    # ⭐ 다른 토픽
                'mask_topic': '/speed_filter_mask',
                'base': 0.0,
                'multiplier': 1.0,                            # 마스크 픽셀값 그대로 % 사용
            }],
        ),
        Node(
            package='nav2_map_server',
            executable='map_server',
            name='speed_mask_server',
            output='screen',
            parameters=[{
                'yaml_filename': speed_mask_yaml,
                'topic_name': 'speed_filter_mask', 
                'frame_id': 'map',
                'use_sim_time': use_sim_time,
            }],
        ),

        # ===== 🚦 매니저 노드 (4개 모두 등록) =====
        Node(
            package='nav2_lifecycle_manager',
            executable='lifecycle_manager',
            name='lifecycle_manager_costmap_filters',
            output='screen',
            parameters=[{
                'autostart': True,
                'node_names': [
                    'keepout_filter_info_server',
                    'keepout_mask_server',
                    'speed_filter_info_server',
                    'speed_mask_server',
                ],
            }],
        ),
        # ===== Nav2 Bringup (그룹 리매핑 적용) =====
        GroupAction(
            actions=[
                # 이 그룹 안에 있는 모든 노드의 /cmd_vel 출력을 /cmd_vel_nav로 강제 변경
                SetRemap(src='/cmd_vel', dst='/cmd_vel_nav'),
                SetRemap(src='/cmd_vel_smoothed', dst='/cmd_vel_nav_smoothed'),
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(
                        os.path.join(nav2_launch_dir, 'bringup_launch.py')),
                    launch_arguments={
                        'map': map_path,
                        'use_sim_time': use_sim_time,
                        'params_file': param_path,
                        'use_composition': 'False',
                    }.items(),
                )
            ]
        ),
        
        # ===== RViz2 Node =====
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            arguments=['-d', rviz_config],
            parameters=[{'use_sim_time': use_sim_time}],
            output='screen'
        ),
    ])