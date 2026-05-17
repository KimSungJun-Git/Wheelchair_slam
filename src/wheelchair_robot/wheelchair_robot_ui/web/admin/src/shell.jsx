
const { useState, useEffect } = React;

// 전역 다국어 사전
window.dict = {
  ko: {
    nav_admin: "관리",
    api_connected: "API 연결됨",
    sample_mode: "샘플 모드",
    session: "세션",
    server_not_running: "server.py 미실행",
    logout: "로그아웃",
    backend_connected: "백엔드 연결됨",
    admin: "관리자",
    facility_team: "시설관리팀",
    overview_daily_events: "일자별 이벤트",
    overview_daily_sub: "위험(빨강) · 주의(주황) 스택",
    overview_detected_causes: "감지된 이상 원인",
    overview_causes_sub: "reason 키 별 집계",
    overview_accident_locations: "사고 발생 위치 히트맵",
    overview_locations_sub: "SLAM 좌표(pose.x / pose.y) — 점 크기는 빈도",
    btn_deep_analyze: "최신 로그 R1 깊은 진단",
    deep_error_default: "알 수 없는 에러가 발생했습니다.",
    deep_starting: "분석을 준비하고 있습니다...",
    deep_running: "AI 분석 중...",
    deep_done: "분석 완료!",
    deep_failed: "분석 실패:",
    reports_conf_unknown: "신뢰도 알 수 없음",
    overview_conf_good: "양호",
    overview_conf_ok: "보통",
    overview_conf_low: "낮음",
    reports_level_critical: "위험",
    reports_level_warning: "주의",
    reports_level_normal: "정상",
    reports_search: "보고서 검색...",
    reports_filter_all: "전체",
    reports_filter_critical: "위험만",
    reports_filter_warning: "주의만",
    reports_conf_gte: "신뢰도",
    reports_shown_count: "개 표시됨",
    reports_empty: "조건에 맞는 보고서가 없습니다.",
    reports_loading: "보고서를 불러오는 중...",
    reports_msg_count: "개 메시지",
    reports_raw_log: "원본 로그",
    reports_share: "공유",
    reports_pdf: "PDF 저장",
    reports_ai_confidence: "AI 분석 신뢰도",
    reports_kpi_estop: "비상정지",
    reports_kpi_sos: "SOS",
    reports_kpi_cmd: "명령수정",
    reports_kpi_normal: "정상주행",
    reports_low_conf_title: "추가 데이터 수집 필요",
    reports_low_conf_sub: "AI 신뢰도가 낮습니다.",
    reports_raw_lines: "줄",
    reports_raw_truncated: " (생략됨)",
    share_modal_title: "보고서 공유",
    share_modal_body: "보호자 및 담당자에게 전송합니다.",
    share_modal_attach_log: "원본 로그 첨부",
    share_modal_attach_pose: "위치 데이터 첨부",
    ov_recent: "최근 {h}h 이벤트",
    ov_total_sess: "전체 세션 {n}건",
    ov_avg_conf: "평균 AI 신뢰도",
    ov_qwen_analysis: "Qwen 분석 — {grade}",
    ov_wc_conn: "휠체어 연결",
    ov_online: "온라인",
    ov_offline: "오프라인",
    ov_recent_sess: "최근 세션 {date}",
    ov_no_data: "데이터 없음",
    ov_auto: "자율주행",
    ov_manual: "수동",
    ov_saved_reports: "저장된 보고서",
    ov_folder: "driving_data 폴더",
    ov_auto_parse: "최신 .md 자동 파싱",
    ov_loading: "데이터 불러오는 중…",
    ov_empty_loc: "위치 데이터가 있는 사고가 없습니다",
    ov_empty_reason: "집계된 원인이 없습니다",
    ov_coord: "SLAM 좌표 (m)",
    rp_basic_rep: "📄 기본 보고서",
    rp_deep_rep: "🤖 R1 깊은 진단 보고서",
    rp_fail_basic: "기본 보고서 데이터를 불러오지 못했습니다.",
    rp_fail_deep: "깊은 진단 보고서가 아직 생성되지 않았습니다.",
    lv_wait: "위치 데이터 대기 중…",
    lv_end_confirm: "현재 주행 세션을 마감하고 지금까지의 로그로 AI 진단을 시작하시겠습니까?",
    lv_end_success: "AI 분석이 시작되었습니다! 약 1~2분 뒤 '보고서' 탭에서 결과를 확인하세요.",
    lv_end_fail: "분석 요청 중 문제가 발생했습니다. 서버가 켜져 있는지 확인해주세요.",
    lv_loading: "실시간 데이터 연결 중…",
    lv_loc_title: "실시간 위치",
    lv_loc_sub: "SLAM 좌표 갱신 (2Hz 폴링)",
    lv_conn: "연결됨",
    lv_disconn: "끊김",
    lv_stream_title: "이벤트 스트림",
    lv_stream_sub: "최근 30건 · 신규는 위로 슬라이드",
    lv_count: "건",
    lv_end_btn: "일과 마감 및 AI 분석 시작",
    lv_end_req: "분석 요청 중...",
    lv_end_desc: "지금까지의 주행 로그를 바탕으로 리포트를 생성합니다.",
    lv_stop_title: "원격 정지",
    lv_stop_sub: "현재 주행 즉시 중단 · /sos_trigger 발행",
    lv_stop_sent: "정지 명령 전송됨",
    lv_stop_wait: "관제실 확인 대기 중…",
    lv_release: "해제 및 자율 복귀",
    lv_stop_confirm: "원격 정지 확인",
    lv_stop_msg1: "휠체어를 즉시 정지시킵니다. 사용자가 탑승 중이라면 충격이 발생할 수 있습니다.",
    lv_stop_msg2: "조치: /sos_trigger 토픽으로 \"manual_stop\" 발행",
    lv_cancel: "취소",
    lv_execute: "정지 실행",
    lv_standby: "대기 중…",
    login_title: "SMAC 관제 시스템",
    login_sub: "관리자 계정으로 로그인하세요",
    login_id_placeholder: "아이디",
    login_pw_placeholder: "비밀번호",
    login_btn: "로그인",
    login_err_invalid: "아이디 또는 비밀번호가 올바르지 않습니다.",
    alert_sos_title: "🚨 환자 SOS 긴급 호출!",
    alert_sos_msg: "환자가 구조를 요청했습니다:",
    alert_stop_title: "⚠️ 휠체어 비상 정지",
    alert_stop_msg: "센서 오류 및 장애물 감지:",
    reason_imu_lost: "IMU 연결 끊김",
    reason_imu_emergency: "IMU 비상(기울기·충격)",
    reason_imu_기울기: "IMU 기울기 초과",
    reason_ultrasonic_lost: "초음파 연결 끊김",
    reason_lidar_lost: "라이다 연결 끊김",
    reason_odom_lost: "오도메트리 끊김",
    reason_localization_emergency: "위치 추정 실패",
    reason_obstacle_front: "전방 장애물",
    reason_unknown: "원인불명",
    deep_err_server: "서버 에러 발생",
    lv_linear_vel: "선속도",
    lv_angular_vel: "각속도",
    ov_coords_count: "개 좌표",
    refresh_btn: "새로고침",
    avatar_initial: "관"
  },
  en: {
    nav_admin: "Admin",
    api_connected: "API Connected",
    sample_mode: "Sample Mode",
    session: "Session",
    server_not_running: "server.py not running",
    logout: "Logout",
    backend_connected: "Backend Connected",
    admin: "Admin",
    facility_team: "Facility Team",
    overview_daily_events: "Daily Events",
    overview_daily_sub: "Critical(Red) · Warning(Orange) Stack",
    overview_detected_causes: "Detected Causes",
    overview_causes_sub: "Aggregation by reason key",
    overview_accident_locations: "Location Heatmap",
    overview_locations_sub: "SLAM coords — Dot size is frequency",
    btn_deep_analyze: "R1 Deep Diagnosis",
    deep_error_default: "Unknown error occurred.",
    deep_starting: "Preparing analysis...",
    deep_running: "AI analyzing...",
    deep_done: "Analysis Done!",
    deep_failed: "Analysis Failed:",
    reports_conf_unknown: "Unknown Conf",
    overview_conf_good: "Good",
    overview_conf_ok: "Fair",
    overview_conf_low: "Low",
    reports_level_critical: "Critical",
    reports_level_warning: "Warning",
    reports_level_normal: "Normal",
    reports_search: "Search reports...",
    reports_filter_all: "All",
    reports_filter_critical: "Critical Only",
    reports_filter_warning: "Warning Only",
    reports_conf_gte: "Conf. ≥",
    reports_shown_count: " shown",
    reports_empty: "No reports match the filter.",
    reports_loading: "Loading report...",
    reports_msg_count: " messages",
    reports_raw_log: "Raw Log",
    reports_share: "Share",
    reports_pdf: "Save PDF",
    reports_ai_confidence: "AI Confidence",
    reports_kpi_estop: "E-Stop",
    reports_kpi_sos: "SOS",
    reports_kpi_cmd: "Modified",
    reports_kpi_normal: "Normal",
    reports_low_conf_title: "More Data Required",
    reports_low_conf_sub: "AI confidence is low.",
    reports_raw_lines: " lines",
    reports_raw_truncated: " (truncated)",
    share_modal_title: "Share Report",
    share_modal_body: "Send to guardian/manager.",
    share_modal_attach_log: "Attach raw logs",
    share_modal_attach_pose: "Attach pose data",
    ov_recent: "Last {h}h Events",
    ov_total_sess: "Total {n} Sessions",
    ov_avg_conf: "Avg AI Confidence",
    ov_qwen_analysis: "Qwen Analysis — {grade}",
    ov_wc_conn: "Wheelchair Conn.",
    ov_online: "Online",
    ov_offline: "Offline",
    ov_recent_sess: "Recent Session {date}",
    ov_no_data: "No Data",
    ov_auto: "Auto",
    ov_manual: "Manual",
    ov_saved_reports: "Saved Reports",
    ov_folder: "driving_data folder",
    ov_auto_parse: "Auto parsing latest .md",
    ov_loading: "Loading data...",
    ov_empty_loc: "No accidents with location data",
    ov_empty_reason: "No aggregated reasons",
    ov_coord: "SLAM Coords (m)",
    rp_basic_rep: "📄 Basic Report",
    rp_deep_rep: "🤖 R1 Deep Diagnosis",
    rp_fail_basic: "Failed to load basic report.",
    rp_fail_deep: "Deep diagnosis report not generated yet.",
    lv_wait: "Waiting for location data...",
    lv_end_confirm: "End current session and start AI diagnosis?",
    lv_end_success: "AI analysis started! Check 'Reports' tab in 1-2 mins.",
    lv_end_fail: "Error requesting analysis. Check server.",
    lv_loading: "Connecting live data...",
    lv_loc_title: "Live Location",
    lv_loc_sub: "SLAM coords refresh (2Hz)",
    lv_conn: "Connected",
    lv_disconn: "Disconnected",
    lv_stream_title: "Event Stream",
    lv_stream_sub: "Last 30 · New slides up",
    lv_count: " events",
    lv_end_btn: "End Session & Analyze",
    lv_end_req: "Requesting...",
    lv_end_desc: "Generates report from current driving logs.",
    lv_stop_title: "Remote Stop",
    lv_stop_sub: "Halt immediately · publish /sos_trigger",
    lv_stop_sent: "Stop Command Sent",
    lv_stop_wait: "Waiting for control room...",
    lv_release: "Release & Auto",
    lv_stop_confirm: "Confirm Remote Stop",
    lv_stop_msg1: "Halts immediately. May cause shock to rider.",
    lv_stop_msg2: "Action: Publish \"manual_stop\" to /sos_trigger",
    lv_cancel: "Cancel",
    lv_execute: "Execute Stop",
    lv_standby: "Standby...",
    login_title: "SMAC Control System",
    login_sub: "Please log in with an administrator account",
    login_id_placeholder: "User ID",
    login_pw_placeholder: "Password",
    login_btn: "Login",
    login_err_invalid: "Invalid ID or Password.",
    alert_sos_title: "🚨 Patient SOS Emergency!",
    alert_sos_msg: "Patient requested rescue:",
    alert_stop_title: "⚠️ Wheelchair Emergency Stop",
    alert_stop_msg: "Sensor error / Obstacle detected:",
    reason_imu_lost: "IMU Disconnected",
    reason_imu_emergency: "IMU Emergency (Tilt/Impact)",
    reason_imu_기울기: "IMU Tilt Exceeded",
    reason_ultrasonic_lost: "Ultrasonic Disconnected",
    reason_lidar_lost: "LiDAR Disconnected",
    reason_odom_lost: "Odometry Lost",
    reason_localization_emergency: "Localization Failed",
    reason_obstacle_front: "Front Obstacle",
    reason_unknown: "Unknown Cause",
    deep_err_server: "Server Error Occurred",
    lv_linear_vel: "Linear Vel",
    lv_angular_vel: "Angular Vel",
    ov_coords_count: " coords",
    refresh_btn: "Refresh",
    avatar_initial: "A"
  }
};

