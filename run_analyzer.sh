#!/bin/bash
source /opt/ros/humble/setup.bash 2>/dev/null || source /opt/ros/noetic/setup.bash 2>/dev/null
source ~/wheelchair_ws/install/setup.bash

echo "====================================="
echo "🤖 AI 주행 데이터 분석을 시작합니다..."
echo "Qwen 모델이 켜져 있는지 확인해주세요 (ollama run qwen2.5:7b)"
echo "====================================="

ros2 run wheelchair_robot_ai agent_analyzer
