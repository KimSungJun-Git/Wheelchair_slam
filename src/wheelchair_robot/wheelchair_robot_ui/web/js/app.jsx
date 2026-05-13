// ─── 6. Main App Component (Router & ROS Connect) ─────────────────
function AppInner() {
  // 화면 스택: ['home'] -> ['home', 'search'] -> ['home', 'search', 'nav']
  const [stack, setStack] = React.useState(['home']);
  const [mode, setMode] = React.useState('manual');
  const [rosTopics, setRosTopics] = React.useState(null);
  const [rosConnected, setRosConnected] = React.useState(false);
  const [confirm, setConfirm] = React.useState(null); // {title, message, tone, onConfirm}

  const t = I18N['ko'];
  const act = useActivity();
  const actRef = React.useRef(act);
  actRef.current = act;
  const currentScreen = stack[stack.length - 1];

  const navTaskRef = React.useRef(null);
  const [activeDest, setActiveDest] = React.useState(null); // {key, label}
  const [arrival, setArrival] = React.useState(null); // {label} when arrived

  // 자율 주행 종료 토픽이 들어왔을 때 클로저 안에서 최신 activeDest를 보기 위한 ref
  const activeDestRef = React.useRef(null);
  React.useEffect(() => { activeDestRef.current = activeDest; }, [activeDest]);

  // 실시간 센서 데이터 (실제 ROS 토픽에서 갱신)
  // distances: 5방향 최소 거리(m). null이면 안전(>1m)으로 간주
  const [distances, setDistances] = React.useState({
    front: null, frontLeft: null, frontRight: null, left: null, right: null,
  });
  // 로봇 위치 (AMCL pose 또는 odom). 맵 표시는 꺼져 있지만 데이터는 유지 (디버깅용·향후 재활성화)
  const [robotWorld, setRobotWorld] = React.useState(null);
  // 맵 정보 (origin, resolution) - /map 토픽에서 자동 추출
  const [mapConfig, setMapConfig] = React.useState(DEFAULT_MAP_CONFIG);
  // 안전 알림 (전방 장애물·IMU 위험·위치 분실 시 트리거)
  // 'obstacle_too_close' | 'obstacle_cleared' | 'keepout_violation' | 'imu_emergency' | 'localization_lost'
  const [safetyAlert, setSafetyAlert] = React.useState(null);
  // 알림 화면에 표시할 사유 (safetyAlert는 100ms 안에 비워지므로 별도 보관)
  // 'obstacle_too_close' | 'keepout_violation' | 'imu_emergency' | 'localization_lost' | 'user_stop' | 'sos' | null
  const [alertReason, setAlertReason] = React.useState(null);

  // 5방향 거리값 누적 캐시 — 라이다·초음파 콜백이 각자 갱신
  const lidarSectorRef = React.useRef({ front: null, frontLeft: null, frontRight: null, left: null, right: null });
  const ultraRef = React.useRef({ front: null, left: null, right: null });

  // ⭐ 변경(2025): 도착 판정을 타이머 → /nav_status 토픽 기반으로 전환.
  //   기존 scheduleArrival(14초) 시뮬레이션 제거. mode_switch_node._dest_result_cb에서
  //   'arrived'/'cancelled'/'failed'를 발행하면 아래 navStatusSub가 받아서 처리.

  // safety_alert 자동 처리: 자율 주행 중 위험 신호 진입 시 알림 화면으로
  React.useEffect(() => {
    if (
      safetyAlert === 'obstacle_too_close' ||
      safetyAlert === 'imu_emergency' ||
      safetyAlert === 'localization_lost' ||
      safetyAlert === 'keepout_violation'
    ) {
      // 알림 화면 진입 사유 보존 (safetyAlert는 100ms 안에 null이 됨)
      setAlertReason(safetyAlert);
      // 자율 주행 화면일 때만 자동 전환 (다른 화면이면 로그만)
      if (currentScreen === 'nav') {
        setStack(prev => [...prev, 'alert']);
      }
    }
    // 알림 처리 후 비우기 (재발생 시 다시 트리거되도록)
    if (safetyAlert) {
      const tid = setTimeout(() => setSafetyAlert(null), 100);
      return () => clearTimeout(tid);
    }
  }, [safetyAlert]);

  // ===== 5방향 거리 통합 (라이다 + 초음파) =====
  // 라이다 sector별 최소거리 + 초음파 좌/중/우를 결합. 더 가까운 값을 사용.
  const recomputeDistances = () => {
    const merged = { ...lidarSectorRef.current };
    // 초음파는 정확하지만 정면(좁은 빔) 위주. 라이다보다 가까우면 우선.
    const u = ultraRef.current;
    const tighter = (a, b) => {
      if (a == null) return b;
      if (b == null) return a;
      return Math.min(a, b);
    };
    merged.front = tighter(merged.front, u.front);
    merged.left  = tighter(merged.left,  u.left);
    merged.right = tighter(merged.right, u.right);
    setDistances(merged);
  };

  React.useEffect(() => {
    const connectId = actRef.current.startActivity('로봇 연결 시도');
    const ros = new ROSLIB.Ros({ url: ROS_CONFIG.url });
    ros.on('connection', () => { setRosConnected(true); actRef.current.completeActivity(connectId, '연결 완료'); });
    ros.on('error', () => { setRosConnected(false); actRef.current.failActivity(connectId, 'UI 테스트 모드'); });
    ros.on('close', () => setRosConnected(false));

    // ===== Publisher =====
    const destPub = new ROSLIB.Topic({ ros, name: '/destination', messageType: 'std_msgs/String' });
    const modeSwitchPub = new ROSLIB.Topic({ ros, name: '/mode_switch', messageType: 'std_msgs/String' });
    const cmdVelPub = new ROSLIB.Topic({ ros, name: '/cmd_vel_teleop', messageType: 'geometry_msgs/Twist' });

    // ===== Subscriber =====
    const modeSub = new ROSLIB.Topic({ ros, name: '/robot_mode', messageType: 'std_msgs/String' });
    modeSub.subscribe((msg) => {
      setMode(msg.data);
      actRef.current.logEvent(`주행 모드 전환: ${msg.data === 'auto' ? '자율' : '수동'}`);
    });

    // --- 라이다 /scan: 5방향 sector 최소 거리 계산 ---
    const scanSub = new ROSLIB.Topic({
      ros, name: '/scan', messageType: 'sensor_msgs/LaserScan',
      throttle_rate: 100,  // 10Hz로 제한 (UI 부하 감소)
      queue_length: 1,
    });
    scanSub.subscribe((msg) => {
      const { angle_min, angle_increment, ranges, range_min, range_max } = msg;
      const sectors = { front: Infinity, frontLeft: Infinity, frontRight: Infinity, left: Infinity, right: Infinity };
      for (let i = 0; i < ranges.length; i++) {
        const r = ranges[i];
        if (!isFinite(r) || r < range_min || r > range_max) continue;
        const angDeg = (angle_min + i * angle_increment) * 180 / Math.PI;
        // [-180, 180]로 정규화
        let a = angDeg;
        while (a > 180) a -= 360;
        while (a < -180) a += 360;
        for (const sec of LIDAR_SECTORS) {
          if (a >= sec.from && a <= sec.to) {
            if (r < sectors[sec.key]) sectors[sec.key] = r;
            break;
          }
        }
      }
      // Infinity → null로 변환
      const out = {};
      for (const k in sectors) out[k] = isFinite(sectors[k]) ? sectors[k] : null;
      lidarSectorRef.current = out;
      recomputeDistances();
    });

    // --- 초음파 3개 ---
    const ultraFrontSub = new ROSLIB.Topic({ ros, name: '/ultrasonic/range', messageType: 'sensor_msgs/Range', throttle_rate: 100, queue_length: 1 });
    const ultraLeftSub  = new ROSLIB.Topic({ ros, name: '/ultrasonic/left',  messageType: 'sensor_msgs/Range', throttle_rate: 100, queue_length: 1 });
    const ultraRightSub = new ROSLIB.Topic({ ros, name: '/ultrasonic/right', messageType: 'sensor_msgs/Range', throttle_rate: 100, queue_length: 1 });
    ultraFrontSub.subscribe((msg) => { ultraRef.current.front = (msg.range > 0 && isFinite(msg.range)) ? msg.range : null; recomputeDistances(); });
    ultraLeftSub.subscribe((msg)  => { ultraRef.current.left  = (msg.range > 0 && isFinite(msg.range)) ? msg.range : null; recomputeDistances(); });
    ultraRightSub.subscribe((msg) => { ultraRef.current.right = (msg.range > 0 && isFinite(msg.range)) ? msg.range : null; recomputeDistances(); });

    // --- AMCL pose: 로봇 실제 위치 (Nav2 사용 시) ---
    // 휠체어 표시는 꺼져 있지만 데이터는 받아둠 (디버깅·향후 재활성화 대비)
    const amclSub = new ROSLIB.Topic({
      ros, name: '/amcl_pose', messageType: 'geometry_msgs/PoseWithCovarianceStamped',
      throttle_rate: 100, queue_length: 1,
    });
    amclSub.subscribe((msg) => {
      const p = msg.pose.pose;
      // quaternion → yaw
      const q = p.orientation;
      const yaw = Math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z));
      setRobotWorld({ x: p.position.x, y: p.position.y, yaw });
    });

    // --- 백업: /odom (AMCL이 없을 때) ---
    const odomSub = new ROSLIB.Topic({
      ros, name: '/odometry/filtered', messageType: 'nav_msgs/Odometry',
      throttle_rate: 200, queue_length: 1,
    });
    odomSub.subscribe((msg) => {
      // AMCL이 한 번이라도 와있으면 odom으로 덮어쓰지 않음
      // (AMCL이 더 정확한 map 좌표계)
      setRobotWorld(prev => {
        if (prev) return prev;  // AMCL이 있으면 유지
        const p = msg.pose.pose;
        const q = p.orientation;
        const yaw = Math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z));
        return { x: p.position.x, y: p.position.y, yaw };
      });
    });

    // --- /map: origin/resolution 자동 추출 (TRANSIENT_LOCAL latched topic) ---
    // 한 번 받으면 MAP_CONFIG를 자동 갱신 → 사용자가 yaml 안 봐도 됨
    const mapSub = new ROSLIB.Topic({
      ros, name: '/map', messageType: 'nav_msgs/OccupancyGrid',
      // latched 토픽이라 구독 즉시 한 번 발행됨
      queue_length: 1,
    });
    mapSub.subscribe((msg) => {
      const info = msg.info;
      // 맵 전체 픽셀 너비를 SVG 너비에 맞추는 pixels_per_meter 자동 계산
      const mapWidthMeters = info.width * info.resolution;
      const mapHeightMeters = info.height * info.resolution;
      // 가로/세로 중 큰 쪽이 SVG에 꽉 차도록
      const ppm = Math.min(
        DEFAULT_MAP_CONFIG.svg_width / mapWidthMeters,
        DEFAULT_MAP_CONFIG.svg_height / mapHeightMeters
      );
      setMapConfig({
        ...DEFAULT_MAP_CONFIG,
        origin_x: info.origin.position.x,
        origin_y: info.origin.position.y,
        pixels_per_meter: ppm,
      });
      actRef.current.logEvent(
        `맵 정보 자동 적용: ${info.width}×${info.height}px, ${info.resolution.toFixed(3)}m/px`
      );
      // 한 번 받으면 충분, 구독 해제
      mapSub.unsubscribe();
    });

    // --- 안전 알림 (safety_stop_node /safety_alert) ---
    const safetyAlertSub = new ROSLIB.Topic({ ros, name: '/safety_alert', messageType: 'std_msgs/String' });
    safetyAlertSub.subscribe((msg) => {
      setSafetyAlert(msg.data);
      if (msg.data === 'obstacle_too_close') {
        actRef.current.logEvent('⚠️ 전방 장애물 감지 - 자율 주행 중단');
      } else if (msg.data === 'obstacle_cleared') {
        actRef.current.logEvent('✅ 장애물 해소');
      } else if (msg.data === 'keepout_violation') {
        actRef.current.logEvent('🚫 금지구역 진입');
      }
    });

    // ============================================================
    //  ⭐ 새로 추가된 알림·상태 토픽 (다른 패키지의 발행자와 매칭)
    // ============================================================

    // --- /nav_status: 자율 주행 종료 알림 (mode_switch_node가 발행하도록 패치 필요) ---
    //   'arrived' | 'cancelled' | 'failed'
    //   mode_switch_node._dest_result_cb / _home_result_cb / cancel_nav 에서 발행
    const navStatusSub = new ROSLIB.Topic({ ros, name: '/nav_status', messageType: 'std_msgs/String' });
    navStatusSub.subscribe((msg) => {
      const status = msg.data;
      if (status === 'arrived') {
        if (navTaskRef.current != null) {
          actRef.current.completeActivity(navTaskRef.current, '목적지 도착');
          navTaskRef.current = null;
        }
        // 클로저 이슈 방지: ref로 최신 activeDest 읽기
        const dest = activeDestRef.current;
        setArrival({ label: dest?.label || '목적지' });
      } else if (status === 'failed') {
        if (navTaskRef.current != null) {
          actRef.current.failActivity(navTaskRef.current, '주행 실패');
          navTaskRef.current = null;
        }
        actRef.current.logEvent('❌ 자율 주행 실패');
      } else if (status === 'cancelled') {
        if (navTaskRef.current != null) {
          actRef.current.cancelActivity(navTaskRef.current, '주행 취소');
          navTaskRef.current = null;
        }
      }
    });

    // --- /sensor_health: 센서 헬스 JSON ({ lidar: 'ok'|'lost(N.Ns)'|'never', ... }) ---
    const lastHealth = {};  // 직전 상태 캐시 — 변경 시에만 로그
    const sensorHealthSub = new ROSLIB.Topic({ ros, name: '/sensor_health', messageType: 'std_msgs/String' });
    sensorHealthSub.subscribe((msg) => {
      try {
        const health = JSON.parse(msg.data);
        for (const [k, v] of Object.entries(health)) {
          if (lastHealth[k] === v) continue;
          lastHealth[k] = v;
          const name = SENSOR_LABELS[k] || k;
          if (v === 'ok') actRef.current.logEvent(`✅ ${name} 센서 정상`);
          else if (v === 'never') actRef.current.logEvent(`🔌 ${name} 센서 응답 없음`);
          else if (typeof v === 'string' && v.startsWith('lost')) actRef.current.logEvent(`🔌 ${name} 센서 끊김 (${v})`);
        }
      } catch (e) { /* JSON 파싱 실패 무시 */ }
    });

    // --- /emergency_stop/imu: IMU 비상 (imu_safety_node 발행, Bool) ---
    const imuEmergencySub = new ROSLIB.Topic({ ros, name: '/emergency_stop/imu', messageType: 'std_msgs/Bool' });
    let lastImuEmergency = false;
    imuEmergencySub.subscribe((msg) => {
      if (msg.data === lastImuEmergency) return;
      lastImuEmergency = msg.data;
      if (msg.data) {
        actRef.current.logEvent('🚨 IMU 비상 (기울기/충격 감지)');
        setSafetyAlert('imu_emergency');
      } else {
        actRef.current.logEvent('✅ IMU 정상 복귀');
      }
    });

    // --- /emergency_stop/localization: 위치 추적 비상 (localization_monitor_node 발행, Bool) ---
    const locEmergencySub = new ROSLIB.Topic({ ros, name: '/emergency_stop/localization', messageType: 'std_msgs/Bool' });
    let lastLocEmergency = false;
    locEmergencySub.subscribe((msg) => {
      if (msg.data === lastLocEmergency) return;
      lastLocEmergency = msg.data;
      if (msg.data) {
        actRef.current.logEvent('🚨 위치 추적 분실 - 글로벌 재인식 시도');
        setSafetyAlert('localization_lost');
      } else {
        actRef.current.logEvent('✅ 위치 추적 복구');
      }
    });

    // --- /localization_status: 위치 상태 (localization_monitor_node, ok/uncertain/lost) ---
    let lastLocStatus = null;
    const locStatusSub = new ROSLIB.Topic({ ros, name: '/localization_status', messageType: 'std_msgs/String' });
    locStatusSub.subscribe((msg) => {
      if (lastLocStatus === msg.data) return;
      lastLocStatus = msg.data;
      if (msg.data === 'uncertain') actRef.current.logEvent('⚠️ 위치 추적 불확실');
      else if (msg.data === 'lost') actRef.current.logEvent('🚨 위치 추적 분실');
      else if (msg.data === 'ok') actRef.current.logEvent('✅ 위치 추적 정상');
    });

    // --- /sos_trigger: SOS 이벤트 (imu_safety_node + localization_monitor_node 발행) ---
    //   예: 'imu_기울기:roll=...' / 'localization_lost' / mode_switch_node가 받아서 로그 기록
    const sosTriggerSub = new ROSLIB.Topic({ ros, name: '/sos_trigger', messageType: 'std_msgs/String' });
    sosTriggerSub.subscribe((msg) => {
      actRef.current.logEvent(`🆘 SOS: ${msg.data}`);
    });

    // --- /avoidance_direction: 회피 방향 권장 (safety_stop_node) ---
    const avoidLabels = { left: '왼쪽으로 우회', right: '오른쪽으로 우회', blocked: '양쪽 막힘 - 회피 불가' };
    const avoidSub = new ROSLIB.Topic({ ros, name: '/avoidance_direction', messageType: 'std_msgs/String' });
    avoidSub.subscribe((msg) => {
      actRef.current.logEvent(`↪️ ${avoidLabels[msg.data] || msg.data}`);
    });

    // --- /safety_action: cmd_vel 게이트 결과 (JSON {source, action, reason}) ---
    //   action: 'allowed'(통과) | 'modified'(속도 제한) | 'blocked'(차단)
    //   'allowed'는 너무 자주 발행되니 무시. 변화만 로그.
    let lastAction = null;
    const safetyActionSub = new ROSLIB.Topic({ ros, name: '/safety_action', messageType: 'std_msgs/String' });
    safetyActionSub.subscribe((msg) => {
      try {
        const a = JSON.parse(msg.data);
        const key = `${a.action}:${a.reason || ''}`;
        if (lastAction === key) return;
        lastAction = key;
        if (a.action === 'blocked') actRef.current.logEvent(`🛑 명령 차단 (${a.reason || '비상'})`);
        else if (a.action === 'modified') actRef.current.logEvent(`✂️ 속도 제한 (${a.reason || '장애물'})`);
      } catch (e) { /* JSON 파싱 실패 무시 */ }
    });

    // --- /current_zone: 현재 구역 상태 텍스트 (safety_stop_node) ---
    //   '비상정지...' / '위험구역(정지)...' / '일반구역...'
    let lastZoneType = null;
    const zoneSub = new ROSLIB.Topic({ ros, name: '/current_zone', messageType: 'std_msgs/String' });
    zoneSub.subscribe((msg) => {
      let zoneType = '일반';
      if (msg.data.startsWith('비상정지')) zoneType = '비상';
      else if (msg.data.startsWith('위험구역')) zoneType = '위험';
      if (lastZoneType === zoneType) return;
      lastZoneType = zoneType;
      if (zoneType === '비상') actRef.current.logEvent('🛑 비상정지 구역 진입');
      else if (zoneType === '위험') actRef.current.logEvent('⚠️ 위험구역 진입');
      else actRef.current.logEvent('✅ 일반구역 복귀');
    });

    setRosTopics({ destPub, modeSwitchPub, cmdVelPub });
    return () => {
      modeSub.unsubscribe();
      scanSub.unsubscribe();
      ultraFrontSub.unsubscribe();
      ultraLeftSub.unsubscribe();
      ultraRightSub.unsubscribe();
      amclSub.unsubscribe();
      odomSub.unsubscribe();
      safetyAlertSub.unsubscribe();
      // 새로 추가된 구독들
      navStatusSub.unsubscribe();
      sensorHealthSub.unsubscribe();
      imuEmergencySub.unsubscribe();
      locEmergencySub.unsubscribe();
      locStatusSub.unsubscribe();
      sosTriggerSub.unsubscribe();
      avoidSub.unsubscribe();
      safetyActionSub.unsubscribe();
      zoneSub.unsubscribe();
      ros.close();
    };
  }, []);

  // 화면 전환 helpers
  const pushScreen = (s) => setStack(prev => [...prev, s]);
  const popScreen = () => setStack(prev => prev.length > 1 ? prev.slice(0, -1) : prev);
  const goHomeAll = () => {
    if (navTaskRef.current != null) {
      act.cancelActivity(navTaskRef.current, '홈으로 복귀');
      navTaskRef.current = null;
    }
    setActiveDest(null);
    setStack(['home']);
  };

  const goSearch = () => pushScreen('search');

  // 목적지 / 대기소 확인 다이얼로그
  const askStartNavigation = (destName) => {
    const label = DEST_LABELS[destName] || destName;
    setConfirm({
      title: `${label}(으)로 이동할까요?`,
      message: '확인을 누르면 휠체어가 즉시 자율 주행을 시작합니다.',
      confirmText: '네, 이동합니다',
      cancelText: '아니오',
      tone: 'primary',
      onConfirm: () => {
        setConfirm(null);
        doStartNavigation(destName);
      },
    });
  };
  const askGoHomeBase = () => {
    setConfirm({
      title: '대기소로 자동 귀환할까요?',
      message: '확인을 누르면 휠체어가 대기소까지 자율 주행으로 돌아갑니다.',
      confirmText: '네, 귀환합니다',
      cancelText: '아니오',
      tone: 'primary',
      onConfirm: () => {
        setConfirm(null);
        doStartNavigation('home');
      },
    });
  };

