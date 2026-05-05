from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    teleop_node = Node(
        package='wheelchair_core',      # 우리가 만든 패키지 이름
        executable='teleop_keyboard',   # setup.py에 등록한 실행명
        name='teleop_keyboard',
        output='screen',
        emulate_tty=True,               # 키보드 입력을 터미널에서 제대로 받기 위한 설정

        # ⭐️ 핵심: 출력 토픽을 mux 입력 토픽 이름으로 변경
        remappings=[
            ('cmd_vel', '/cmd_vel_teleop') 
        ]
    )

    return LaunchDescription([
        teleop_node
    ])