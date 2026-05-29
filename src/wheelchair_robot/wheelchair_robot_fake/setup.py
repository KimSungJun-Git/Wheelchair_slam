from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'wheelchair_robot_fake'

setup(
    name=package_name,
    version='0.0.1',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='kim',
    maintainer_email='ksjun100848@naver.com',
    description='하드웨어 없이 RViz에서 SLAM/위치추정을 돌리기 위한 가짜 센서 노드들',
    license='Apache 2.0',
    extras_require={'test': ['pytest']},
    entry_points={
        'console_scripts': [
            'fake_encoder_node = wheelchair_robot_fake.fake_encoder_node:main',
            'fake_imu_node     = wheelchair_robot_fake.fake_imu_node:main',
            'fake_lidar_node   = wheelchair_robot_fake.fake_lidar_node:main',
        ],
    },
)
