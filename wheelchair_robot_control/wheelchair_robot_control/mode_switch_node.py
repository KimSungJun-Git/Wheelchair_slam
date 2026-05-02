#!/usr/bin/env python3
#mode_switch_node.py
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.executors import MultiThreadedExecutor
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import Path
from geometry_msgs.msg import Twist, PoseStamped
from std_msgs.msg import String, Empty
from action_msgs.srv import CancelGoal
from typing import Optional
import sys
import termios
import tty
import threading
import time
import math

def quaternion_from_yaw(yaw):
    """yaw(rad) → (x, y, z, w) quaternion"""
    return (0.0, 0.0, math.sin(yaw / 2.0), math.cos(yaw / 2.0))

class ModeSwitchNode(Node):
    def __init__(self):
        super().__init__('mode_switch_node')

        # ===== 모드 상태 =====
        self.mode = 'manual'
        self.last_goal: Optional[PoseStamped] = None
        self._goal_handle = None
        self._goal_locked = False

        # ===== 대기소(홈) 좌표 — SLAM 맵에서 확인 후 수정 =====
        self.destinations = {
            'home':       {'x': 1.815,  'y': 1.179,  'yaw': 0.0},   # 시작지점 (대기소)
            'room_101':   {'x': 2.146,  'y': 0.003,  'yaw': 0.0},   # 101호
            'room_102':   {'x': -0.338, 'y': -0.910, 'yaw': 0.0},   # 102호
            'emergency':  {'x': -0.751, 'y': 0.272,  'yaw': 0.0},   # 응급실
        }
        self.home_pose = self.destinations['home']
        # 목적지 이름으로 이동 명령
        self.dest_sub = self.create_subscription(String, '/destination', self.destination_callback, 10)

        # ===== Nav2 Action Client =====
        self._nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')

        # ===== Nav2 Cancel Service =====
        self._cancel_client = self.create_client(CancelGoal, '/navigate_to_pose/_action/cancel_goal')

        # ===== 토픽 구독 =====
        self.nav_cmd_sub = self.create_subscription(Twist, '/cmd_vel_safe', self.nav_cmd_callback, 10)
        self.teleop_cmd_sub = self.create_subscription(Twist, '/cmd_vel_teleop', self.teleop_cmd_callback, 10)

        goal_qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.goal_sub = self.create_subscription(PoseStamped, '/goal_pose', self.goal_cb, goal_qos)

        self.plan_sub = self.create_subscription(Path, '/plan', self.plan_cb, 10)

        self.mode_cmd_sub = self.create_subscription(String, '/mode_switch', self.mode_cmd_callback, 10)

        # 홈 귀환 명령 (웹 UI → Empty 메시지)
        self.home_sub = self.create_subscription(Empty, '/go_home', self.go_home_callback, 10)

        # 안전 알림 (safety_stop_node → 금지구역 진입 시 goal 취소)
        self.safety_sub = self.create_subscription(String, '/safety_alert', self.safety_alert_callback, 10)

        # ===== 토픽 발행 =====
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.mode_pub = self.create_publisher(String, '/robot_mode', 10)

        # ===== 최신 명령 저장 =====
        self.latest_nav_cmd = Twist()
        self.latest_teleop_cmd = Twist()
        self.last_teleop_time = 0.0

        # ===== 타이머 =====
        self.create_timer(0.1, self.control_loop)
        self.create_timer(1.0, self.publish_mode)

        # ===== 키보드 입력 쓰레드 =====
        self.key_thread = threading.Thread(target=self.key_listener, daemon=True)
        self.key_thread.start()
        
        self._current_destination = None # 현재 이동 중인 목적지 이름 저장용 변수

        self.get_logger().info(
            f'Mode Switch Node 시작 - 현재 모드: {self.mode}\n'
            f'  [m] 모드 전환 (manual <-> auto)\n'
            f'  [h] 홈 귀환\n'
            f'  [q] 종료\n'
            f'  홈 좌표: x={self.home_pose["x"]}, y={self.home_pose["y"]}')

    # ===== 목적지 수신 =====
    def destination_callback(self, msg):
        """웹 UI나 외부에서 목적지 이름 받아서 이동"""
        name = msg.data.strip().lower()

        if name not in self.destinations:
            self.get_logger().warn(
                f'알 수 없는 목적지: "{name}" | 사용 가능: {list(self.destinations.keys())}')
            return

        self.get_logger().info(f'목적지 수신: {name}')
        self._send_destination_goal(name)

    # ===== 통합 목적지 이동 (홈 귀환 포함) =====
    def _send_destination_goal(self, name):
        """지정된 이름의 목적지로 NavigateToPose 전송"""
        if name not in self.destinations:
            self.get_logger().warn(f'알 수 없는 목적지: "{name}"')
            return

        dest = self.destinations[name]

        # 자율주행 모드로 전환
        if self.mode == 'manual':
            self.mode = 'auto'
            self.get_logger().info(f'>>> {name}(으)로 이동을 위해 자율주행 모드로 전환')

        # 기존 goal 취소
        self.cancel_nav()

        if not self._nav_client.wait_for_server(timeout_sec=3.0):
            self.get_logger().error('navigate_to_pose 서버 연결 실패')
            return

        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = 'map'
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        goal.pose.pose.position.x = dest['x']
        goal.pose.pose.position.y = dest['y']

        q = quaternion_from_yaw(dest['yaw'])
        goal.pose.pose.orientation.z = q[2]
        goal.pose.pose.orientation.w = q[3]

        self.get_logger().info(
            f'{name}(으)로 이동: x={dest["x"]:.2f}, y={dest["y"]:.2f}')

        # 현재 진행 중인 목적지 이름 저장 (도착 콜백에서 사용)
        self._current_destination = name

        send_future = self._nav_client.send_goal_async(
            goal, feedback_callback=self._dest_feedback_cb)
        send_future.add_done_callback(self._dest_response_cb)

    # ===== 콜백들 (이름 변경: home → dest) =====
    def _dest_response_cb(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().warn(f'{self._current_destination} Goal 거부됨!')
            return
        self.get_logger().info(f'{self._current_destination} Goal 수락 - 이동 중')
        self._goal_handle = goal_handle

        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self._dest_result_cb)

    def _dest_feedback_cb(self, feedback_msg):
        remaining = feedback_msg.feedback.distance_remaining
        self.get_logger().info(
            f'{self._current_destination}(으)로 이동 중... 남은 거리: {remaining:.2f}m')

    def _dest_result_cb(self, future):
        self._goal_locked = False
        self.get_logger().info(
            f'{self._current_destination} 도착 완료 → 수동 모드로 전환')
        self.mode = 'manual'
        self._goal_handle = None
        self._current_destination = None
        self.cmd_pub.publish(Twist())
    
    # ===== 홈 귀환 =====
    def go_home_callback(self, msg):
        self.get_logger().info('홈 귀환 명령 수신')
        self._send_home_goal()

    def _send_home_goal(self):
        """대기소 좌표로 NavigateToPose 전송"""
        # 자율주행 모드로 전환
        if self.mode == 'manual':
            self.mode = 'auto'
            self.get_logger().info('>>> 홈 귀환을 위해 자율주행 모드로 전환')

        # 기존 goal 취소
        self.cancel_nav()

        if not self._nav_client.wait_for_server(timeout_sec=3.0):
            self.get_logger().error('navigate_to_pose 서버 연결 실패')
            return

        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = 'map'
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        goal.pose.pose.position.x = self.home_pose['x']
        goal.pose.pose.position.y = self.home_pose['y']

        q = quaternion_from_yaw(self.home_pose['yaw'])
        goal.pose.pose.orientation.z = q[2]
        goal.pose.pose.orientation.w = q[3]

        self.get_logger().info(
            f'홈 좌표로 이동: x={self.home_pose["x"]}, y={self.home_pose["y"]}')

        send_future = self._nav_client.send_goal_async(
            goal, feedback_callback=self._home_feedback_cb)
        send_future.add_done_callback(self._home_response_cb)
    
    def _home_response_cb(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().warn('홈 귀환 Goal 거부됨!')
            return
        self.get_logger().info('홈 귀환 Goal 수락 - 이동 중')
        self._goal_handle = goal_handle

        # 도착 완료 콜백
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self._home_result_cb)

    def _home_feedback_cb(self, feedback_msg):
        remaining = feedback_msg.feedback.distance_remaining
        self.get_logger().info(f'귀환 중... 남은 거리: {remaining:.2f}m')

    def _home_result_cb(self, future):
        self._goal_locked = False
        self.get_logger().info('홈 도착 완료 → 수동 모드로 전환')
        self.mode = 'manual'
        self._goal_handle = None
        self.cmd_pub.publish(Twist())

    # ===== 안전 알림 처리 =====
    def safety_alert_callback(self, msg):
        if msg.data == 'keepout_violation':
            self.get_logger().error('🚫 금지구역 진입 → Nav2 goal 취소 + 수동 전환')
            self.cancel_nav()
            self.mode = 'manual'
            self.cmd_pub.publish(Twist())
    
        elif msg.data == 'obstacle_too_close':
            # 자율 모드 중일 때만 처리 (수동 모드면 이미 사용자가 조작 중)
            if self.mode == 'auto':
                self.get_logger().error(
                    '⚠️ 전방 장애물 감지 → Nav2 goal 취소 + 수동 모드 전환\n'
                    '    탑승자: 직접 회피 후 [m] 키로 자율 모드 재시작 가능')
                self.cancel_nav()
                self.mode = 'manual'
                self.cmd_pub.publish(Twist())
            else:
                self.get_logger().warn(
                    '⚠️ 전방 장애물 (수동 모드 중) — 직접 조작으로 회피하세요')
    
        elif msg.data == 'obstacle_cleared':
            # 정보용 로그만, 자동 재시작 안 함 (사용자가 결정)
            self.get_logger().info(
                '✅ 전방 장애물 해소. 자율주행 재시작하려면 [m] 키 입력')

    # ===== 기존 기능 =====
    def goal_cb(self, msg: PoseStamped):
        self.last_goal = msg
        self._goal_locked = True
        self.get_logger().info(
            f'목적지 저장: x={msg.pose.position.x:.2f}, y={msg.pose.position.y:.2f}')

    def plan_cb(self, msg):
        if self._goal_locked:
            return

        if len(msg.poses) > 0:
            goal_pose = PoseStamped()
            goal_pose.header = msg.header
            goal_pose.pose = msg.poses[-1].pose
            self.last_goal = goal_pose
            self.get_logger().info(
                f'목적지 저장 (plan): x={goal_pose.pose.position.x:.2f}, '
                f'y={goal_pose.pose.position.y:.2f}')

    def nav_cmd_callback(self, msg):
        self.latest_nav_cmd = msg

    def teleop_cmd_callback(self, msg):
        self.latest_teleop_cmd = msg
        self.last_teleop_time = time.time()

        # 사용자가 방향키를 눌러서 속도 값이 0이 아닌 경우
        if msg.linear.x != 0.0 or msg.angular.z != 0.0:
            if self.mode == 'auto':
                self.get_logger().warn('>>> 사용자의 수동 조작 감지! 자율주행 모드를 해제합니다.')
                
                # 1. 모드를 수동(manual)으로 바꿉니다.
                self.mode = 'manual'
                
                # 2. 현재 Nav2가 수행 중인 이동 작업을 취소합니다.
                self.cancel_nav()

    def mode_cmd_callback(self, msg):
        cmd = msg.data.strip().lower()
        if cmd == 'm':
            self.switch_mode()
        elif cmd == 'home':
            self._send_home_goal()

    def control_loop(self):
        if self.mode == 'auto':
            self.cmd_pub.publish(self.latest_nav_cmd)
        else:
            if time.time() - self.last_teleop_time < 0.5:
                self.cmd_pub.publish(self.latest_teleop_cmd)
            else:
                self.cmd_pub.publish(Twist())

    def publish_mode(self):
        mode_msg = String()
        mode_msg.data = self.mode
        self.mode_pub.publish(mode_msg)

    def switch_mode(self):
        self.cmd_pub.publish(Twist())
        self.latest_nav_cmd = Twist()
        self.latest_teleop_cmd = Twist()

        if self.mode == 'manual':
            self.mode = 'auto'
            self.get_logger().info('>>> 자율주행 모드로 전환')
            self.resume_nav()
        else:
            self.mode = 'manual'
            self.get_logger().info('>>> 수동 조작 모드로 전환')
            self.cancel_nav()

    def cancel_nav(self):
        try:
            if self._cancel_client.service_is_ready():
                request = CancelGoal.Request()
                self._cancel_client.call_async(request)
                self.get_logger().info('Nav2 goal 취소 완료')
            else:
                self.get_logger().warn('Nav2 cancel 서버 없음')
        except Exception as e:
            self.get_logger().warn(f'Nav2 취소 중 오류: {e}')
        self._goal_handle = None

    def resume_nav(self):
        if self.last_goal is None:
            self.get_logger().warn('저장된 목적지 없음 - RViz에서 목적지를 찍어주세요')
            return

        if not self._nav_client.wait_for_server(timeout_sec=2.0):
            self.get_logger().error('navigate_to_pose 서버 연결 실패')
            return

        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = PoseStamped()
        goal_msg.pose.header.frame_id = self.last_goal.header.frame_id
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg.pose.pose = self.last_goal.pose

        self.get_logger().info(
            f'목적지 재전송: x={self.last_goal.pose.position.x:.2f}, '
            f'y={self.last_goal.pose.position.y:.2f}')

        send_future = self._nav_client.send_goal_async(goal_msg)
        send_future.add_done_callback(self._goal_response_cb)

    def _goal_response_cb(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().warn('Goal 거부됨!')
            return
        self.get_logger().info('Goal 수락됨 - 네비게이션 재개')
        self._goal_handle = goal_handle

    def key_listener(self):
        old_settings = termios.tcgetattr(sys.stdin)
        try:
            tty.setraw(sys.stdin.fileno())
            while rclpy.ok():
                key = sys.stdin.read(1)
                if key in ('m', 'M'):
                    self.switch_mode()
                elif key in ('h', 'H'):
                    self._send_home_goal()
                elif key in ('q', 'Q'):
                    self.get_logger().info('종료합니다.')
                    rclpy.shutdown()
                    break
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)


def main(args=None):
    rclpy.init(args=args)
    node = ModeSwitchNode()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()