include "map_builder.lua"
include "trajectory_builder.lua"

options = {
  map_builder = MAP_BUILDER,
  trajectory_builder = TRAJECTORY_BUILDER,
  map_frame = "map",
  tracking_frame = "imu_link",    --1. 보통 imu기준으로 잡는다.
  published_frame = "odom",       --1. 계산한 위치를 어떤 프레임으로 보낼지 odom으로 보낸다.
  odom_frame = "odom",    
  provide_odom_frame = false,     --1. slam이 직접 odom좌표개를 생성할지 여부
  publish_frame_projected_to_2d = true,
  use_odometry = true,            --1. 바퀴 회전수를 위치추정에 사용할 것인지
  use_nav_sat = false,            
  use_landmarks = false,
  num_laser_scans = 1,            --1. 라이다의 개수
  num_multi_echo_laser_scans = 0,
  num_subdivisions_per_laser_scan = 1,
  num_point_clouds = 0,
  lookup_transform_timeout_sec = 0.2,
  submap_publish_period_sec = 0.3,
  pose_publish_period_sec = 5e-3,
  trajectory_publish_period_sec = 30e-3,
  rangefinder_sampling_ratio = 1.,
  odometry_sampling_ratio = 1.,
  fixed_frame_pose_sampling_ratio = 1.,
  imu_sampling_ratio = 1.,
  landmarks_sampling_ratio = 1.,
}

MAP_BUILDER.use_trajectory_builder_2d = true

TRAJECTORY_BUILDER_2D.min_range = 0.12    --2. 라이더 인식할 거리 범위
TRAJECTORY_BUILDER_2D.max_range = 3.5     --2. 라이더 인식할 거리 범위
TRAJECTORY_BUILDER_2D.missing_data_ray_length = 3.
TRAJECTORY_BUILDER_2D.use_imu_data = true    --2. slam에서 IMU데이터를 사용할지 결정 false면 라이다와 모도메트리에 집중
TRAJECTORY_BUILDER_2D.use_online_correlative_scan_matching = true 
TRAJECTORY_BUILDER_2D.motion_filter.max_angle_radians = math.rad(0.1)  --2. 로봇이 아주 조금 움직였을 때는 지도를 갱신하지 않도록 필터링하여 연산량을 줄입니다.

POSE_GRAPH.constraint_builder.min_score = 0.65  --3. 새로운 스캔 데이터가 기존 지도와 얼마나 일치해야
--값을 낮추면 비슷해도 같은곳으로 인식한다
POSE_GRAPH.constraint_builder.global_localization_min_score = 0.7  --3.로봇이 자기 위치를 완전히 잃어버렸을 때, 전체 지도에서 현재 위치를 찾기 위한 최소 일치 점수입니다.
-- 값을 높이면 신중하게 천천히 이동한다. 낮추면 잘못된 곳을 잡을 수 있다
-- POSE_GRAPH.optimize_every_n_nodes = 0

return options
