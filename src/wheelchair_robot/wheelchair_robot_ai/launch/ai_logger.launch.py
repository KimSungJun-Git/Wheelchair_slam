# launch/ai_logger.launch.py
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='wheelchair_robot_ai',
            executable='log_collector_node',
            name='log_collector_node',
            output='screen'
        )
    ])