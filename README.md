# Wheelchair Robot — Autonomous Wheelchair System

A ROS2-based indoor autonomous wheelchair platform. The rider picks a destination from a touch UI, the wheelchair localizes itself and navigates around obstacles on its own, and caregivers/operators monitor live status and read AI-generated post-session reports from a separate admin dashboard.

---

## 1. What the system does

### Autonomous navigation
The rider taps a destination (patient room, ER, standby area, etc.). The wheelchair plans a route on a pre-built indoor map, follows it while avoiding dynamic obstacles, and reroutes on the fly. Keepout zones (stairs, restricted areas) are automatically excluded from the plan.

### Multi-layer safety
Four hazards are monitored simultaneously while driving:
- Tilt and impact on the wheelchair body
Proximity in three directions (front / left / right) with graded color
- Localization loss (with a second-line monitor node for confirmation)
- Entry into keepout zones

When any hazard fires, the wheelchair stops immediately, and the event type, reason, timestamp, and coordinates are logged together.

### Manual / autonomous switching · SOS
The rider can switch out of autonomous mode and drive manually at any time, then switch back. An SOS button on the rider screen and a remote-stop button on the admin dashboard both cut autonomous driving instantly.

### Rider screen
A live SLAM map shows the wheelchair's pose, heading, and trail, plus five-directional obstacle distances. The screen auto-switches between driving / arrival / alert / SOS contexts. A side "system activity" panel tracks every action (connect, route, stop) as in-progress / done / failed, and the rider can cancel all active actions with one tap.

### Automatic logging + AI analysis report
Every safety event is automatically recorded (with duplicate-message removal and a 5-second deduplication window). When a session ends — or when the operator clicks "End session and run AI analysis" — a local LLM reads that session's logs and writes a Korean-language report containing:
- Movement-pattern summary
- Repeated-intervention zones
- Discomfort zones for the rider
- Improvement suggestions
- Overall stability assessment (high / medium / low)
- **AI confidence score** (a banner warns when it falls below 50%)

Every finding is required to cite actual statistics, not speculation.

### Admin dashboard
Three pages for caregivers and operators:
- **Overview** — event statistics by time window / hour / weekday / reason, plus a SLAM coordinate heatmap
- **AI Reports** — Session cards, dual-tab rendered Markdown reports (Basic Summary vs. R1 Deep Diagnosis), confidence bar, and guardian-share dialog. The operator can trigger a deep analysis of the latest session directly from the UI.- **Live Monitor** — current pose, recent trail, last 30 events streamed in, with a one-click remote stop

---

## 2. System composition

### Hardware / sensor layer (Raspberry Pi)
- **IMU** — `stella_ahrs` (orientation, acceleration)
- **2D LiDAR** — `ydlidar_ros2_driver`
- **Motor + wheel odometry** — `stella_md` (`/odom`, `cmd_vel`)
- **Ultrasonic ×3** — front / left / right via `uul.py`

### SLAM & navigation (remote PC)
| Package | Role |
|---|---|
| `wheelchair_robot_description` | URDF model, TF tree, RViz display |
| `wheelchair_robot_cartographer` | Cartographer SLAM, occupancy grid |
| `wheelchair_robot_navigation2` | Nav2 stack + Keepout Filter |
| `robot_localization` (EKF) | Fuses `/odom` + `/imu/data` → `/odometry/filtered` |

### Control & safety (`wheelchair_robot_control`)
- `mode_switch_node` — autonomous/manual switching and destination-result callbacks
- `imu_safety_node` — tilt and impact detection
- `localization_monitor_node` — second-line localization watchdog
- `safety_stop_node`, `main_controller` — stop logic and integrated control

### Teleop (`wheelchair_robot_teleop`)
Keyboard teleop, remapped to `cmd_vel_teleop` so it only takes effect in manual mode.

### AI pipeline (`wheelchair_robot_ai`)
- `log_collector_node` — writes every safety event to `~/wheelchair_ws/driving_data/*.json` as JSONL
- `agent_analyzer` — LangGraph + Ollama (Qwen2.5:7b) workflow producing the Korean report

