#!/usr/bin/env python3
import sys
import numpy as np
import cv2
from scipy.spatial.transform import Rotation

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo
from apriltag_msgs.msg import AprilTagDetectionArray
from geometry_msgs.msg import PointStamped

class TagPoseNode(Node):
    TAG_REAL_SIZE = 0.15
    PARK_OFFSET_Z = 0.45   # 태그 앞 45cm (앞뒤 거리는 동일)

    def __init__(self, target_id):
        super().__init__('tag_pose_node')
        self.target_id = int(target_id)
        self.no_tag_count = 0

        # ⭐️ 핵심 추가: 번호에 따라 주차 방향(좌/우)을 자동으로 바꿉니다!
        if self.target_id in [0, 1]:
            self.PARK_OFFSET_X = 0.40  # 파랑, 빨강은 기둥 오른쪽
            dir_text = "오른쪽 (➡️)"
        else:
            self.PARK_OFFSET_X = -0.40 # 초록, 보라는 기둥 왼쪽 (거울 모드)
            dir_text = "왼쪽 (⬅️)"

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

        self._pub_target = self.create_publisher(PointStamped, '/tag/parking_target', 10)
        self._pub_tag_raw = self.create_publisher(PointStamped, '/tag/raw_tag', 10)

        colors = {0: "파란색(Blue)", 1: "빨간색(Red)", 2: "초록색(Green)", 3: "보라색(Purple)"}
        color_name = colors.get(self.target_id, "알 수 없음")
        
        self.get_logger().info(f'TagPoseNode 준비 완료! 🎯 목표: [{self.target_id}번] {color_name} 기둥')
        self.get_logger().info(f'🚗 주차 방향 설정: 기둥의 {dir_text}') # 터미널에 방향 표시

    def _info_cb(self, msg: CameraInfo):
        if not self._got_camera_info:
            self._K = np.array(msg.k, dtype=np.float32).reshape(3, 3)
            self._D = np.array(msg.d, dtype=np.float32)
            self._got_camera_info = True

    def _det_cb(self, msg: AprilTagDetectionArray):
        if not msg.detections:
            self.no_tag_count += 1
            if self.no_tag_count % 30 == 0:
                self.get_logger().info('👀 화면에 아무 기둥도 안 보입니다. 휠체어를 돌려주세요!')
            return

        self.no_tag_count = 0
        
        target_det = None
        for det in msg.detections:
            try:
                cid = int(det.id[0])
            except TypeError:
                cid = int(det.id)
                
            if cid == self.target_id:
                target_det = det
                break

        if target_det is None:
            return # 목표 번호가 아니면 조용히 무시

        # 목표를 찾았을 때의 처리
        img_pts = np.array([[c.x, c.y] for c in target_det.corners], dtype=np.float32)
        ok, rvec, tvec = cv2.solvePnP(self._obj_pts, img_pts, self._K, self._D, flags=cv2.SOLVEPNP_IPPE_SQUARE)
        if not ok: return

        R, _ = cv2.Rodrigues(rvec)

        # 위에서 설정한 좌/우 오프셋(PARK_OFFSET_X)이 여기서 적용됩니다!
        park_tag = np.array([[self.PARK_OFFSET_X], [0.0], [self.PARK_OFFSET_Z]], dtype=np.float32)
        park_cam = R @ park_tag + tvec
        
        target = PointStamped()
        target.header = msg.header
        target.point.x, target.point.y, target.point.z = float(park_cam[0,0]), float(park_cam[1,0]), float(park_cam[2,0])
        self._pub_target.publish(target)

        raw_tag = PointStamped()
        raw_tag.header = msg.header
        raw_tag.point.x, raw_tag.point.y, raw_tag.point.z = float(tvec[0,0]), float(tvec[1,0]), float(tvec[2,0])
        self._pub_tag_raw.publish(raw_tag)

def main(args=None):
    print("\n" + "="*50)
    print("🏥 병실 주차 타겟을 선택하세요 (AprilTag 번호)")
    print("  [0] 파란색 기둥 (Blue)")
    print("  [1] 빨간색 기둥 (Red)")
    print("  [2] 초록색 기둥 (Green)")
    print("  [3] 보라색 기둥 (Purple)")
    print("="*50)
    
    selected_id = 0
    while True:
        try:
            val = input("👉 주차할 번호를 입력하세요 (0~3): ")
            selected_id = int(val)
            if selected_id in [0, 1, 2, 3]:
                break
            else:
                print("⚠️ 0, 1, 2, 3 중에서 하나의 숫자만 입력해주세요.\n")
        except ValueError:
            print("⚠️ 숫자를 입력해주세요.\n")
            
    rclpy.init(args=args)
    node = TagPoseNode(target_id=selected_id)
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