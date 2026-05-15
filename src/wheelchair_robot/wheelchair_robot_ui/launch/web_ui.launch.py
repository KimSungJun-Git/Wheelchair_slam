import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    ExecuteProcess, DeclareLaunchArgument,
    RegisterEventHandler, LogInfo, OpaqueFunction,
)
from launch.event_handlers import OnShutdown
from launch.substitutions import LaunchConfiguration
from launch.conditions import IfCondition
from launch_ros.actions import Node


def cleanup_empty_sessions(context, *args, **kwargs):
    """launch 종료(Ctrl+C 포함) 시 빈 세션 파일 정리."""
    import glob
    from pathlib import Path

    data_dir = Path(os.path.expanduser("~/wheelchair_ws/driving_data"))
    if not data_dir.exists():
        return []

    deleted = 0
    for json_path in data_dir.glob("*.json"):
        try:
            if json_path.stat().st_size < 200:        # 빈 세션 기준 (~149 bytes)
                base = json_path.with_suffix("")       # _report.md / _r1_diagnosis.md 동반 정리
                for companion in [
                    json_path,
                    base.with_name(base.name + "_report.md"),
                    base.with_name(base.name + "_r1_diagnosis.md"),
                ]:
                    if companion.exists():
                        companion.unlink()
                deleted += 1
        except OSError:
            pass
    print(f"🧹 빈 세션 {deleted}개 정리 완료 ({data_dir})")
    return []


def generate_launch_description():
    pkg_share = get_package_share_directory('wheelchair_robot_ui')
    web_dir = os.path.join(pkg_share, 'web')

    use_rosbridge = LaunchConfiguration('use_rosbridge')
    port = LaunchConfiguration('port')

    return LaunchDescription([
        DeclareLaunchArgument('use_rosbridge', default_value='true'),
        DeclareLaunchArgument('port', default_value='8000'),

        Node(
            package='rosbridge_server',
            executable='rosbridge_websocket',
            name='rosbridge_websocket',
            output='screen',
            condition=IfCondition(use_rosbridge),
        ),
        ExecuteProcess(
            cmd=['python3', '-m', 'http.server', port, '-d', web_dir, '-b', '0.0.0.0'],
            output='screen',
            name='wheelchair_ui_server',
        ),
        Node(
            package='wheelchair_admin_dashboard',
            executable='server',
            name='admin_backend_server',
            output='screen',
        ),
        Node(
            package='wheelchair_robot_ai',
            executable='log_collector_node',
            name='log_collector_node',
            output='screen',
        ),

        # ⬇ 여기가 추가된 핵심 부분
        RegisterEventHandler(
            OnShutdown(on_shutdown=[
                LogInfo(msg="🛑 launch 종료 감지 — 빈 세션 정리 시작"),
                OpaqueFunction(function=cleanup_empty_sessions),
            ])
        ),
    ])