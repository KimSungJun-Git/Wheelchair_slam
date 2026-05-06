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
        
        # ⭐️ 링 버퍼 설정 (최대 1000개의 로그를 메모리에 유지, 오래된 것은 자동 삭제됨)
        self.log_buffer = deque(maxlen=1000) 
        
        # 데이터 저장 폴더
        self.save_dir = os.path.expanduser('~/wheelchair_ws/driving_data')
        os.makedirs(self.save_dir, exist_ok=True)
        # ⭐️ 위치 정보를 저장할 변수 추가
        self.current_x = 0.0
        self.current_y = 0.0
        # ⭐️ 추가: 최신 상태값 저장 (이벤트 발생 시 같이 기록)
        self.latest_pose = {"x": None, "y": None, "yaw": None}
        self.latest_velocity = {"linear": None, "angular": None}
        self.latest_zone = None  # safety_stop의 현재 구역 정보
        # ⭐️ 추가 구독 (상태 추적용 — 버퍼에 안 쌓고 최신값만 갱신)
        self.create_subscription(Twist, '/cmd_vel', self.cmd_callback, 10)
        self.create_subscription(String, '/current_zone', self.zone_callback, 10)
        self.create_subscription(
            PoseWithCovarianceStamped, '/amcl_pose', self.amcl_callback, 10)
        self.create_subscription(Twist, '/cmd_vel', self.cmd_callback, 10)
        self.create_subscription(String, '/current_zone', self.zone_callback, 10)
        self.latest_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}
        self.latest_velocity = {"linear": 0.0, "angular": 0.0}
        self.latest_zone = None
        # ⭐️ 로봇의 오도메트리(위치) 토픽 구독
        # 토픽 구독
        self.create_subscription(String, '/safety_action', self.log_callback, 10)
        self.create_subscription(String, '/sos_trigger', self.log_callback, 10)
        self.create_subscription(String, '/safety_action', self.log_callback, 10)
        self.create_subscription(String, '/sos_trigger', self.sos_callback, 10) 
        
        # ⭐ 이번 실행 전용 단일 파일명 (한 실행 = 한 파일)
        session_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        self.session_filename = f"[주행로그]_{session_time}.json"
        self.session_filepath = os.path.join(self.save_dir, self.session_filename)
        self.session_event_counter = Counter()

        self.get_logger().info(f"🟢 세션 시작 → {self.session_filename}")
        
        self.get_logger().info(f"🟢 [스마트 블랙박스] 링 버퍼 활성화 대기 중...")
        
        self.last_snapshot_time = {}      # 이벤트별 마지막 저장 시간
        self.snapshot_cooldown_sec = 30.0 # 같은 이벤트는 30초 내 1회만 저장
        
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
            # data['location'] = {...}   ← 이 줄 삭제 (pose와 중복)
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
        
        # 디바운싱 (콘솔 출력 스팸만 막음)
        last_time = self.last_snapshot_time.get(event_name, 0)
        if now - last_time < self.snapshot_cooldown_sec:
            return
        self.last_snapshot_time[event_name] = now
        
        cutoff_time = now - seconds
        snapshot = [log for log in self.log_buffer if log['timestamp'] >= cutoff_time]
        
        label_map = {"blocked": "비상정지", "modified": "명령수정", "sos": "SOS"}
        label = label_map.get(event_name, event_name)
        
        # ⭐ 세션 파일에 append (구분 헤더 포함)
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
        if rclpy.ok():                 # ← 핵심: 이미 닫혔는지 체크
            rclpy.shutdown()