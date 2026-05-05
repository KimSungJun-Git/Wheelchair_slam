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

        # ===== 임계값 (완화됨 — 실측 후 추가 튜닝 권장) =====
        # AMCL covariance: x(0), y(7), yaw(35) 위치
        self.cov_xy_threshold = 0.5       # m² — std≈0.7m  (이전 0.25에서 완화)
        self.cov_yaw_threshold = 0.5      # rad² — std≈40° (이전 0.25에서 완화)
        self.lost_grace_sec = 3.0         # 연속 N초 이상 위험 시 lost 판정 (이전 2.0에서 완화)

        self.first_lost_time = None
        self.is_lost = False

        # ===== 토픽/서비스 =====
        self.create_subscription(
            PoseWithCovarianceStamped, '/amcl_pose', self.amcl_cb, 10)

        # ⭐ 전용 토픽으로 분리 — safety_stop_node가 /emergency_stop/localization 구독
        self.emergency_pub = self.create_publisher(Bool, '/emergency_stop/localization', 10)
        self.sos_pub = self.create_publisher(String, '/sos_trigger', 10)
        self.status_pub = self.create_publisher(String, '/localization_status', 10)

        # AMCL의 global_localization 서비스 (전역 재인식)
        self.global_loc_client = self.create_client(Empty, '/reinitialize_global_localization')

        self.create_timer(0.5, self.publish_state)
        self.get_logger().info(
            f'Localization Monitor 시작 | cov_xy≤{self.cov_xy_threshold}, cov_yaw≤{self.cov_yaw_threshold}, '
            f'grace={self.lost_grace_sec}s | 토픽: /emergency_stop/localization')

    def amcl_cb(self, msg: PoseWithCovarianceStamped):
        cov = msg.pose.covariance
        cov_x, cov_y, cov_yaw = cov[0], cov[7], cov[35]

        danger = (cov_x > self.cov_xy_threshold or
                  cov_y > self.cov_xy_threshold or
                  cov_yaw > self.cov_yaw_threshold)

        now = self.get_clock().now()

        if danger:
            if self.first_lost_time is None:
                self.first_lost_time = now
                self.get_logger().warn(
                    f'⚠️ 위치 불확실: cov_x={cov_x:.3f}, cov_y={cov_y:.3f}, cov_yaw={cov_yaw:.3f}')
            elif not self.is_lost:
                elapsed = (now - self.first_lost_time).nanoseconds / 1e9
                if elapsed > self.lost_grace_sec:
                    self.is_lost = True
                    self.get_logger().error('🚨 위치 추적 분실 → 정지 + 글로벌 재인식 호출')
                    self.sos_pub.publish(String(data='localization_lost'))
                    self.trigger_global_relocalization()
        else:
            if self.is_lost:
                self.get_logger().info('✅ 위치 재인식 성공')
            self.first_lost_time = None
            self.is_lost = False

    def trigger_global_relocalization(self):
        if self.global_loc_client.wait_for_service(timeout_sec=1.0):
            self.global_loc_client.call_async(Empty.Request())
            self.get_logger().info('AMCL 파티클 재분포 요청 전송')
        else:
            self.get_logger().warn('reinitialize_global_localization 서비스 응답 없음')

    def publish_state(self):
        self.emergency_pub.publish(Bool(data=self.is_lost))
        status = 'lost' if self.is_lost else ('uncertain' if self.first_lost_time else 'ok')
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