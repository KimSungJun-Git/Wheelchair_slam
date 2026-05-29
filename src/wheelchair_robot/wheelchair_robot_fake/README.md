# wheelchair_robot_fake

하드웨어(엔코더 · IMU · LiDAR) 없이 RViz에서 SLAM/위치추정을 띄우기 위한 가짜 센서 노드 모음.

## 개요

세 가지 가짜 노드가 `/cmd_vel`을 받아 위치를 적분하고,
실제 센서가 측정할 법한 토픽들을 발행한다. 기존 `ekf.yaml`, URDF, AMCL 파라미터를
그대로 재사용한다.

| 노드 | 발행 토픽 | 메시지 타입 | frame_id |
|---|---|---|---|
| `fake_encoder_node` | `/odom` | `nav_msgs/Odometry` | `odom` → `base_footprint` |
| `fake_imu_node` | `/imu/data` | `sensor_msgs/Imu` | `imu_link` |
| `fake_lidar_node` | `/scan` | `sensor_msgs/LaserScan` | `laser_frame` |

## 설치

```bash
# src/wheelchair_robot/ 아래에 이 패키지 폴더를 둔 뒤:
cd ~/wheelchair_ws
colcon build --packages-select wheelchair_robot_fake --symlink-install
source install/setup.bash
```

## 3가지 실행 모드

### A) 위치 추정만, 가상 룸 (`fake_bringup`)

EKF만 돌아가고 lidar는 내장된 가상 직사각형 룸에 raycasting.

```bash
ros2 launch wheelchair_robot_fake fake_bringup.launch.py
```

### B) **기존 맵에 AMCL 위치추정** (`fake_localization`) ⭐

기존 `wheelchair_robot_world.yaml` 맵을 로딩하고 그 위에서 lidar가 raycasting하여 AMCL이 정상 동작.

```bash
ros2 launch wheelchair_robot_fake fake_localization.launch.py
```

특징:
- 시작 5초 후 `/initialpose` 자동 발행 → RViz 클릭 없이 AMCL이 (0,0)에서 수렴
- 별도 맵/시작 위치 지정 가능:
  ```bash
  ros2 launch wheelchair_robot_fake fake_localization.launch.py \
      map:=/path/to/other.yaml \
      initial_x:=1.0 initial_y:=0.5 initial_yaw:=1.5708
  ```

### C) Cartographer 매핑 (`fake_slam`)

가상 룸을 운전하면 `/map`이 실제로 그려진다.

```bash
ros2 launch wheelchair_robot_fake fake_slam.launch.py
```

## 운전

어떤 모드든 별도 터미널에서:

```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

## TF 트리

```
fake_localization:
  map → odom → base_footprint → base_link → imu_link, laser_frame
   ↑      ↑          ↑                              
   AMCL  EKF      URDF(고정)                        

fake_bringup / fake_slam:
  odom → base_footprint → base_link → ...
   ↑         ↑                                       
   EKF      EKF                                      
```

## 가상 룸 커스터마이즈 (모드 A·C)

```bash
ros2 run wheelchair_robot_fake fake_lidar_node \
  --ros-args \
  -p room_x_min:=-8.0 -p room_x_max:=8.0 \
  -p obstacles:="[3.0, 4.0, -1.0, 1.0,  -3.0, -2.0, 2.0, 4.0]"
```

`obstacles`는 `[x_min, x_max, y_min, y_max]` 4개씩 묶어 박스 추가.

## 맵 기반 lidar 동작 원리

`fake_lidar_node`에 `map_yaml` 파라미터를 지정하면:

1. nav2 map_server 호환 YAML + PGM 파일을 직접 파싱
2. 점유 격자(0~255 픽셀 → occupied/free) 생성
3. `(self.x, self.y)` 위치에서 360개 ray를 각 방향으로 0.5셀씩 ray-march
4. 점유 셀에 닿으면 그 거리를 반환 (노이즈 추가)

`initial_map_x/y/yaw`로 맵 안 어디서 시작할지 지정한다.
이 값은 AMCL이 `/initialpose`로 받는 값과 일치해야 한다 (`fake_localization`은 자동으로 일치시킴).

## 동작 원리 (전체)

세 노드 모두 동일한 `/cmd_vel`을 적분하므로 ground truth가 자연스럽게 일관된다.
각자 노이즈를 더해 측정값처럼 발행하므로 EKF가 융합하면서 실제 시스템과 유사한
드리프트/필터링 거동을 보여준다.

`ekf.yaml`이 실제로 읽는 필드:
- `/odom` → `twist.linear.x` (vx), `twist.angular.z` (vyaw)
- `/imu/data` → `angular_velocity.z` (vyaw)

나머지 필드들은 RViz 시각화/디버깅용.
