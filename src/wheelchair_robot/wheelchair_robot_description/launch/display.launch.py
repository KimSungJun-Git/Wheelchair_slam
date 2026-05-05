import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    # 패키지 이름 설정
    package_name = 'wheelchair_robot_description'

    # 파일 경로 설정
    urdf_file = os.path.join(
        get_package_share_directory(package_name),
        'urdf',
        'wheelchair_robot.urdf'
    )
    rviz_config_file = os.path.join(
        get_package_share_directory(package_name),
        'rviz',
        'wheelchair_robot_model.rviz'
    )

    # URDF 파일 읽기
    with open(urdf_file, 'r') as infp:
        robot_desc = infp.read()

    return LaunchDescription([
        # 1. 로봇 상태 퍼블리셔 (URDF를 기반으로 TF 생성)
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='screen',
            parameters=[{'robot_description': robot_desc}]
        ),
        # 2. 조인트 상태 퍼블리셔 GUI (가상 관절 조작용)
        Node(
            package='joint_state_publisher_gui',
            executable='joint_state_publisher_gui',
            name='joint_state_publisher_gui',
            output='screen'
        ),
        # 3. RViz2 실행
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            output='screen',
            arguments=['-d', rviz_config_file]
        )
    ])
