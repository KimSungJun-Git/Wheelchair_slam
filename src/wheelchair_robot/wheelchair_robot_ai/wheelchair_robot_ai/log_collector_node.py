import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json
import os
from datetime import datetime
from geometry_msgs.msg import Twist, PoseWithCovarianceStamped
import math

import time
from geometry_msgs.msg import Twist
from collections import deque, Counter

class LogCollectorNode(Node):
    def __init__(self):
        super().__init__('log_collector_node')
        self.log_buffer = deque(maxlen=1000) 
        self.save_dir = os.path.expanduser('~/wheelchair_ws/driving_data')
        os.makedirs(self.save_dir, exist_ok=True)
        
        self.latest_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}
        self.latest_velocity = {"linear": 0.0, "angular": 0.0}
        self.latest_zone = None

        self.create_subscription(Twist, '/cmd_vel', self.cmd_callback, 10)
        self.create_subscription(String, '/current_zone', self.zone_callback, 10)
        self.create_subscription(PoseWithCovarianceStamped, '/amcl_pose', self.amcl_callback, 10)
        self.create_subscription(String, '/safety_action', self.log_callback, 10)
        self.create_subscription(String, '/sos_trigger', self.sos_callback, 10) 
        
        self.create_subscription(String, '/request_log_rotation', self.rotation_callback, 10)

        self.last_snapshot_time = {}      
        self.snapshot_cooldown_sec = 30.0 
        
        # 초기 세션 생성
        self.create_new_session()
        self.get_logger().info(f"🟢 [스마트 블랙박스] 링 버퍼 활성화 대기 중...")
        
        self.get_logger().info(f"🟢 [스마트 블랙박스] 링 버퍼 활성화 대기 중...")
        
        self.last_snapshot_time = {}      
        self.snapshot_cooldown_sec = 30.0
    def create_new_session(self):
        session_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        self.session_filename = f"[주행로그]_{session_time}.json"
        self.session_filepath = os.path.join(self.save_dir, self.session_filename)
        self.session_event_counter = Counter()

        # 세션 시작 마커를 즉시 디스크에 기록 → 파일이 항상 존재 보장
        with open(self.session_filepath, 'w', encoding='utf-8') as f:
            marker = {
                "_session_marker": True,
                "event_type": "session_start",
                "timestamp": time.time(),
                "session_name": self.session_filename,
            }
            f.write(json.dumps(marker, ensure_ascii=False) + '\n')

        self.get_logger().info(f"🟢 새 세션 시작 → {self.session_filename}")
        
    def rotation_callback(self, msg):
        self.get_logger().info("🔄 UI 요약 요청 수신")
        # event_name을 매번 unique하게 → 쿨다운 우회
        self.save_snapshot(seconds=30, event_name=f"summary_{int(time.time())}")
        self.create_new_session()
        
    def amcl_callback(self, msg):
        """맵 기준 절대 위치 (SLAM 사용 중)"""
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        yaw = math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                         1.0 - 2.0 * (q.y * q.y + q.z * q.z))
        self.latest_pose = {
            "x": round(p.x, 3),
            "y": round(p.y, 3),
            "yaw": round(yaw, 3),
        }
                
    def cmd_callback(self, msg):
        """현재 명령 속도 = 로봇이 실제로 움직이려는 속도"""
        self.latest_velocity = {
            "linear": round(msg.linear.x, 3),
            "angular": round(msg.angular.z, 3),
        }
    
    
    def zone_callback(self, msg):
        """현재 안전 구역 갱신"""
        self.latest_zone = msg.data        
        
    def sos_callback(self, msg):
        """SOS는 단순 문자열로 옴 (위치 분실 등)"""
        data = {
            "source": "sos_trigger",
            "action": "sos",
            "reason": msg.data,
            "timestamp": time.time(),
        }
        self.log_buffer.append(data)
        self.get_logger().error(f"🆘 SOS 감지({msg.data})! 전후 30초 데이터 캡처 중...")
        self.save_snapshot(seconds=30, event_name="sos")
        
    def log_callback(self, msg):
        try:
            data = json.loads(msg.data)
            current_time = time.time()
            data['timestamp'] = current_time
            data['pose'] = self.latest_pose.copy()
            data['velocity'] = self.latest_velocity.copy()
            data['zone'] = self.latest_zone
            
            self.log_buffer.append(data)
            
            action = data.get("action", "unknown")
            
            if action == "modified":
                self.get_logger().warn("⚠️ 명령 수정 감지! 전후 30초 데이터 캡처 중...")
                self.save_snapshot(seconds=30, event_name="modified")
            elif action == "blocked":
                self.get_logger().error("🚨 비상정지 감지! 전후 30초 데이터 캡처 중...")
                self.save_snapshot(seconds=30, event_name="blocked")
                
        except json.JSONDecodeError:
            pass

    def save_snapshot(self, seconds, event_name):
        now = time.time()
        
        last_time = self.last_snapshot_time.get(event_name, 0)
        if now - last_time < self.snapshot_cooldown_sec:
            return
        self.last_snapshot_time[event_name] = now
        
        cutoff_time = now - seconds
        snapshot = [log for log in self.log_buffer if log['timestamp'] >= cutoff_time]
        
        label_map = {"blocked": "비상정지", "modified": "명령수정", "sos": "SOS"}
        label = label_map.get(event_name, event_name)
        
        with open(self.session_filepath, 'a', encoding='utf-8') as f:
            header = {
                "_event_marker": True,
                "event_type": event_name,
                "event_label": label,
                "timestamp": now,
                "snapshot_size": len(snapshot),
            }
            f.write(json.dumps(header, ensure_ascii=False) + '\n')
            for log in snapshot:
                f.write(json.dumps(log, ensure_ascii=False) + '\n')
        
        self.session_event_counter[event_name] += 1
        self.get_logger().info(
            f"💾 [{label}] 캡처 → {self.session_filename} "
            f"(누적: {dict(self.session_event_counter)})"
        )
def main(args=None):
    rclpy.init(args=args)
    node = LogCollectorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("수집 종료.")
    finally:
        node.destroy_node()
        if rclpy.ok():                 
            rclpy.shutdown()