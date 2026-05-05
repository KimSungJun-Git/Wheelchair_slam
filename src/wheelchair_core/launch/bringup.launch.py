import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    # 1. EKF 설정 파일 경로 (wheelchair_robot_control 패키지)
    control_pkg = get_package_share_directory('wheelchair_robot_control')
    ekf_config = os.path.join(control_pkg, 'config', 'ekf.yaml')
    
    # 2. twist_mux 설정 파일 경로 (wheelchair_core 패키지)
    core_pkg = get_package_share_directory('wheelchair_core')
    twist_mux_params = os.path.join(core_pkg, 'config', 'twist_mux.yaml')

    # 3. 키보드 텔레옵 노드 (새 터미널 창을 띄워 키보드 입력을 받음)
    teleop_node = Node(
        package='wheelchair_core',
        executable='teleop_keyboard',
        name='teleop_keyboard',
        output='screen',
        emulate_tty=True,
        prefix='gnome-terminal -- ', # launch 환경에서의 TTY 에러 방지를 위해 필수
        remappings=[
            ('cmd_vel', '/cmd_vel_teleop') # mux의 조이스틱 입력 토픽과 이름 매칭
        ]
    )

    return LaunchDescription([
        # ⭐️ 터틀봇 가제보 실행 시 robot_state_publisher가 자동 실행되므로 여기서는 제거함.
        
        # 1. EKF 노드 (/odom과 /imu를 융합하여 /odometry/filtered 발행)
        Node(
            package='robot_localization',
            executable='ekf_node',
            name='ekf_filter_node',
            output='screen',
            parameters=[ekf_config, {'use_sim_time': True}] # 시뮬레이터 사용이므로 True 권장
        ),
        
        # 2. Twist Mux 노드 (속도 명령 제어 및 우선순위 분배)
        Node(
            package='twist_mux',
            executable='twist_mux',
            name='twist_mux',
            parameters=[
                twist_mux_params,
                {'use_sim_time': True}
            ],
            remappings=[
                ('/cmd_vel_out', '/cmd_vel') # 최종 출력을 로봇 바퀴로 연결
            ],
            output='screen'
        ),

        # 3. 키보드 조작 노드 추가
        teleop_node
    ])