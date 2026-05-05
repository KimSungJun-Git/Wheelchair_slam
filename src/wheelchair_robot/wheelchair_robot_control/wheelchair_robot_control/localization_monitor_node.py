#!/usr/bin/env python3
# localization_monitor_node.py
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseWithCovarianceStamped
from std_srvs.srv import Empty
from std_msgs.msg import Bool, String


class LocalizationMonitor(Node):
    def __init__(self):
        super().__init__('localization_monitor')

        # ===== 임계값 =====
        self.cov_xy_threshold = 0.5
        self.cov_yaw_threshold = 0.5
        self.lost_grace_sec = 3.0
        self.amcl_stale_sec = 2.0       # AMCL 끊김 판정 시간
        self.startup_grace_sec = 5.0    # 부팅 직후 NO_AMCL 경고 보류 시간

        # ===== 상태 머신 =====
        # 'init' → 'no_amcl' / 'ok' / 'stale' / 'uncertain' / 'lost'
        self.state = 'init'

        # 측정 데이터
        self.last_cov_x = None
        self.last_cov_y = None
        self.last_cov_yaw = None
        self.last_amcl_time = None
        self.first_uncertain_time = None

        self.start_time = self.get_clock().now()

        # ===== 토픽/서비스 =====
        self.create_subscription(
            PoseWithCovarianceStamped, '/amcl_pose', self.amcl_cb, 10)

        self.emergency_pub = self.create_publisher(Bool, '/emergency_stop/localization', 10)
        self.sos_pub = self.create_publisher(String, '/sos_trigger', 10)
        self.status_pub = self.create_publisher(String, '/localization_status', 10)

        self.global_loc_client = self.create_client(Empty, '/reinitialize_global_localization')

        # 상태 토픽은 0.5s 주기 (safety_stop_node 호환성 유지)
        self.create_timer(0.5, self.publish_state)
        # 상태 머신 평가는 1Hz — 전이가 발생할 때만 로그 출력
        self.create_timer(1.0, self.evaluate_state)

        self.get_logger().info(
            f'Localization Monitor 시작 | cov_xy≤{self.cov_xy_threshold}, '
            f'cov_yaw≤{self.cov_yaw_threshold}, grace={self.lost_grace_sec}s | '
            '상태 전이 시에만 로그 출력')

    def amcl_cb(self, msg: PoseWithCovarianceStamped):
        """AMCL 메시지 도착 시 데이터만 갱신. 로그는 evaluate_state에서."""
        cov = msg.pose.covariance
        self.last_cov_x = cov[0]
        self.last_cov_y = cov[7]
        self.last_cov_yaw = cov[35]
        self.last_amcl_time = self.get_clock().now()

    def evaluate_state(self):
        """1Hz로 상태를 평가. 전이가 있으면 그때만 로그 + 액션."""
        now = self.get_clock().now()
        new_state = self._compute_state(now)

        if new_state == self.state:
            return  # 변화 없음 — 로그 안 함

        old_state = self.state
        self.state = new_state
        self._log_transition(old_state, new_state, now)
        self._handle_transition(new_state)

    def _compute_state(self, now):
        # 1) AMCL 미수신
        if self.last_amcl_time is None:
            elapsed_boot = (now - self.start_time).nanoseconds / 1e9
            return 'init' if elapsed_boot < self.startup_grace_sec else 'no_amcl'

        # 2) AMCL 끊김
        age = (now - self.last_amcl_time).nanoseconds / 1e9
        if age > self.amcl_stale_sec:
            return 'stale'

        # 3) covariance 평가 (None 가드 — Pylance 정적 검사 통과용)
        if (self.last_cov_x is None or
                self.last_cov_y is None or
                self.last_cov_yaw is None):
            return 'init'

        danger = (self.last_cov_x > self.cov_xy_threshold or
                  self.last_cov_y > self.cov_xy_threshold or
                  self.last_cov_yaw > self.cov_yaw_threshold)

        if not danger:
            self.first_uncertain_time = None
            return 'ok'

        if self.first_uncertain_time is None:
            self.first_uncertain_time = now

        elapsed = (now - self.first_uncertain_time).nanoseconds / 1e9
        return 'lost' if elapsed > self.lost_grace_sec else 'uncertain'

    def _log_transition(self, old, new, now):
        cov_str = ''
        if self.last_cov_x is not None:
            cov_str = (f' | cov_x={self.last_cov_x:.3f}, '
                       f'cov_y={self.last_cov_y:.3f}, '
                       f'cov_yaw={self.last_cov_yaw:.3f}')

        if new == 'ok':
            if old in ('init', 'no_amcl'):
                self.get_logger().info(f'✅ 위치 추적 시작{cov_str}')
            elif old == 'stale':
                self.get_logger().info(f'✅ AMCL 수신 복귀{cov_str}')
            elif old == 'lost':
                self.get_logger().info(f'✅ 위치 재인식 성공{cov_str}')
            elif old == 'uncertain':
                self.get_logger().info(f'✅ 위치 정상 복귀{cov_str}')

        elif new == 'no_amcl':
            self.get_logger().warn(
                '⏳ AMCL pose 미수신 — /amcl_pose, map_server, /scan 점검 필요')

        elif new == 'stale':
            age = (now - self.last_amcl_time).nanoseconds / 1e9
            self.get_logger().warn(f'⏰ AMCL 수신 끊김 — 마지막 수신 {age:.1f}s 전')

        elif new == 'uncertain':
            self.get_logger().warn(f'⚠️ 위치 불확실{cov_str}')

        elif new == 'lost':
            self.get_logger().error(
                f'🚨 위치 추적 분실{cov_str} → 글로벌 재인식 호출')

    def _handle_transition(self, new):
        if new == 'lost':
            self.sos_pub.publish(String(data='localization_lost'))
            self._trigger_global_relocalization()

    def _trigger_global_relocalization(self):
        if self.global_loc_client.wait_for_service(timeout_sec=1.0):
            self.global_loc_client.call_async(Empty.Request())
            self.get_logger().info('AMCL 파티클 재분포 요청 전송')
        else:
            self.get_logger().warn('reinitialize_global_localization 서비스 응답 없음')

    def publish_state(self):
        """외부 노드 호환 토픽 — 기존 is_lost 의미 유지 (covariance 분실만)"""
        is_lost = (self.state == 'lost')
        self.emergency_pub.publish(Bool(data=is_lost))

        if self.state == 'lost':
            status = 'lost'
        elif self.state == 'uncertain':
            status = 'uncertain'
        else:
            status = 'ok'
        self.status_pub.publish(String(data=status))


def main():
    rclpy.init()
    node = LocalizationMonitor()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()