const NAV = [
  { id: "overview", icon: "LayoutDashboard", label: "개요" },
  { id: "reports", icon: "FileText", label: "보고서" },
  { id: "live", icon: "Activity", label: "실시간 모니터" },
];

function Icon({ name, size = 18, className = "", strokeWidth = 1.75 }) {
  const L = window.lucide;
  if (!L) return null;
  const node = L.icons?.[toKebab(name)];
  if (!node) return null;
  const [, , children] = node;
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`lucide ${className}`}
    >
      {children.map((c, i) => React.createElement(c[0], { key: i, ...c[1] }))}
    </svg>
  );
}

function toKebab(s) {
  return s.replace(/([a-z0-9])([A-Z])/g, "$1-$2").toLowerCase();
}

function Sidebar({ page, setPage, mode, health, onLogout, lang }) {
  const navLabels = {
    ko: { overview: "개요", reports: "보고서", live: "실시간 모니터" },
    en: { overview: "Overview", reports: "Reports", live: "Live Monitor" }
  };
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">
          <Icon name="Accessibility" size={20} strokeWidth={2} />
        </div>
        <div>
          <div className="brand-title">Mobicare</div>
          <div className="brand-sub">Wheelchair Ops</div>
        </div>
      </div>

      <nav className="nav">
        <div className="nav-label">{window.dict[lang].nav_admin}</div>
        {NAV.map((n) => (
          <button
            key={n.id}
            className={`nav-item ${page === n.id ? "active" : ""}`}
            onClick={() => setPage(n.id)}
          >
            <span className="nav-icon">
              <Icon name={n.icon} size={18} />
            </span>
            <span className="nav-text">{navLabels[lang][n.id]}</span>
            {n.id === "live" && mode === "live" && <span className="nav-pulse" />}
          </button>
        ))}
      </nav>

      <div className="sidebar-foot">
        <div className="fleet-card">
          <div className="fleet-card-row">
            <span className={`fleet-dot ${mode === "live" ? "ok" : "warn"}`} />
            <span>{mode === "live" ? window.dict[lang].api_connected : window.dict[lang].sample_mode}</span>
          </div>
          <div className="fleet-card-row mute">
            <span>{window.dict[lang].session} {health?.session_count ?? "—"}</span>
          </div>
          <div className="fleet-card-foot">
            {mode === "live" ? "localhost:8090" : window.dict[lang].server_not_running}
          </div>
        </div>
        <button className="logout" onClick={onLogout}>
          <Icon name="LogOut" size={16} />
          <span>{window.dict[lang].logout}</span>
        </button>
      </div>
    </aside>
  );
}