### Web UI — rider (`wheelchair_robot_ui`)
- React + rosbridge_websocket (`ws://localhost:9090`)
- LiDAR sectors fused with ultrasonic readings into a single five-direction minimum-distance vector
- Screen flow: home → destination select → navigation → arrival / alert / SOS

### Web UI — admin dashboard (`wheelchair_admin_dashboard`)
- FastAPI backend (port 8090) + static React frontend
- Endpoints: `/api/health`, `/api/reports`, `/api/report/{id}`, `/api/events`, `/api/live`, `/api/analyze_session`, `/api/deep_analyze`
- Falls back to a sample-data preview mode automatically if the backend is down

### Integrated bringup
A single launch file (`wheelchair_robot_ui/launch/web_ui.launch.py`) starts rosbridge_websocket, the static web server (port 8000), the admin backend (port 8090), and `log_collector_node` together.

---

## 3. How to run

### Raspberry Pi (sensor layer)
```bash
# IMU
ros2 launch stella_ahrs stella_ahrs_launch.py
# LiDAR
ros2 launch ydlidar_ros2_driver ydlidar_launch.py
# Odometry
ros2 launch stella_md stella_md_launch.py
# Ultrasonic
cd ~/colcon_ws/src/ && python3 uul.py
```

### Remote PC (navigation + control + AI)
```bash
# Terminal 1: sensors + EKF + SLAM
ros2 launch wheelchair_robot_cartographer bringup_cartographer.launch.py

# Terminal 2: Nav2
ros2 launch wheelchair_robot_navigation2 navigation2.launch.py

# Terminal 3: autonomous/manual mode switch
ros2 run wheelchair_robot_control mode_switch_node

# Terminal 4: keyboard teleop (manual mode)
ros2 run wheelchair_robot_teleop teleop_keyboard --ros-args -r cmd_vel:=/cmd_vel_teleop

# Terminal 5: wheelchair tilt watchdog
ros2 run wheelchair_robot_control imu_safety_node

# Terminal 6: secondary localization watchdog
ros2 run wheelchair_robot_control localization_monitor_node

# Terminal 7: AI analysis pipeline
./run_all.sh
```

### Web UI
```bash
ros2 launch wheelchair_robot_ui web_ui.launch.py
```

| Screen | URL |
|---|---|
| Rider UI | http://localhost:8000/Wheelchair_SLAM_UI.html |
| Admin Dashboard | http://localhost:8000/admin/Dashboard.html |

---

## 4. Data flow

```
[Sensors] → ROS2 topics → [SLAM / Nav2 / safety nodes] → /safety_action, /sos_trigger
                                                           ↓
                                                  [log_collector_node]
                                                           ↓
                                       ~/wheelchair_ws/driving_data/*.json
                                                    ↙               ↘
                                       [agent_analyzer]        [FastAPI backend]
                                              ↓                        ↓
                                        *_report.md          Admin Dashboard (HTTP)

[Rider UI] ←─ rosbridge_websocket (9090) ─→ [All ROS2 topics]
```

---

## 5. Roadmap / development notes

- `/api/live` currently polls the last line of the most recent JSON file. Switching to SSE / WebSocket push is planned for true real-time.
- The remote-stop button is fully wired in the UI; the topic publish path goes through rosbridge or an `rclpy` node embedded in `server.py`.
- The guardian-share dialog is built; SMTP / KakaoTalk notification adapters will be added under `POST /api/share/{report_id}`.
- For demos, `fake_alerts.sh` publishes six representative alert scenarios at 15-second intervals.

---

## 6. Package tree

```
wheelchair_robot/
├── wheelchair_robot_description/     # URDF, TF, RViz
├── wheelchair_robot_cartographer/    # SLAM
├── wheelchair_robot_navigation2/     # Nav2 + Keepout Filter
├── wheelchair_robot_control/         # mode switching, safety nodes, EKF
├── wheelchair_robot_teleop/          # keyboard manual driving
├── wheelchair_robot_ai/              # log collection + LLM analysis
├── wheelchair_robot_ui/              # rider React UI + rosbridge launch
└── wheelchair_admin_dashboard/       # admin FastAPI + React dashboard
```

---

**Maintainer** — kim (ksjun100848@naver.com)
**License** — Apache 2.0