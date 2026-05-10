import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import ExecuteProcess, DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch.conditions import IfCondition
from launch_ros.actions import Node

def generate_launch_description():
    pkg_share = get_package_share_directory('wheelchair_robot_ui')
    web_dir = os.path.join(pkg_share, 'web')

    use_rosbridge = LaunchConfiguration('use_rosbridge')
    port = LaunchConfiguration('port')

    return LaunchDescription([
        DeclareLaunchArgument(
            'use_rosbridge', default_value='true',
            description='이미 rosbridge가 실행 중이면 false로 설정',
        ),
        DeclareLaunchArgument(
            'port', default_value='8000',
            description='웹 UI 정적 서버 포트',
        ),

        # rosbridge_websocket: UI(브라우저)와 ROS2 사이의 WebSocket 브리지
        Node(
            package='rosbridge_server',
            executable='rosbridge_websocket',
            name='rosbridge_websocket',
            output='screen',
            condition=IfCondition(use_rosbridge),
        ),

        # 정적 웹서버: UI HTML/JS 파일 서빙
        ExecuteProcess(
            cmd=['python3', '-m', 'http.server', port, '-d', web_dir, '-b', '0.0.0.0'],
            output='screen',
            name='wheelchair_ui_server',
        ),

        # 관리자 대시보드 백엔드 데이터 서버 (server.py)
        ExecuteProcess(
            cmd=['bash', '-c', 'cd ~/wheelchair_ws/src/wheelchair_robot/wheelchair_admin_dashboard && python3 server.py'],
            output='screen',
            name='admin_backend_server',
        ),
        Node(
            package='wheelchair_robot_ai',
            executable='log_collector_node',   # setup.py에 정의된 실행 파일 이름
            name='log_collector_node',
            output='screen'
        ),
    ])