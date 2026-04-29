from setuptools import find_packages, setup
import os # 1. os 임포트 추가
from glob import glob # 2. glob 임포트 추가

package_name = 'wheelchair_robot_control'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='kim',
    maintainer_email='ksjun100848@naver.com',
    description='Wheelchair Robot Control Package with EKF',
    license='Apache 2.0',
    extras_require={
        'test': ['pytest'],
    },
    entry_points={
        'console_scripts': [
            'main_controller = wheelchair_robot_control.main_controller:main',
            'safety_stop_node = wheelchair_robot_control.safety_stop_node:main',
            'mode_switch_node = wheelchair_robot_control.mode_switch_node:main',
        ],
    },
)