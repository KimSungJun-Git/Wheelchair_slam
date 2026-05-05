import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    # 제어 패키지 경로에서 EKF 설정 파일 가져오기
    control_pkg = get_package_share_directory('wheelchair_robot_control')
    ekf_config = os.path.join(control_pkg, 'config', 'ekf.yaml')
    
    return LaunchDescription([
        # ⭐️ 터틀봇 가제보 실행 시 robot_state_publisher가 자동 실행되므로 여기서는 제거함.
        
        # 1. EKF 노드 (/odom과 /imu를 융합하여 /odometry/filtered 발행)
        Node(
            package='robot_localization',
            executable='ekf_node',
            name='ekf_filter_node',
            output='screen',
            parameters=[ekf_config, {'use_sim_time': True}] # 시뮬레이터 사용이므로 True 권장
        )
    ])