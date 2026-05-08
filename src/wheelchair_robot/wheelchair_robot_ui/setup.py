from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'wheelchair_robot_ui'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        # ament 인덱스
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        # package.xml
        ('share/' + package_name, ['package.xml']),
        # launch 파일들
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        # 웹 UI 정적 파일들 — colcon build 후
        # install/wheelchair_robot_ui/share/wheelchair_robot_ui/web/ 에 복사됨
        (os.path.join('share', package_name, 'web'), glob('web/*.html')),
        (os.path.join('share', package_name, 'web', 'js'),
            glob('web/js/*.js') + glob('web/js/*.jsx')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='kim',
    maintainer_email='ksjun100848@naver.com',
    description='Wheelchair Robot Web UI — React 기반 운영 화면',
    license='Apache 2.0',
    extras_require={
        'test': ['pytest'],
    },
    entry_points={
        # 별도 Python 노드 없음 — launch에서 정적 서버를 ExecuteProcess로 실행
        'console_scripts': [],
    },
)