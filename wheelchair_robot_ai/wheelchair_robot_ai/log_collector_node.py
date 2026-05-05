import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json
import os
from datetime import datetime
from collections import deque
import time

class LogCollectorNode(Node):
    def __init__(self):
        super().__init__('log_collector_node')
        
        # ⭐️ 링 버퍼 설정 (최대 1000개의 로그를 메모리에 유지, 오래된 것은 자동 삭제됨)
        self.log_buffer = deque(maxlen=1000) 
        
        # 데이터 저장 폴더
        self.save_dir = os.path.expanduser('~/wheelchair_ws/driving_data')
        os.makedirs(self.save_dir, exist_ok=True)
        
        # 토픽 구독
        self.create_subscription(String, '/safety_action', self.log_callback, 10)
        self.create_subscription(String, '/sos_trigger', self.log_callback, 10)
        
        self.get_logger().info(f"🟢 [스마트 블랙박스] 링 버퍼 활성화 대기 중...")

    def log_callback(self, msg):
        try:
            data = json.loads(msg.data)
            current_time = time.time()
            data['timestamp'] = current_time
            
            # 1. 일단 모든 로그는 메모리(링 버퍼)에 담음
            self.log_buffer.append(data)
            
            # 2. 에러 중요도 판별 (action 값 기준)
            action = data.get("action", "unknown")
            
            if action == "warning":
                self.get_logger().warn("⚠️ 단순 경고 감지! 과거 5초 데이터 캡처 중...")
                self.save_snapshot(seconds=5, event_name="warning")
                
            elif action == "emergency_stop" or action == "fatal":
                self.get_logger().error("🚨 긴급 정지 감지! 과거 30초 데이터 캡처 중...")
                self.save_snapshot(seconds=30, event_name="fatal")
                
        except json.JSONDecodeError:
            pass

    def save_snapshot(self, seconds, event_name):
        # 현재 시간 기준으로 지정된 초(seconds) 이내의 데이터만 필터링
        cutoff_time = time.time() - seconds
        snapshot = [log for log in self.log_buffer if log['timestamp'] >= cutoff_time]
        
        # 파일로 저장
        filename = f"snapshot_{event_name}_{datetime.now().strftime('%Y%md_%H%M%S')}.json"
        filepath = os.path.join(self.save_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            for log in snapshot:
                f.write(json.dumps(log, ensure_ascii=False) + '\n')
                
        self.get_logger().info(f"💾 {event_name.upper()} 스냅샷 저장 완료: {len(snapshot)}개 로그 기록됨")

def main(args=None):
    rclpy.init(args=args)
    node = LogCollectorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("수집 종료.")
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()