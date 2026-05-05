import os
from glob import glob
from setuptools import find_packages, setup

package_name = 'wheelchair_core'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob(os.path.join('launch', '*launch.[pxy][yma]*'))),
        (os.path.join('share', package_name, 'worlds'), glob(os.path.join('worlds', '*.world'))),
        (os.path.join('share', package_name, 'config'), glob(os.path.join('config', '*.*'))),
        (os.path.join('share', package_name, 'maps'), glob(os.path.join('maps', '*.*'))),
        (os.path.join('share', package_name, 'rviz'), glob(os.path.join('rviz', '*.*'))),
        (os.path.join('share', package_name, 'urdf'), glob(os.path.join('urdf', '*.*'))),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'worlds'), glob('worlds/*.world')),
        (os.path.join('share', package_name, 'params'), glob('params/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='kim',
    maintainer_email='ksjun100848@naver.com',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'scenario_manager = wheelchair_core.scenario_manager_node:main',
            'safety_bumper = wheelchair_core.safety_bumper_node:main',
            'precision_docking = wheelchair_core.precision_docking_node:main',
            'Nav_go_to_pose = wheelchair_core.Nav_go_to_pose:main',
            'telegram_robot = wheelchair_core.telegram_robot:main',
            'safety_stop_node = wheelchair_core.safety_stop_node:main',
            'mode_switch_node = wheelchair_core.mode_switch_node:main',
            'teleop_keyboard = wheelchair_core.teleop_keyboard:main',
            'mode_manager = wheelchair_core.wheelchair_mode_manager:main',
        ],
    },
)