// 일과(이용) 종료 + AI 분석 트리거
  const askEndSession = () => {
    setConfirm({
      title: '오늘 이용을 종료할까요?',
      message: '주행 기록을 AI가 분석합니다 (1~2분 소요).',
      confirmText: '네, 종료합니다',
      cancelText: '아니오',
      tone: 'primary',
      onConfirm: async () => {
        setConfirm(null);
        actRef.current.logEvent('🛑 이용 종료 요청');
        try {
          const res = await fetch('http://localhost:8090/api/analyze_session', {
            method: 'POST',
          });
          const data = await res.json();
          if (data.ok) {
            actRef.current.logEvent('🤖 AI 분석 시작됨');
          } else {
            actRef.current.logEvent('⚠️ 분석 요청 실패');
          }
        } catch (e) {
          actRef.current.logEvent('⚠️ 서버 연결 실패 — 관제 서버 확인');
        }
      },
    });
  };

  // ⭐ 변경(2025): scheduleArrival 호출 제거. 도착은 /nav_status 토픽으로만 판정.
  const doStartNavigation = (destName) => {
    if (navTaskRef.current != null) act.cancelActivity(navTaskRef.current, '새 목적지 지정');
    const label = DEST_LABELS[destName] || destName;
    const id = act.startActivity(`자율 주행: ${label}`);
    navTaskRef.current = id;
    setActiveDest({ key: destName, label });
    setMode('auto');
    if (rosTopics) rosTopics.destPub.publish(new ROSLIB.Message({ data: destName }));
    pushScreen('nav');
  };

  const doGoHomeBase = () => {
    if (navTaskRef.current != null) act.cancelActivity(navTaskRef.current, '대기소 귀환으로 변경');
    const id = act.startActivity('대기소 자동 귀환');
    navTaskRef.current = id;
    setActiveDest({ key: 'home_base', label: '대기소' });
    setMode('auto');
    if (rosTopics) rosTopics.modeSwitchPub.publish(new ROSLIB.Message({ data: 'home' }));
    pushScreen('nav');
  };

  // 네비게이션 화면에서 정지 (긴급 아님)
  const stopNavigation = () => {
    if (navTaskRef.current != null) {
      act.cancelActivity(navTaskRef.current, '사용자 정지');
      navTaskRef.current = null;
    }
    act.logEvent('주행 정지');
    if (rosTopics) rosTopics.cmdVelPub.publish(new ROSLIB.Message({ linear: {x:0, y:0, z:0}, angular: {x:0, y:0, z:0} }));
    setAlertReason('user_stop');
    pushScreen('alert');
  };

  // 홈 화면의 SOS = 진짜 긴급 정지
  const triggerSOS = () => {
    setConfirm({
      title: 'SOS 호출을 보낼까요?',
      message: '보호자와 관제실에 즉시 알림이 전달됩니다.',
      confirmText: '네, 호출합니다',
      cancelText: '아니오',
      tone: 'danger',
      onConfirm: () => {
        setConfirm(null);
        if (navTaskRef.current != null) {
          act.cancelActivity(navTaskRef.current, '긴급 정지');
          navTaskRef.current = null;
        }
        act.cancelAllActive('긴급 정지');
        act.logEvent('🛑 SOS 긴급 호출');
        if (rosTopics) rosTopics.cmdVelPub.publish(new ROSLIB.Message({ linear: {x:0, y:0, z:0}, angular: {x:0, y:0, z:0} }));
        setAlertReason('sos');
        pushScreen('alert');
      },
    });
  };

  // ⭐ 변경(2025): scheduleArrival 호출 제거. 재개해도 도착은 /nav_status가 알려줌.
  const resumeNav = () => {
    setAlertReason(null);
    const id = act.startActivity('자율 주행 재개 (우회 경로)');
    navTaskRef.current = id;
    setMode('auto');
    popScreen(); // alert에서 한 단계 뒤로 (이전이 nav면 nav로)
    if (currentScreen === 'alert' && stack[stack.length - 2] !== 'nav') pushScreen('nav');
  };

  // NavScreen에서 뒤로/홈 누르면 → 주행 취소 확인
  const askCancelNav = (target) => () => {
    // 진행 중인 자율 주행도, 저장된 목적지도 없으면 굳이 물어볼 것 없이 바로 동작
    if (navTaskRef.current == null && !activeDest) {
      if (target === 'home') setStack(['home']);
      else popScreen();
      return;
    }
    setConfirm({
      title: target === 'home' ? '홈으로 돌아갈까요?' : '주행을 취소할까요?',
      message: target === 'home' ? '진행 중인 자율 주행이 취소되고 홈 화면으로 이동합니다.' : '진행 중인 자율 주행이 취소됩니다.',
      confirmText: '네, 취소합니다',
      cancelText: '계속 주행',
      tone: 'warn',
      onConfirm: () => {
        setConfirm(null);
        if (navTaskRef.current != null) {
          act.cancelActivity(navTaskRef.current, target === 'home' ? '홈으로 복귀' : '사용자 취소');
          navTaskRef.current = null;
        }
        setActiveDest(null);
        if (rosTopics) rosTopics.cmdVelPub.publish(new ROSLIB.Message({ linear: {x:0, y:0, z:0}, angular: {x:0, y:0, z:0} }));
        if (target === 'home') setStack(['home']);
        else popScreen();
      },
    });
  };

  // NavScreen에서 수동 버튼 → 조이스틱 화면으로
  const navToManual = () => {
    if (navTaskRef.current != null) {
      act.cancelActivity(navTaskRef.current, '수동 모드 전환');
      navTaskRef.current = null;
    }
    setMode('manual');
    act.logEvent('수동 주행 모드 진입');
    if (rosTopics) rosTopics.modeSwitchPub.publish(new ROSLIB.Message({ data: 'm' }));
    pushScreen('joystick');
  };

  // NavScreen에서 자율 버튼 → 이미 자율이지만 명시적으로 표시
  const navToAuto = () => {
    if (mode !== 'auto') {
      setMode('auto');
      act.logEvent('자율 주행 모드 진입');
      if (rosTopics) rosTopics.modeSwitchPub.publish(new ROSLIB.Message({ data: 'a' }));
    }
  };

  // 조이스틱 화면 → 자율 모드 복귀 버튼: 기존 목적지가 남아 있으면 같은 경로로 다시 자율 주행 시작
  // ⭐ 변경(2025): scheduleArrival 호출 제거. 도착은 /nav_status 토픽으로만 판정.
  const joystickToAuto = () => {
    setMode('auto');
    act.logEvent('자율 모드로 복귀');
    if (rosTopics) rosTopics.modeSwitchPub.publish(new ROSLIB.Message({ data: 'a' }));
    // 기존 목적지가 있으면 그 경로 그대로 자율 주행 재개
    if (activeDest) {
      if (navTaskRef.current != null) act.cancelActivity(navTaskRef.current, '재개');
      const id = act.startActivity(`자율 주행 재개: ${activeDest.label}`);
      navTaskRef.current = id;
      if (rosTopics) {
        if (activeDest.key === 'home_base') rosTopics.modeSwitchPub.publish(new ROSLIB.Message({ data: 'home' }));
        else rosTopics.destPub.publish(new ROSLIB.Message({ data: activeDest.key }));
      }
      // 자율 주행 진행 중에는 nav 화면으로 보장: stack에서 joystick 제거 후 nav가 맨 위가 되게
      setStack(prev => {
        const withoutJoystick = prev.filter(s => s !== 'joystick');
        if (withoutJoystick[withoutJoystick.length - 1] === 'nav') return withoutJoystick;
        return [...withoutJoystick, 'nav'];
      });
    } else {
      // 목적지 없으면 단순 뒤로
      popScreen();
    }
  };

  // 어디서든 수동조작으로 가는 글로벌 핸들러: 진행 중 자율 주행 작업은 취소하지만 activeDest는 유지
  const goToManualAnywhere = () => {
    if (navTaskRef.current != null) {
      act.cancelActivity(navTaskRef.current, '수동 조작 전환');
      navTaskRef.current = null;
    }
    setMode('manual');
    act.logEvent('수동 주행 모드 진입');
    if (rosTopics) rosTopics.modeSwitchPub.publish(new ROSLIB.Message({ data: 'm' }));
    // 이미 joystick이면 그대로, 아니면 push
    setStack(prev => prev[prev.length - 1] === 'joystick' ? prev : [...prev, 'joystick']);
  };

  let screen;
  switch (currentScreen) {
    case 'home':     screen = <HomeScreen t={t} onSearch={goSearch} onGoHome={askGoHomeBase} onSOS={triggerSOS} onEndSession={askEndSession} />; break;
    case 'search':   screen = <SearchScreen t={t} onBack={popScreen} onGoHome={goHomeAll} onStartRoute={askStartNavigation} />; break;
    case 'nav':      screen = <NavScreen t={t} mode={mode} distances={distances} robotWorld={robotWorld} mapConfig={mapConfig} onBack={askCancelNav('back')} onGoHome={askCancelNav('home')} onStop={stopNavigation} onManual={navToManual} onAuto={navToAuto} />; break;
    case 'alert':    screen = <AlertScreen t={t} alertReason={alertReason} robotWorld={robotWorld} mapConfig={mapConfig} onResume={resumeNav} onManual={navToManual} onBack={askCancelNav('back')} onGoHome={askCancelNav('home')} onGoHomeBase={askGoHomeBase} />; break;
    case 'joystick': screen = <JoystickScreen t={t} robotWorld={robotWorld} mapConfig={mapConfig} onBack={askCancelNav('back')} onGoHome={askCancelNav('home')} setMode={joystickToAuto} cmdVelPub={rosTopics?.cmdVelPub} />; break;
    default: screen = <HomeScreen t={t} onSearch={goSearch} onGoHome={askGoHomeBase} onSOS={triggerSOS} onEndSession={askEndSession} />;
  
  }

  const hasActiveNav = act.activities.some(a => a.status === 'active' && (a.label.startsWith('자율 주행') || a.label.includes('대기소 자동 귀환')));
  const showOverlays = currentScreen !== 'home' && currentScreen !== 'alert';

  return (
    <div style={{ position: 'relative' }}>
      {screen}
      {/* ROS 연결 끊김 배너 - 의료기기 안전 표준상 통신 단절은 명시적으로 표시 */}
      {!rosConnected && (
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, zIndex: 80,
          padding: '6px 16px',
          background: 'rgba(229, 72, 77, 0.95)',
          color: '#fff',
          fontSize: 12, fontWeight: 800, fontFamily: TOKENS.font.sans,
          textAlign: 'center',
          letterSpacing: 0.5,
        }}>
          ⚠️ 로봇 통신 끊김 — 화면 정보가 실시간이 아닐 수 있습니다
        </div>
      )}
      {/* 글로벌 정지 버튼: 화면 하단 중앙(우측 상단의 보호자 pill·하단의 SOS와 겹치지 않도록 nav 화면 외엔 표시 안 함) */}
      {hasActiveNav && showOverlays && currentScreen !== 'nav' && (
        <button
          onClick={(e) => { e.stopPropagation(); stopNavigation(); }}
          style={{
            position: 'absolute', top: 50, right: 16, zIndex: 70,
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '12px 20px', borderRadius: 999,
            background: TOKENS.color.danger, color: '#fff',
            border: '2px solid rgba(255,255,255,0.9)',
            fontSize: 16, fontWeight: 800, fontFamily: 'inherit',
            cursor: 'pointer',
            boxShadow: '0 8px 24px rgba(229,72,77,0.4)',
          }}
          title="현재 주행 정지"
        >
          <Icon name="stop" size={18} stroke={2.5} /> 정지
        </button>
      )}
      {/* 글로벌 수동조작 버튼: 자체 수동 진입점이 없는 home·search 화면에서만 표시.
          - nav: 하단 중앙 토글에 [수동] 버튼이 있음 → 중복 방지
          - alert: 권장 조치 카드에 [수동 모드 전환] BigButton이 있음 → 중복 방지
          - joystick: 이미 수동 화면이라 의미 없음
          - home: SOS가 좌측 하단에 있으므로 우측 하단에 배치
          - search: 좌측 하단이 비어 있어 좌측 하단에 배치 */}
      {(currentScreen === 'home' || currentScreen === 'search') && (
        <button
          onClick={(e) => { e.stopPropagation(); goToManualAnywhere(); }}
          style={{
            position: 'absolute',
            bottom: 24,
            ...(currentScreen === 'home' ? { right: 24 } : { left: 24 }),
            zIndex: 70,
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '14px 22px', borderRadius: 999,
            background: '#fff', color: TOKENS.color.primaryDark,
            border: `2px solid ${TOKENS.color.primaryDark}`,
            fontSize: 16, fontWeight: 800, fontFamily: 'inherit',
            cursor: 'pointer',
            boxShadow: '0 8px 24px rgba(0,47,108,0.18)',
          }}
          title="수동 조작으로 전환"
        >
          <Icon name="play" size={18} stroke={2.5} /> 수동조작
        </button>
      )}
      <ConfirmDialog
        open={!!confirm}
        title={confirm?.title}
        message={confirm?.message}
        confirmText={confirm?.confirmText}
        cancelText={confirm?.cancelText}
        tone={confirm?.tone}
        onConfirm={confirm?.onConfirm}
        onCancel={() => setConfirm(null)}
      />
      <ArrivalModal
        open={!!arrival}
        label={arrival?.label}
        onDismiss={() => {
          setArrival(null);
          setActiveDest(null);
          setStack(['home']);
        }}
      />
      {currentScreen !== 'home' && <ActivityPanel />}
    </div>
  );
}

function App() {
  return <ActivityProvider><AppInner /></ActivityProvider>;
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);