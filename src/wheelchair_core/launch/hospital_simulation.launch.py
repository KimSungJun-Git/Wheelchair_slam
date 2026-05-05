import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, AppendEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
import xacro

def generate_launch_description():
    pkg_gazebo_ros = get_package_share_directory('gazebo_ros')
    pkg_wheelchair_core = get_package_share_directory('wheelchair_core')
    
    # 터틀봇3 모델 경로 및 파일 설정
    turtlebot_model = os.environ.get('TURTLEBOT3_MODEL', 'waffle_pi')
    
    # 모델 폴더 경로를 GAZEBO_MODEL_PATH에 추가 (메쉬 파일을 찾기 위해 필수)
    tb3_model_path = os.path.join(get_package_share_directory('turtlebot3_gazebo'), 'models')
    
    urdf_file = os.path.join(
        get_package_share_directory('turtlebot3_description'),
        'urdf',
        f'turtlebot3_{turtlebot_model}.urdf'
    )
    
    # URDF 파일 읽기
    with open(urdf_file, 'r') as infp:
        robot_desc = infp.read()

    world_file = os.path.join(pkg_wheelchair_core, 'worlds', 'hospital_env.world')

    # 가제보 서버 실행
    gzserver_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_gazebo_ros, 'launch', 'gzserver.launch.py')
        ),
        launch_arguments={'world': world_file}.items()
    )

    # 가제보 클라이언트 실행
    gzclient_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_gazebo_ros, 'launch', 'gzclient.launch.py')
        )
    )

    # Robot State Publisher 실행 (TF 퍼블리시 필수)
    robot_state_publisher_cmd = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[{'robot_description': robot_desc}]
    )

    # 로봇 스폰 (Robot State Publisher가 쏘는 토픽에서 URDF를 받아 스폰)
    spawn_turtlebot_cmd = Node(
        package='gazebo_ros',
        executable='spawn_entity.py',
        arguments=[
            '-entity', 'turtlebot3',
            '-topic', 'robot_description',
            '-x', '-1.0',
            '-y', '1.0',
            '-z', '0.01'
        ],
        output='screen'
    )

    ld = LaunchDescription()
    
    # 환경변수 추가 (터틀봇 모델 렌더링을 위함)
    ld.add_action(AppendEnvironmentVariable(
        name='GAZEBO_MODEL_PATH',
        value=tb3_model_path
    ))
    
    ld.add_action(gzserver_cmd)
    ld.add_action(gzclient_cmd)
    ld.add_action(robot_state_publisher_cmd)
    ld.add_action(spawn_turtlebot_cmd)

    return ld
