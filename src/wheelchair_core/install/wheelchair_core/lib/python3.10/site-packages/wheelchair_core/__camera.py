#!/usr/bin/env python3
"""
camera_node.py (Gazebo 버전)
─────────────────────────────────────────────────────────────────
AprilTag 감지 → solvePnP → 주차 목표 좌표 3종 발행
- Gazebo 카메라 내부 파라미터 초기값 조정
- 마커 크기 8cm (0.08m) 고정
- TurtleBot3 기준 주차 오프셋 튜닝
"""

import sys
import numpy as np
import cv2

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo
from apriltag_msgs.msg import AprilTagDetectionArray
from geometry_msgs.msg import PointStamped


class TagPoseNode(Node):
    # ── 파라미터 ──────────────────────────────────────────────
    TAG_REAL_SIZE  = 0.08   # 마커 크기 (8cm)
    PARK_OFFSET_Z  = -0.30  # 마커 앞 30cm (깊이)
    
    # TurtleBot3 Waffle Pi 크기 고려
    # - 로봇 길이: 0.28m, 폭: 0.265m
    # - 마커로부터 측면 오프셋 조정
    PARK_OFFSET_X_RIGHT = 0.35   # 오른쪽 주차 (마커 기준 +X)
    PARK_OFFSET_X_LEFT  = -0.35  # 왼쪽 주차 (마커 기준 -X)

    def __init__(self, target_id: int = 0):
        super().__init__('tag_pose_node')
        self.target_id = target_id

        # 주차 방향 설정
        if self.target_id in [0, 1]:
            self.park_offset_x = self.PARK_OFFSET_X_RIGHT
            dir_text = "오른쪽 (➡️)"
        else:
            self.park_offset_x = self.PARK_OFFSET_X_LEFT
            dir_text = "왼쪽 (⬅️)"

        # ── 카메라 내부 파라미터 초기값 (Gazebo 기본 카메라) ──
        # Gazebo의 기본 카메라 설정: 640x480, FOV 60도
        # fx = fy = (640/2) / tan(30도) ≈ 554
        fx = fy = 554.0
        cx, cy  = 320.0, 240.0
        self._K = np.array([[fx, 0, cx],
                             [ 0, fy, cy],
                             [ 0,  0,  1]], dtype=np.float32)
        self._D = np.zeros(5, dtype=np.float32)
        self._got_camera_info = False

        # 3D 마커 코너 좌표 (태그 중심 기준, Z=0 평면)
        h = self.TAG_REAL_SIZE / 2.0
        self._obj_pts = np.array([
            [-h,  h, 0.0],
            [ h,  h, 0.0],
            [ h, -h, 0.0],
            [-h, -h, 0.0]
        ], dtype=np.float32)

        # ── 구독 ──────────────────────────────────────────────
        self.create_subscription(CameraInfo, '/camera_info', self._info_cb, 1)
        self.create_subscription(AprilTagDetectionArray, '/detections', self._det_cb, 10)

        # ── 발행 ──────────────────────────────────────────────
        self._pub_target  = self.create_publisher(PointStamped, '/tag/parking_target', 10)
        self._pub_raw     = self.create_publisher(PointStamped, '/tag/raw_tag',         10)
        self._pub_forward = self.create_publisher(PointStamped, '/tag/forward_dir',     10)

        colors = {0: "파란색(Blue)",  1: "빨간색(Red)",
                  2: "초록색(Green)", 3: "보라색(Purple)"}
        self.get_logger().info(
            f'🎯 TagPoseNode 준비 완료! [{self.target_id}번] {colors.get(self.target_id, "???")}')
        self.get_logger().info(f'🚗 주차 방향: 마커의 {dir_text}')

    # ── 콜백 ──────────────────────────────────────────────────
    def _info_cb(self, msg: CameraInfo):
        """camera_info 수신 시 내부 파라미터 업데이트"""
        if not self._got_camera_info:
            self._K = np.array(msg.k, dtype=np.float32).reshape(3, 3)
            self._D = np.array(msg.d, dtype=np.float32)
            self._got_camera_info = True
            self.get_logger().info(
                f'✅ camera_info 수신: '
                f'fx={self._K[0,0]:.1f}, fy={self._K[1,1]:.1f}, '
                f'cx={self._K[0,2]:.1f}, cy={self._K[1,2]:.1f}')

    def _det_cb(self, msg: AprilTagDetectionArray):
        """AprilTag 감지 콜백"""
        if not msg.detections:
            return

        # target_id에 해당하는 감지 결과 찾기
        target_det = None
        for det in msg.detections:
            try:
                cid = int(det.id[0])
            except (TypeError, IndexError):
                cid = int(det.id)
            if cid == self.target_id:
                target_det = det
                break

        if target_det is None:
            return

        # ── solvePnP 실행 ────────────────────────────────────
        try:
            img_pts = np.array(
                [[c.x, c.y] for c in target_det.corners], dtype=np.float32)

            ok, rvec, tvec = cv2.solvePnP(
                self._obj_pts, img_pts, self._K, self._D,
                flags=cv2.SOLVEPNP_IPPE_SQUARE)

            if not ok:
                return

            R, _ = cv2.Rodrigues(rvec)
            stamp = msg.header

            # ── 1. 마커 원점 발행 (카메라 기준 마커 위치) ────────
            raw = PointStamped()
            raw.header = stamp
            raw.point.x = float(tvec[0, 0])
            raw.point.y = float(tvec[1, 0])
            raw.point.z = float(tvec[2, 0])
            self._pub_raw.publish(raw)

            # ── 2. 마커 법선 방향 발행 (벽 정면 계산용) ────────
            front_tag = np.array([[0.0], [0.0], [-1.0]], dtype=np.float32)
            front_cam = R @ front_tag + tvec

            fwd = PointStamped()
            fwd.header = stamp
            fwd.point.x = float(front_cam[0, 0])
            fwd.point.y = float(front_cam[1, 0])
            fwd.point.z = float(front_cam[2, 0])
            self._pub_forward.publish(fwd)

            # ── 3. 주차 목표 지점 발행 ──────────────────────
            park_offset = np.array(
                [[self.park_offset_x], [0.0], [self.PARK_OFFSET_Z]], dtype=np.float32)
            park_cam = R @ park_offset + tvec

            target = PointStamped()
            target.header = stamp
            target.point.x = float(park_cam[0, 0])
            target.point.y = float(park_cam[1, 0])
            target.point.z = float(park_cam[2, 0])
            self._pub_target.publish(target)

            # ── 로그 ──────────────────────────────────────────
            dist = float(tvec[2, 0])
            if dist > 0.1:  # 최소 거리 필터
                self.get_logger().info(
                    f'📍 마커[{self.target_id}] 거리: {dist:.2f}m | '
                    f'목표: ({target.point.x:.3f}, {target.point.y:.3f}, {target.point.z:.3f})',
                    throttle_duration_sec=0.5)

        except Exception as e:
            self.get_logger().error(f'❌ solvePnP 오류: {str(e)}')


def main(args=None):
    rclpy.init(args=args)
    
    # 고정된 마커 ID (0번)로 실행
    node = TagPoseNode(target_id=0)
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()