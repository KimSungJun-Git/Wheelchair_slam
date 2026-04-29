include "map_builder.lua"
include "trajectory_builder.lua"

options = {
  map_builder = MAP_BUILDER,
  trajectory_builder = TRAJECTORY_BUILDER,
  map_frame = "map",
  tracking_frame = "base_footprint", -- [수정] IMU 대신 로봇 중심을 추적 기준으로 변경
  published_frame = "odom",
  odom_frame = "odom",
  provide_odom_frame = false,
  publish_frame_projected_to_2d = true,
  use_odometry = true,
  use_nav_sat = false,
  use_landmarks = false,
  num_laser_scans = 1,
  num_multi_echo_laser_scans = 0,
  num_subdivisions_per_laser_scan = 1,
  num_point_clouds = 0,
  lookup_transform_timeout_sec = 1.0, -- [수정] TF 지연으로 인한 에러를 막기 위해 대기 시간 증가
  submap_publish_period_sec = 0.3,
  pose_publish_period_sec = 5e-3,
  trajectory_publish_period_sec = 30e-3,
  rangefinder_sampling_ratio = 1.,
  odometry_sampling_ratio = 1.0,      -- [수정] IMU가 없으므로 오도메트리를 100% 신뢰하도록 1.0으로 변경
  fixed_frame_pose_sampling_ratio = 1.,
  imu_sampling_ratio = 1.,
  landmarks_sampling_ratio = 1.,
}

MAP_BUILDER.use_trajectory_builder_2d = true

TRAJECTORY_BUILDER_2D.min_range = 0.12
TRAJECTORY_BUILDER_2D.max_range = 10.0
TRAJECTORY_BUILDER_2D.missing_data_ray_length = 3.
TRAJECTORY_BUILDER_2D.use_imu_data = false -- IMU 사용 안 함 (유지)
TRAJECTORY_BUILDER_2D.use_online_correlative_scan_matching = true 

-- [유지] 진동으로 인한 불필요한 노이즈 맵핑 방지 (약 5.7도 이상 회전 시에만 업데이트)
TRAJECTORY_BUILDER_2D.motion_filter.max_angle_radians = math.rad(0.1)

-- [추가] IMU 부재를 보완하기 위해 라이다 스캔 매칭의 의존도와 탐색 범위를 높임
TRAJECTORY_BUILDER_2D.real_time_correlative_scan_matcher.linear_search_window = 0.1
TRAJECTORY_BUILDER_2D.real_time_correlative_scan_matcher.rotation_delta_cost_weight = 1.0

POSE_GRAPH.constraint_builder.min_score = 0.65
POSE_GRAPH.constraint_builder.global_localization_min_score = 0.7

-- POSE_GRAPH.optimize_every_n_nodes = 0

return options