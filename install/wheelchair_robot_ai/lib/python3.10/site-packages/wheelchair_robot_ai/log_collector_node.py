#!/usr/bin/env python3
# log_collector_node.py
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json
import os
from datetime import datetime

class LogCollectorNode(Node):
    def __init__(self):
        super().__init__('log_collector_node')
        self.log_file = os.path.expanduser('~/driving_log.json')
        
        self.create_subscription(String, '/sos_trigger', self.sos_callback, 10)
        self.create_subscription(String, '/safety_action', self.action_callback, 10)
                
        # 1. logs 폴더 지정 및 생성
        log_dir = os.path.expanduser('~/wheelchair_ws/driving_data')
        os.makedirs(log_dir, exist_ok=True)

        # 2. 현재 시간을 년월일_시분초 포맷으로 만들기 (예: 20260505_221430)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # 3. 새로운 파일명으로 저장 경로 설정
        self.log_path = os.path.join(log_dir, f'driving_log_{timestamp}.json')
        self.get_logger().info(f'로그 수집 시작... 저장 경로: {self.log_path}')

    def save_log(self, topic, data):
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "topic": topic,
            "data": data
        }
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

    def sos_callback(self, msg: String):
        self.save_log('/sos_trigger', msg.data)

    def action_callback(self, msg: String):
        try:
            parsed_data = json.loads(msg.data)
            self.save_log('/safety_action', parsed_data)
        except json.JSONDecodeError:
            self.save_log('/safety_action', msg.data)

def main(args=None):
    rclpy.init(args=args)
    node = LogCollectorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()