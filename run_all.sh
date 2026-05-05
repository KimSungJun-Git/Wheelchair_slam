#!/bin/bash

# ⭐️ 추가된 핵심 코드: 워크스페이스 환경 변수 불러오기
source /opt/ros/humble/setup.bash
source ~/wheelchair_ws/install/setup.bash

echo "========================================="
echo "🟢 [1단계] 주행 로그 수집을 시작합니다..."
echo "종료하려면 언제든 Ctrl + C 를 누르세요."
echo "========================================="
ros2 launch wheelchair_robot_ai ai_logger.launch.py

echo ""
echo "========================================="
echo "🤖 [2단계] 주행이 종료되었습니다. AI 분석을 시작합니다..."
echo "========================================="
./run_analyzer.sh
