# wheelchair_robot_ai/setup.py
from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'wheelchair_robot_ai'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ntrex',
    maintainer_email='lab@ntrex.co.kr',
    description='AI Analytics and Logging for Wheelchair Robot',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'log_collector_node = wheelchair_robot_ai.log_collector_node:main',
            'agent_analyzer = wheelchair_robot_ai.agent_analyzer:main',
        ],
    },
)