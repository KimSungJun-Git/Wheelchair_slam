#!/bin/bash

echo "🚨 관제 시스템 다중 알림 자동 전송 테스트를 시작합니다. (15초 간격)"
echo "종료하려면 Ctrl + C를 누르세요."
echo "------------------------------------------------------"

while true; do
  echo "전송 [1/6]: 🚨 SOS 긴급 호출 (물리 버튼)"
  ros2 topic pub --once /sos_trigger std_msgs/String "{data: '휠체어 탑승자 수동 SOS 버튼 작동'}" > /dev/null 2>&1
  sleep 3

  echo "전송 [2/6]: ⚠️ Nav2 Keepout Filter 접근"
  ros2 topic pub --once /safety_action std_msgs/String "{data: '{\"action\": \"blocked\", \"reason\": \"병원 출입금지 구역(Keepout Zone) 접근 차단\"}'}" > /dev/null 2>&1
  sleep 3

  echo "전송 [3/6]: ⚠️ LiDAR 센서 에러"
  ros2 topic pub --once /safety_action std_msgs/String "{data: '{\"action\": \"blocked\", \"reason\": \"LiDAR 스캔 데이터 수신 불가 및 시야 가림\"}'}" > /dev/null 2>&1
  sleep 3

  echo "전송 [4/6]: 🚨 SOS 긴급 호출 (음성 인식)"
  ros2 topic pub --once /sos_trigger std_msgs/String "{data: '환자 음성 SOS 감지됨 (도와주세요)'}" > /dev/null 2>&1
  sleep 3

  echo "전송 [5/6]: ⚠️ IMU / 엔코더(Encoder) 통신 지연"
  ros2 topic pub --once /safety_action std_msgs/String "{data: '{\"action\": \"blocked\", \"reason\": \"하단 모터 엔코더 및 IMU 데이터 동기화 실패\"}'}" > /dev/null 2>&1
  sleep 3

  echo "전송 [6/6]: ⚠️ 동적 장애물 지속 감지"
  ros2 topic pub --once /safety_action std_msgs/String "{data: '{\"action\": \"blocked\", \"reason\": \"전방 0.5m 복도 보행자 지속 감지로 인한 경로 생성 실패\"}'}" > /dev/null 2>&1
  sleep 3
done

