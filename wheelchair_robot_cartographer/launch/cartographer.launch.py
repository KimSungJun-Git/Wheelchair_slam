import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch_ros.actions import Node
from launch.substitutions import LaunchConfiguration, ThisLaunchFileDir
from launch.launch_description_sources import PythonLaunchDescriptionSource

def generate_launch_description():

    pkg_dir = get_package_share_directory('wheelchair_robot_cartographer')
    rviz_config = os.path.join(pkg_dir, 'rviz', 'wheelchair_robot_cartographer.rviz')

    use_sim_time = LaunchConfiguration('use_sim_time', default='false')
    config_dir = LaunchConfiguration('cartographer_config_dir', 
                                     default=os.path.join(pkg_dir, 'config'))
    config_basename = LaunchConfiguration('configuration_basename', 
                                          default='wheelchair_robot.lua')
    resolution = LaunchConfiguration('resolution', default='0.05')
    publish_period = LaunchConfiguration('publish_period_sec', default='1.0')

    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument('cartographer_config_dir', default_value=config_dir),
        DeclareLaunchArgument('configuration_basename', default_value=config_basename),
        DeclareLaunchArgument('resolution', default_value=resolution),
        DeclareLaunchArgument('publish_period_sec', default_value=publish_period),

        Node(
            package='cartographer_ros',
            executable='cartographer_node',
            name='cartographer_node',
            output='screen',
            parameters=[{'use_sim_time': use_sim_time}],
            arguments=['-configuration_directory', config_dir,
                       '-configuration_basename', config_basename]),

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([ThisLaunchFileDir(), '/occupancy_grid.launch.py']),
            launch_arguments={
                'use_sim_time': use_sim_time, 
                'resolution': resolution,
                'publish_period_sec': publish_period
            }.items()),

        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            arguments=['-d', rviz_config],
            parameters=[{'use_sim_time': use_sim_time}],
            output='screen'),
    ])