# wheelchair_robot_fake

하드웨어 없이 **프로젝트 전체 파이프라인**을 RViz에서 검증하기 위한 가짜 센서 패키지.

## 무엇이 작동하는가

| 다른 패키지의 기능 | fake 환경에서 작동? | 비고 |
|---|---|---|
| URDF TF (description) | ✓ | `robot_state_publisher` |
| EKF 융합 (control) | ✓ | `/odom`+`/imu/data` |
| AMCL 위치추정 (navigation2) | ✓ | 가짜 lidar가 실제 맵에 raycasting |
| Nav2 경로계획/컨트롤 | ✓ | RPP, BT navigator, behavior |
| safety_stop_node | ✓ | LiDAR 거리 + AMCL zone 모두 |
| Keepout filter | ✓ | 동일 mask 파일 사용 |
| Speed filter | ✓ | 동일 mask 파일 사용 |
| mode_switch_node | ✓ | `/destination` 토픽으로 제어 |
| localization_monitor_node | ✓ | `/amcl_pose` 모니터링 |
| imu_safety_node | ✓ | 가짜 IMU 데이터 입력 |
| Web UI (rosbridge) | ✓ | 별도 `web_ui.launch.py`로 띄움 |
| log_collector_node (AI) | ✓ | `/safety_alert` 등 동일하게 발행됨 |

## 설치

```bash
cd ~/wheelchair_ws
colcon build --packages-select wheelchair_robot_fake --symlink-install
source install/setup.bash
```

## 4가지 실행 모드

### A) 위치 추정만, 가상 룸 (`fake_bringup`)

가장 가벼움. EKF + RViz만. SLAM 매핑 전 단계.

```bash
ros2 launch wheelchair_robot_fake fake_bringup.launch.py

# 가상 룸 크기를 실제 맵 크기에 맞추기 (벽 위치만 자동 정렬)
ros2 launch wheelchair_robot_fake fake_bringup.launch.py \
    room_from_map:=$HOME/wheelchair_ws/src/wheelchair_robot/wheelchair_robot_navigation2/map/wheelchair_robot_world.yaml
```

### B) 기존 맵 + AMCL 위치추정만 (`fake_localization`)

Nav2 없이 AMCL 단독. 위치 분실/복구 시나리오 테스트용.

```bash
ros2 launch wheelchair_robot_fake fake_localization.launch.py
```

### C) Cartographer 매핑 (`fake_slam`)

가상 룸에서 새 맵을 그리는 시나리오.

```bash
ros2 launch wheelchair_robot_fake fake_slam.launch.py
```

### D) **풀 파이프라인** (`fake_navigation`) ⭐

기존 프로젝트의 전부를 fake 환경에서 한 번에 실행.

```bash
# RViz Nav2 Goal 버튼으로 바로 목적지 이동 테스트
ros2 launch wheelchair_robot_fake fake_navigation.launch.py use_relay:=true

# 또는 mode_switch_node를 통한 풀스택 (기본)
ros2 launch wheelchair_robot_fake fake_navigation.launch.py
```

#### 목적지로 이동시키는 3가지 방법

**1. RViz의 "Nav2 Goal" 버튼** (가장 빠름)
- 단, mode_switch_node가 manual이라 `/cmd_vel`이 안 흐름
- `use_relay:=true`로 띄우면 mode_switch 우회 → 즉시 작동
- 또는 mode_switch 터미널에서 'm' 키로 auto 전환

**2. 토픽으로 목적지 이름 보내기** (권장)
mode_switch_node가 받으면 자동으로 auto 모드 전환 + Nav2 goal 전송.

```bash
ros2 topic pub /destination std_msgs/String "data: 'room_101'" --once
ros2 topic pub /destination std_msgs/String "data: 'home'" --once
ros2 topic pub /go_home std_msgs/Empty "{}" --once
```

목적지 이름은 `mode_switch_node`의 `destinations` 딕셔너리 참조 (home, room_101, room_102, emergency 등).

**3. /goal_pose 직접 발행** (Nav2 raw)

```bash
ros2 topic pub /goal_pose geometry_msgs/PoseStamped \
  "{header: {frame_id: 'map'}, pose: {position: {x: 1.8, y: 1.2, z: 0.0}, orientation: {w: 1.0}}}" --once
```

## 맵 정보 확인 (가상 벽 크기 맞추기용)

`map_inspector` 유틸로 맵 크기/범위를 확인:

```bash
ros2 run wheelchair_robot_fake map_inspector \
    $HOME/wheelchair_ws/src/wheelchair_robot/wheelchair_robot_navigation2/map/wheelchair_robot_world.yaml
```

출력 예시:
```
============================================================
  맵 파일: wheelchair_robot_world.yaml
============================================================
  픽셀 크기:  248 × 192
  해상도:     0.05 m/픽셀
  월드 크기:  12.40 m × 9.60 m
  X 범위:     [-1.45, +10.95]
  Y 범위:     [-1.60, +8.00]
  Origin:     (-1.45, -1.60)

  → fake_lidar 가상 룸 파라미터로 그대로 사용:
    -p room_x_min:=-1.45 -p room_x_max:=10.95 \
    -p room_y_min:=-1.60 -p room_y_max:=8.00

  → 또는 실제 맵 raycasting 사용 (권장):
    -p map_yaml:=/.../wheelchair_robot_world.yaml
```

fake_lidar도 부팅 시 같은 정보를 로그로 출력한다.

## cmd_vel 파이프라인

**use_relay=false (mode_switch_node 사용, 기본)**
```
Nav2 ──/cmd_vel_nav──▶ safety_stop ──/cmd_vel_safe──▶ mode_switch ──/cmd_vel──▶ fake_encoder
                       ▲
                   /scan, /amcl_pose
키보드 teleop ──/cmd_vel_teleop──▶ mode_switch
```

**use_relay=true (mode_switch 우회)**
```
Nav2 ──/cmd_vel_nav──▶ safety_stop ──/cmd_vel_safe──▶ relay ──/cmd_vel──▶ fake_encoder
```

## TF 트리

```
map → odom → base_footprint → base_link → imu_link, laser_frame
 ↑     ↑          ↑                              
AMCL  EKF      URDF                              
```

## 토픽 확인

```bash
# 핵심 발행 토픽
ros2 topic hz /scan /odom /imu/data /amcl_pose

# 파이프라인 추적
ros2 topic echo /cmd_vel_nav  --once
ros2 topic echo /cmd_vel_safe --once
ros2 topic echo /cmd_vel      --once

# 안전 상태
ros2 topic echo /safety_alert
ros2 topic echo /localization_status
ros2 topic echo /current_zone
ros2 topic echo /robot_mode
```

## 동작 원리

세 가짜 노드(`fake_encoder`, `fake_imu`, `fake_lidar`)가 모두 `/cmd_vel`을 받아 동일한 ground truth pose를 적분한다.
각자 노이즈를 더해 측정값처럼 발행하므로, EKF/AMCL이 실제와 유사한 드리프트/필터링 거동을 보여준다.

`fake_lidar`는 `map_yaml`을 지정하면 nav2 map_server 호환 PGM을 직접 파싱해서
그 점유 격자에 ray-march한다. → AMCL이 scan ↔ map 매칭으로 정상 작동.

`ekf.yaml`이 실제로 읽는 필드:
- `/odom` → `twist.linear.x`, `twist.angular.z`
- `/imu/data` → `angular_velocity.z`

나머지 필드들은 RViz 시각화/디버깅용으로 채워준다.
