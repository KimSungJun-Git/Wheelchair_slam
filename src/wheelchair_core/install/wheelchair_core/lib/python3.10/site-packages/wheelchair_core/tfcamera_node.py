#!/usr/bin/env python3
import numpy as np
import cv2
from scipy.spatial.transform import Rotation

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo
from apriltag_msgs.msg import AprilTagDetectionArray
from geometry_msgs.msg import PointStamped, PoseStamped

class TagPoseNode(Node):
    TAG_REAL_SIZE = 0.15

    def __init__(self):
        super().__init__('tag_pose_node')
        
        # ⭐️ ROS2 파라미터 선언 (기본값 설정)
        self.declare_parameter('target_id', 0)
        self.declare_parameter('park_offset_x', 0.40) # 기둥에서 우측으로 거리
        self.declare_parameter('park_offset_z', 0.45) # 기둥에서 앞쪽으로 거리
        
        self.target_id = self.get_parameter('target_id').value

        fx = fy = 554.0
        cx, cy  = 320.0, 240.0
        self._K = np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]], dtype=np.float32)
        self._D = np.zeros(5, dtype=np.float32)
        self._got_camera_info = False

        h = self.TAG_REAL_SIZE / 2.0
        self._obj_pts = np.array([
            [-h,  h, 0.0], [ h,  h, 0.0], [ h, -h, 0.0], [-h, -h, 0.0]
        ], dtype=np.float32)

        self.create_subscription(CameraInfo, '/camera_info', self._info_cb, 1)
        self.create_subscription(AprilTagDetectionArray, '/detections', self._det_cb, 10)

        self._pub_target  = self.create_publisher(PointStamped, '/tag/parking_target', 10)
        self._pub_tag_raw = self.create_publisher(PointStamped, '/tag/raw_tag', 10)
        self._pub_pose    = self.create_publisher(PoseStamped, '/tag/pose', 10)

        self.get_logger().info('TagPoseNode 준비 완료 (파라미터 적용)')

    def _info_cb(self, msg: CameraInfo):
        if not self._got_camera_info:
            self._K = np.array(msg.k, dtype=np.float32).reshape(3, 3)
            self._D = np.array(msg.d, dtype=np.float32)
            self._got_camera_info = True

    def _det_cb(self, msg: AprilTagDetectionArray):
        # ⭐️ 루프 돌 때마다 파라미터 최신값 가져오기 (실시간 변경 반영)
        offset_x = self.get_parameter('park_offset_x').value
        offset_z = self.get_parameter('park_offset_z').value

        for det in msg.detections:
            if det.id != self.target_id: continue

            img_pts = np.array([[c.x, c.y] for c in det.corners], dtype=np.float32)
            ok, rvec, tvec = cv2.solvePnP(self._obj_pts, img_pts, self._K, self._D, flags=cv2.SOLVEPNP_IPPE_SQUARE)
            if not ok: break

            R, _ = cv2.Rodrigues(rvec)

            # 1. 주차 목표 지점 계산
            park_tag = np.array([[offset_x], [0.0], [offset_z]], dtype=np.float32)
            park_cam = R @ park_tag + tvec
            
            target = PointStamped()
            target.header = msg.header
            target.point.x, target.point.y, target.point.z = float(park_cam[0,0]), float(park_cam[1,0]), float(park_cam[2,0])
            self._pub_target.publish(target)

            # 2. 마커 원본 위치
            raw_tag = PointStamped()
            raw_tag.header = msg.header
            raw_tag.point.x, raw_tag.point.y, raw_tag.point.z = float(tvec[0,0]), float(tvec[1,0]), float(tvec[2,0])
            self._pub_tag_raw.publish(raw_tag)

            self._publish_pose(msg.header, R, tvec)
            break

    def _publish_pose(self, header, R, tvec):
        q = Rotation.from_matrix(R).as_quat()
        ps = PoseStamped()
        ps.header = header
        ps.pose.position.x, ps.pose.position.y, ps.pose.position.z = float(tvec[0,0]), float(tvec[1,0]), float(tvec[2,0])
        ps.pose.orientation.x, ps.pose.orientation.y, ps.pose.orientation.z, ps.pose.orientation.w = float(q[0]), float(q[1]), float(q[2]), float(q[3])
        self._pub_pose.publish(ps)

def main(args=None):
    rclpy.init(args=args)
    rclpy.spin(TagPoseNode())
    rclpy.shutdown()

if __name__ == '__main__':
    main()