function Header({ page, mode, health, lang, setLang }) {
  const titles = lang === 'ko' ? {
    overview: { t: "개요", s: "주행 데이터 통계 — driving_data 기반" },
    reports: { t: "AI 사고 보고서", s: `Qwen 분석 — 세션 ${health?.session_count ?? 0}건` },
    live: { t: "실시간 모니터", s: "최근 세션 로그 폴링 (1Hz)" },
  } : {
    overview: { t: "Overview", s: "Driving Data Statistics — based on driving_data" },
    reports: { t: "AI Incident Reports", s: `Qwen Analysis — Sessions: ${health?.session_count ?? 0}` },
    live: { t: "Live Monitor", s: "Recent session log polling (1Hz)" },
  };
  const cur = titles[page];
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  return (
    <header className="topbar">
      <div className="topbar-left">
        <div className="page-title">{cur.t}</div>
        <div className="page-sub">{cur.s}</div>
      </div>
      <div className="topbar-right">
        {mode === "live" ? (
          <div className="link-pill">
            <span className="link-dot" />
            <span className="link-label">{window.dict[lang].backend_connected}</span>
            <span className="link-meta">localhost:8090</span>
          </div>
        ) : (
          <div className="link-pill warn">
            <span className="link-dot warn" />
            <span className="link-label">{window.dict[lang].sample_mode}</span>
            <span className="link-meta">{window.dict[lang].server_not_running}</span>
          </div>
        )}
        <div className="time-pill">
          <Icon name="Clock" size={14} />
          <span>{fmtClock(now)}</span>
        </div>
        
        {/* 한영 전환 버튼 추가 */}
        <button 
          className="btn" 
          onClick={() => setLang(lang === 'ko' ? 'en' : 'ko')}
          style={{ padding: "4px 8px", fontWeight: "bold", marginLeft: "8px" }}
        >
          {lang === 'ko' ? '🇺🇸 EN' : '🇰🇷 KR'}
        </button>

        <button className="icon-btn" title={window.dict[lang].refresh_btn} onClick={() => location.reload()}>
          <Icon name="RefreshCw" size={16} />
        </button>
        <div className="user-chip">
          <div className="avatar">{window.dict[lang].avatar_initial}</div>
          <div className="user-meta">
            <div className="user-name">{window.dict[lang].admin}</div>
            <div className="user-role">{window.dict[lang].facility_team}</div>
          </div>
        </div>
      </div>
    </header>
  );
}

