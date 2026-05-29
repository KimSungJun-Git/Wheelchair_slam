import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource

def generate_launch_description():
    fake_pkg = get_package_share_directory('wheelchair_robot_fake')
    nav2_pkg = get_package_share_directory('wheelchair_robot_navigation2')

    # 1. 위치 추정 및 가짜 센서 실행 (기존 fake_localization)
    fake_localization_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(fake_pkg, 'launch', 'fake_localization.launch.py')
        ),
        launch_arguments={'use_rviz': 'false'}.items()
    )

    # 2. 경로 계획 및 코스트맵 실행 (보라색 벽 표시 및 주행 제어)
    navigation2_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(nav2_pkg, 'launch', 'navigation2.launch.py')
        ),
        launch_arguments={'use_sim_time': 'false', 'use_rviz': 'true'}.items()
    )

    return LaunchDescription([
        fake_localization_launch,
        navigation2_launch
    ])