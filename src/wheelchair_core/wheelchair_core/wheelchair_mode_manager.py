import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import PoseStamped, Twist
from std_msgs.msg import String
from action_msgs.srv import CancelGoal
from typing import Optional
from rclpy.executors import MultiThreadedExecutor
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy

class WheelchairModeManager(Node):
    def __init__(self):
        super().__init__('wheelchair_mode_manager')

        # ── Action Client ──
        self._nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        
        # ── Cancel Service Client (★ 이게 핵심) ──
        self._cancel_client = self.create_client(
            CancelGoal,
            '/navigate_to_pose/_action/cancel_goal'
        )

        # ── 상태 ──
        self.last_goal: Optional[PoseStamped] = None
        self._goal_handle = None
        self.current_mode = 'nav'

        # ── 목적지 구독 ──
        goal_qos = QoSProfile(
            depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL
        )
        self.create_subscription(PoseStamped, '/goal_pose', self.goal_cb, goal_qos)

        # ── 모드 전환 구독 ──
        self.create_subscription(String, '/mode_switch', self.mode_cb, 10)
        from nav_msgs.msg import Path
        self.create_subscription(Path, '/plan', self.plan_cb, 10)

        self.get_logger().info('모드 매니저 시작 — 기본 모드: nav')

        self.get_logger().info('모드 매니저 시작 — 기본 모드: nav')

    def goal_cb(self, msg: PoseStamped):
        self.last_goal = msg
        self.get_logger().info('목적지 저장 완료')
        
    def plan_cb(self, msg):
        """Nav2 경로의 마지막 포인트 = 목적지"""
        if len(msg.poses) > 0:
            goal_pose = PoseStamped()
            goal_pose.header = msg.header
            goal_pose.pose = msg.poses[-1].pose
            self.last_goal = goal_pose
            self.get_logger().info(
                f'목적지 저장 완료 (plan): '
                f'x={goal_pose.pose.position.x:.2f}, y={goal_pose.pose.position.y:.2f}'
            )

    def mode_cb(self, msg: String):
        cmd = msg.data.strip().lower()
        self.get_logger().info(f'모드 전환 명령 수신: {cmd}')

        if cmd == 'm' and self.current_mode == 'nav':
            self.switch_to_manual()
        elif cmd == 'n' and self.current_mode == 'manual':
            self.switch_to_nav()

    # ──────────────────────────────────────────
    # 수동 모드 — cancel service로 확실하게 취소
    # ──────────────────────────────────────────
    def switch_to_manual(self):
        self.current_mode = 'manual'
        self.get_logger().info('▶ 수동 모드 전환')

        # ★ wait_for_service 없이 바로 호출
        cancel_req = CancelGoal.Request()
        future = self._cancel_client.call_async(cancel_req)
        future.add_done_callback(self._cancel_done_cb)

        self._goal_handle = None

    def _cancel_done_cb(self, future):
        try:
            result = future.result()
            self.get_logger().info(
                f'  cancel 완료 — 취소된 goal 수: {len(result.goals_canceling)}'
            )
        except Exception as e:
            self.get_logger().error(f'  cancel 실패: {e}')

    # ──────────────────────────────────────────
    # 자율주행 복귀
    # ──────────────────────────────────────────
    def switch_to_nav(self):
        if self.last_goal is None:
            self.get_logger().warn('저장된 목적지 없음')
            return

        self.current_mode = 'nav'
        self.get_logger().info('▶ 자율주행 복귀')

        goal_pose = PoseStamped()
        goal_pose.header.frame_id = self.last_goal.header.frame_id
        goal_pose.header.stamp = self.get_clock().now().to_msg()
        goal_pose.pose = self.last_goal.pose

        self.send_goal(goal_pose)

    # ──────────────────────────────────────────
    # Goal 전송
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

        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self._result_cb)

    def _result_cb(self, future):
        result = future.result()
        self.get_logger().info(f'  네비게이션 완료: {result.status}')
        self._goal_handle = None

    def _feedback_cb(self, feedback_msg):
        pass


def main(args=None):
    rclpy.init(args=args)
    node = WheelchairModeManager()

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