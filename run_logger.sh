#!/bin/bash
source /opt/ros/humble/setup.bash 2>/dev/null || source /opt/ros/noetic/setup.bash 2>/dev/null
source ~/wheelchair_ws/install/setup.bash

echo "====================================="
echo "🗂️ 휠체어 로봇 자율주행 로그 수집을 시작합니다..."
echo "저장 경로: ~/driving_log.json"
echo "====================================="

ros2 run wheelchair_robot_ai log_collector_node