function fmtClock(d) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}
function ToastAlerts({ alerts, removeAlert }) {
  return (
    <div className="toast-container">
      {alerts.map(alert => (
        <div key={alert.id} className={`toast-box ${alert.type}`}>
          <div className="toast-icon">
            <Icon name={alert.type === 'sos' ? 'Siren' : 'AlertTriangle'} size={24} />
          </div>
          <div className="toast-content">
            <strong>{alert.title}</strong>
            <p>{alert.message}</p>
            <span className="toast-time">{alert.time}</span>
          </div>
          <button className="toast-close" onClick={() => removeAlert(alert.id)}>
            <Icon name="X" size={18} />
          </button>
        </div>
      ))}
    </div>
  );
}

function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(() => {
    return sessionStorage.getItem('admin_logged_in') === 'true';
  });
  
  const [userId, setUserId] = useState('');
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState(false);

  const [page, setPage] = useState("overview");
  const [mode, setMode] = useState("sample");
  const [health, setHealth] = useState(null);
  const [lang, setLang] = useState("ko");

  const [alerts, setAlerts] = useState([]);

  // 알림을 추가하는 함수 (8초 뒤 자동 삭제)
  const addAlert = (type, title, message) => {
    const id = Date.now() + Math.random();
    const time = new Date().toLocaleTimeString(lang === 'ko' ? 'ko-KR' : 'en-US');
    setAlerts(prev => [...prev, { id, type, title, message, time }]);

    setTimeout(() => {
      setAlerts(prev => prev.filter(a => a.id !== id));
    }, 8000);
  };

  useEffect(() => {
    if (!isLoggedIn || !window.ros || !window.ROSLIB) return;

    const sosListener = new window.ROSLIB.Topic({
      ros: window.ros,
      name: '/sos_trigger',
      messageType: 'std_msgs/String'
    });

    const safetyListener = new window.ROSLIB.Topic({
      ros: window.ros,
      name: '/safety_action',
      messageType: 'std_msgs/String'
    });

    sosListener.subscribe((msg) => {
      addAlert('sos', window.dict[lang].alert_sos_title, `${window.dict[lang].alert_sos_msg} ${msg.data}`);
    });

    safetyListener.subscribe((msg) => {
      try {
        const data = JSON.parse(msg.data);
        if (data.action === 'blocked') {
           addAlert('error', window.dict[lang].alert_stop_title, `${window.dict[lang].alert_stop_msg} ${data.reason}`);
        }
      } catch(e) {}
    });

    return () => {
      sosListener.unsubscribe();
      safetyListener.unsubscribe();
    };
  }, [isLoggedIn, lang]); 

  const handleLogin = (e) => {
    e.preventDefault();
    if (userId === 'smac' && password === '0000') {
      setIsLoggedIn(true);
      sessionStorage.setItem('admin_logged_in', 'true');
      setLoginError(false);
    } else {
      setLoginError(true);
    }
  };

  const handleLogout = () => {
    setIsLoggedIn(false);
    sessionStorage.removeItem('admin_logged_in');
    setUserId('');
    setPassword('');
  };

  useEffect(() => {
    if (!isLoggedIn) return;
    let alive = true;
    (async () => {
      const m = await window.Api.getMode();
      const h = await window.Api.getHealth();
      if (!alive) return;
      setMode(m);
      setHealth(h);
    })();
    return () => { alive = false; };
  }, [isLoggedIn]);


  if (!isLoggedIn) {
    return (
      <div className="login-container">
        <div style={{ position: 'absolute', top: 20, right: 20 }}>
          <button className="btn" onClick={() => setLang(lang === 'ko' ? 'en' : 'ko')} style={{ background: '#fff', border: '1px solid #e5e9f0', padding: '6px 12px', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold' }}>
            {lang === 'ko' ? '🇺🇸 EN' : '🇰🇷 KR'}
          </button>
        </div>
        <div className="login-box">
          <h2>{window.dict[lang].login_title}</h2>
          <p>{window.dict[lang].login_sub}</p>
          <form onSubmit={handleLogin}>
            <div className="input-group">
              <input type="text" placeholder={window.dict[lang].login_id_placeholder} value={userId} onChange={(e) => setUserId(e.target.value)} autoFocus />
            </div>
            <div className="input-group">
              <input type="password" placeholder={window.dict[lang].login_pw_placeholder} value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
            {loginError && <div className="error-msg">{window.dict[lang].login_err_invalid}</div>}
            <button type="submit" className="login-btn">{window.dict[lang].login_btn}</button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="app" data-screen-label={`Mobicare · ${page}`}>
      
      {/* ⭐️ 실시간 팝업 알림 렌더링 (화면 맨 위에 떠있음) ⭐️ */}
      <ToastAlerts alerts={alerts} removeAlert={(id) => setAlerts(prev => prev.filter(a => a.id !== id))} />

      <Sidebar page={page} setPage={setPage} mode={mode} health={health} onLogout={handleLogout} lang={lang} />
      <div className="main">
        <Header page={page} mode={mode} health={health} lang={lang} setLang={setLang} />
        <div className="content">
          {page === "overview" && <OverviewPage lang={lang} />}
          {page === "reports" && <ReportsPage lang={lang} />}
          {page === "live" && <LivePage lang={lang} />}
        </div>
      </div>
    </div>
  );
}

window.App = App;
window.Icon = Icon;