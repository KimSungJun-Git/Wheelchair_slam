import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import PoseStamped, Twist
from std_msgs.msg import String
from typing import Optional
import threading


class WheelchairModeManager(Node):
    def __init__(self):
        super().__init__('wheelchair_mode_manager')

        # ── Action Client (BasicNavigator 대신 직접 사용) ──
        self._nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')

        # ── 상태 ──
        self.last_goal: Optional[PoseStamped] = None

        self._goal_handle = None          # 현재 진행 중인 goal
        self.current_mode = 'nav'         # 'nav' or 'manual'

        # ── cmd_vel 퍼블리셔 (정지 명령용) ──
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)

        # ── 목적지 구독 ──
        self.create_subscription(PoseStamped, '/goal_pose', self.goal_cb, 10)

        # ── 모드 전환 구독 (키보드 노드에서 퍼블리시) ──
        self.create_subscription(String, '/mode_switch', self.mode_cb, 10)

        self.get_logger().info('모드 매니저 시작 — 기본 모드: nav')

    # ──────────────────────────────────────────
    # 목적지 수신
    # ──────────────────────────────────────────
    def goal_cb(self, msg: PoseStamped):
        self.last_goal = msg
        self.get_logger().info('목적지 저장 완료')
        # 자동으로 네비게이션 시작
        if self.current_mode == 'nav':
            self.send_goal(msg)

    # ──────────────────────────────────────────
    # 모드 전환  ('m' → manual,  'n' → nav)
    # ──────────────────────────────────────────
    def mode_cb(self, msg: String):
        cmd = msg.data.strip().lower()

        if cmd == 'm' and self.current_mode == 'nav':
            self.switch_to_manual()
        elif cmd == 'n' and self.current_mode == 'manual':
            self.switch_to_nav()

    # ──────────────────────────────────────────
    # 수동 모드 전환
    # ──────────────────────────────────────────
    def switch_to_manual(self):
        self.current_mode = 'manual'
        self.get_logger().info('▶ 수동 모드 전환')

        # 1) 현재 goal 취소
        if self._goal_handle is not None:
            self.get_logger().info('  네비게이션 goal 취소 요청...')
            cancel_future = self._goal_handle.cancel_goal_async()
            cancel_future.add_done_callback(self._cancel_done_cb)
        
        # 2) 즉시 정지 명령
        self.publish_stop()

    def _cancel_done_cb(self, future):
        result = future.result()
        self.get_logger().info(f'  cancel 결과: {result}')
        self._goal_handle = None
        # 혹시 cancel 후에도 움직이면 한 번 더 정지
        self.publish_stop()

    # ──────────────────────────────────────────
    # 자율주행 복귀
    # ──────────────────────────────────────────
    def switch_to_nav(self):
        if self.last_goal is None:
            self.get_logger().warn('저장된 목적지 없음 — RViz에서 목적지를 찍어주세요')
            return

        self.current_mode = 'nav'
        self.get_logger().info('▶ 자율주행 복귀')

        # ★ 핵심: 타임스탬프를 현재 시간으로 갱신
        goal_pose = PoseStamped()
        goal_pose.header.frame_id = self.last_goal.header.frame_id
        goal_pose.header.stamp = self.get_clock().now().to_msg()   # ← 이게 중요!
        goal_pose.pose = self.last_goal.pose

        self.send_goal(goal_pose)

    # ──────────────────────────────────────────
    # Goal 전송 (Action Client 직접 사용)
    # ──────────────────────────────────────────
    def send_goal(self, pose: PoseStamped):
        if not self._nav_client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error('navigate_to_pose 액션 서버 연결 실패')
            return

        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = pose

        self.get_logger().info('  Goal 전송 중...')
        send_future = self._nav_client.send_goal_async(
            goal_msg,
            feedback_callback=self._feedback_cb
        )
        send_future.add_done_callback(self._goal_response_cb)

    def _goal_response_cb(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().warn('  Goal 거부됨!')
            return
        self.get_logger().info('  Goal 수락됨 — 네비게이션 시작')
        self._goal_handle = goal_handle

        # 결과 대기 (비동기)
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self._result_cb)

    def _result_cb(self, future):
        result = future.result()
        self.get_logger().info(f'  네비게이션 완료: {result.status}')
        self._goal_handle = None

    def _feedback_cb(self, feedback_msg):
        pass  # 필요하면 진행률 로깅

    # ──────────────────────────────────────────
    # 유틸
    # ──────────────────────────────────────────
    def publish_stop(self):
        stop = Twist()  # 모든 값 0.0
        for _ in range(5):  # 여러 번 보내서 확실히 정지
            self.cmd_pub.publish(stop)


def main(args=None):
    rclpy.init(args=args)
    node = WheelchairModeManager()
    
    # ★ MultiThreadedExecutor 사용 — action 콜백이 제대로 처리됨
    from rclpy.executors import MultiThreadedExecutor
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