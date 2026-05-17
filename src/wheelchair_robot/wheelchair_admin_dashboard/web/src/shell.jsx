// Shell: sidebar + header + page router
// (Includes the KR/EN dictionary inline so no extra <script> tag is needed.)

window.dict = {
  ko: {
    // --- Shell / nav ---
    nav_admin: "관리",
    nav_overview: "개요",
    nav_reports: "보고서",
    nav_live: "실시간 모니터",
    sidebar_api_connected: "API 연결됨",
    sidebar_sample_mode: "샘플 모드",
    sidebar_server_hint: "server.py 실행 시 라이브",
    sidebar_session: "세션",
    sidebar_logout: "로그아웃",
    header_overview_title: "개요",
    header_overview_sub: "주행 데이터 통계 — driving_data 기반",
    header_reports_title: "AI 사고 보고서",
    header_reports_sub: "Qwen 분석 — 세션",
    header_live_title: "실시간 모니터",
    header_live_sub: "최근 세션 로그 폴링 (1Hz)",
    header_backend_connected: "백엔드 연결됨",
    header_sample_mode: "샘플 모드",
    header_server_down: "server.py 미실행",
    header_admin_name: "관리자",
    header_admin_role: "시설관리팀",
    header_refresh: "새로고침",
    confirm_manual_analyze: "현재까지의 로그를 기반으로 AI 분석을 시작하시겠습니까?",
    alert_analyze_done: "분석 완료! 보고서 목록을 확인하세요.",
    alert_error: "에러: ",

    // --- Overview ---
    overview_loading: "데이터 불러오는 중…",
    overview_recent_events: "최근 {h}h 이벤트",
    overview_total_sessions: "전체 세션",
    overview_critical: "위험",
    overview_warning: "주의",
    overview_avg_conf: "평균 AI 신뢰도",
    overview_qwen_analysis: "Qwen 분석",
    overview_conf_good: "양호",
    overview_conf_ok: "보통",
    overview_conf_low: "낮음",
    overview_wheelchair_link: "휠체어 연결",
    overview_online: "온라인",
    overview_offline: "오프라인",
    overview_last_session: "최근 세션",
    overview_no_data: "데이터 없음",
    overview_mode_auto: "자율주행",
    overview_mode_manual: "수동",
    overview_saved_reports: "저장된 보고서",
    overview_data_folder: "driving_data 폴더",
    overview_md_parse: "최신 .md 자동 파싱",
    overview_daily_events: "일자별 이벤트",
    overview_stack_hint: "위험(빨강) · 주의(주황) 스택",
    overview_detected_causes: "감지된 이상 원인",
    overview_reason_sub: "reason 키 별 집계",
    overview_no_reasons: "집계된 원인이 없습니다",
    overview_count_suffix: "건",
    overview_accident_locations: "사고 발생 위치 히트맵",
    overview_heatmap_sub: "SLAM 좌표(pose.x / pose.y) — 점 크기는 빈도",
    overview_no_loc: "위치 데이터가 있는 사고가 없습니다",
    overview_coords: "개 좌표",
    overview_legend_estop: "비상정지·SOS",
    overview_legend_cmd: "명령수정",
    overview_legend_meters: "SLAM 좌표 (m)",

    // --- Reports ---
    reports_loading: "보고서 로딩 중…",
    btn_deep_analyze: "최신 로그 R1 깊은 진단",
    deep_starting: "서버에 분석 요청 중...",
    deep_running: "분석 중...",
    deep_done: "✅ 분석 완료!",
    deep_failed: "❌ 실패:",
    deep_error_default: "서버 에러 발생",
    reports_search: "파일명 검색",
    reports_filter_all: "전체",
    reports_filter_critical: "위험",
    reports_filter_warning: "주의",
    reports_conf_gte: "신뢰도 ≥",
    reports_shown_count: "건 표시",
    reports_empty: "조건에 맞는 보고서가 없습니다",
    reports_level_critical: "위험",
    reports_level_warning: "주의",
    reports_level_normal: "정상",
    reports_conf_unknown: "신뢰도 미상",
    reports_raw_log: "원본 로그",
    reports_share: "보호자 공유",
    reports_pdf: "PDF",
    reports_ai_confidence: "AI 신뢰도",
    reports_kpi_estop: "비상정지",
    reports_kpi_sos: "SOS",
    reports_kpi_cmd: "명령수정",
    reports_kpi_normal: "정상",
    reports_low_conf_title: "추가 데이터 수집 필요",
    reports_low_conf_sub: "AI 신뢰도가 50% 미만입니다. 다음 주행 세션에서 더 많은 센서 로그를 확보하거나, 수동으로 사건을 라벨링하세요.",
    reports_raw_lines: "줄 표시",
    reports_raw_truncated: " (절단됨)",
    reports_msg_count: "msg",
    share_modal_title: "보호자에게 공유",
    share_modal_body: "이 보고서를 등록된 보호자에게 이메일로 전송합니다. 본문에는 마크다운 요약과 사건 좌표가 포함됩니다.",
    share_modal_attach_log: "원본 로그 첨부",
    share_modal_attach_pose: "SLAM 위치 이미지 포함",
    common_cancel: "취소",
    common_send: "전송",

    // --- Live ---
    live_loading: "실시간 데이터 연결 중…",
    live_title: "실시간 위치",
    live_sub: "SLAM 좌표 갱신 (2Hz 폴링)",
    live_pose_waiting: "위치 데이터 대기 중…",
    live_mode_auto: "자율주행",
    live_mode_manual: "수동",
    live_connected: "연결됨",
    live_disconnected: "끊김",
    live_vel_linear: "선속도",
    live_vel_angular: "각속도",
    live_stream_title: "이벤트 스트림",
    live_stream_sub: "최근 30건 · 신규는 위로 슬라이드",
    live_stream_idle: "대기 중…",
    live_count_suffix: "건",
    live_tag_sos: "SOS",
    live_tag_blocked: "비상정지",
    live_tag_modified: "명령수정",
    live_tag_allowed: "정상",
    live_remote_stop: "원격 정지",
    live_remote_stop_sub: "현재 주행 즉시 중단 · /sos_trigger 발행",
    live_stop_sent: "정지 명령 전송됨",
    live_stop_wait: "관제실 확인 대기 중…",
    live_stop_release: "해제",
    live_confirm_title: "원격 정지 확인",
    live_confirm_body: "휠체어가 즉시 정지합니다. 탑승 중인 사용자가 있을 경우 급정거 충격이 발생할 수 있습니다.",
    live_confirm_action: "조치: /sos_trigger 토픽으로 \"manual_stop\" 발행",
    live_confirm_execute: "정지 실행",
  },

  en: {
    nav_admin: "Admin",
    nav_overview: "Overview",
    nav_reports: "Reports",
    nav_live: "Live Monitor",
    sidebar_api_connected: "API connected",
    sidebar_sample_mode: "Sample mode",
    sidebar_server_hint: "Run server.py for live",
    sidebar_session: "Session",
    sidebar_logout: "Log out",
    header_overview_title: "Overview",
    header_overview_sub: "Driving statistics — based on driving_data",
    header_reports_title: "AI Incident Reports",
    header_reports_sub: "Qwen analysis — sessions",
    header_live_title: "Live Monitor",
    header_live_sub: "Polling latest session log (1Hz)",
    header_backend_connected: "Backend connected",
    header_sample_mode: "Sample Mode",
    header_server_down: "server.py not running",
    header_admin_name: "Admin",
    header_admin_role: "Facility Ops",
    header_refresh: "Refresh",
    confirm_manual_analyze: "Run AI analysis on the session so far?",
    alert_analyze_done: "Analysis complete! Check the reports list.",
    alert_error: "Error: ",

    overview_loading: "Loading data…",
    overview_recent_events: "Last {h}h events",
    overview_total_sessions: "Total sessions",
    overview_critical: "Critical",
    overview_warning: "Warning",
    overview_avg_conf: "Avg. AI confidence",
    overview_qwen_analysis: "Qwen analysis",
    overview_conf_good: "Healthy",
    overview_conf_ok: "OK",
    overview_conf_low: "Low",
    overview_wheelchair_link: "Wheelchair link",
    overview_online: "Online",
    overview_offline: "Offline",
    overview_last_session: "Last session",
    overview_no_data: "No data",
    overview_mode_auto: "Auto",
    overview_mode_manual: "Manual",
    overview_saved_reports: "Saved reports",
    overview_data_folder: "driving_data folder",
    overview_md_parse: "Auto-parse latest .md",
    overview_daily_events: "Events by day",
    overview_stack_hint: "Critical (red) · Warning (orange) stacked",
    overview_detected_causes: "Detected anomaly causes",
    overview_reason_sub: "Aggregated by reason key",
    overview_no_reasons: "No causes aggregated",
    overview_count_suffix: "",
    overview_accident_locations: "Incident location heatmap",
    overview_heatmap_sub: "SLAM coords (pose.x / pose.y) — size = frequency",
    overview_no_loc: "No incidents with location data",
    overview_coords: " points",
    overview_legend_estop: "E-stop · SOS",
    overview_legend_cmd: "Cmd Correction",
    overview_legend_meters: "SLAM coords (m)",

    reports_loading: "Loading report…",
    btn_deep_analyze: "Run R1 deep diagnosis on latest log",
    deep_starting: "Requesting analysis…",
    deep_running: "Analyzing…",
    deep_done: "✅ Done!",
    deep_failed: "❌ Failed:",
    deep_error_default: "Server error",
    reports_search: "Search filename",
    reports_filter_all: "All",
    reports_filter_critical: "Critical",
    reports_filter_warning: "Warning",
    reports_conf_gte: "Confidence ≥",
    reports_shown_count: " shown",
    reports_empty: "No reports match the filter",
    reports_level_critical: "Critical",
    reports_level_warning: "Warning",
    reports_level_normal: "Normal",
    reports_conf_unknown: "Not measured",
    reports_raw_log: "Raw log",
    reports_share: "Share",
    reports_pdf: "PDF",
    reports_ai_confidence: "AI confidence",
    reports_kpi_estop: "E-stop",
    reports_kpi_sos: "SOS",
    reports_kpi_cmd: "Cmd Edit",
    reports_kpi_normal: "Normal",
    reports_low_conf_title: "More data needed",
    reports_low_conf_sub: "AI confidence is below 50%. Collect more sensor logs in the next session, or label incidents manually.",
    reports_raw_lines: " lines",
    reports_raw_truncated: " (truncated)",
    reports_msg_count: "msg",
    share_modal_title: "Share with guardian",
    share_modal_body: "Sends this report to the registered guardian by email. The body contains a Markdown summary and incident coordinates.",
    share_modal_attach_log: "Attach raw log",
    share_modal_attach_pose: "Include SLAM location image",
    common_cancel: "Cancel",
    common_send: "Send",

    live_loading: "Connecting to live data…",
    live_title: "Live Position",
    live_sub: "SLAM coords (2Hz)",
    live_pose_waiting: "Waiting for pose data…",
    live_mode_auto: "Auto",
    live_mode_manual: "Manual",
    live_connected: "Connected",
    live_disconnected: "Disconnected",
    live_vel_linear: "VEL",
    live_vel_angular: "ROT",
    live_stream_title: "Event Stream",
    live_stream_sub: "Last 30 · newest slides in",
    live_stream_idle: "Waiting…",
    live_count_suffix: "",
    live_tag_sos: "SOS",
    live_tag_blocked: "E-STOP",
    live_tag_modified: "CMD EDIT",
    live_tag_allowed: "OK",
    live_remote_stop: "Remote Stop",
    live_remote_stop_sub: "Halt driving immediately · publishes /sos_trigger",
    live_stop_sent: "Stop command sent",
    live_stop_wait: "Waiting for control room…",
    live_stop_release: "Release",
    live_confirm_title: "Confirm Remote Stop",
    live_confirm_body: "The wheelchair stops immediately. If a user is seated in it, a sudden impact may occur.",
    live_confirm_action: "Action: publish \"manual_stop\" on /sos_trigger",
    live_confirm_execute: "Execute Stop",
  },
};

// Helper for templated keys ({h} substitution).
window.tdict = function (lang, key, vars) {
  let s = (window.dict[lang] && window.dict[lang][key]) || (window.dict.ko[key] || key);
  if (vars) {
    for (const k in vars) s = s.replace(`{${k}}`, vars[k]);
  }
  return s;
};

const { useState, useEffect } = React;

const NAV_ICONS = {
  overview: "LayoutDashboard",
  reports: "FileText",
  live: "Activity",
};

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

function Sidebar({ page, setPage, mode, health, lang }) {
  const NAV = [
    { id: "overview", icon: NAV_ICONS.overview, label: dict[lang].nav_overview },
    { id: "reports",  icon: NAV_ICONS.reports,  label: dict[lang].nav_reports },
    { id: "live",     icon: NAV_ICONS.live,     label: dict[lang].nav_live },
  ];
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
        <div className="nav-label">{dict[lang].nav_admin}</div>
        {NAV.map((n) => (
          <button
            key={n.id}
            className={`nav-item ${page === n.id ? "active" : ""}`}
            onClick={() => setPage(n.id)}
          >
            <span className="nav-icon">
              <Icon name={n.icon} size={18} />
            </span>
            <span className="nav-text">{n.label}</span>
            {n.id === "live" && mode === "live" && <span className="nav-pulse" />}
          </button>
        ))}
      </nav>

      <div className="sidebar-foot">
        <div className="fleet-card">
          <div className="fleet-card-row">
            <span className={`fleet-dot ${mode === "live" ? "ok" : "warn"}`} />
            <span>{mode === "live" ? dict[lang].sidebar_api_connected : dict[lang].sidebar_sample_mode}</span>
          </div>
          <div className="fleet-card-row mute">
            <span>{dict[lang].sidebar_session} {health?.session_count ?? "—"}</span>
          </div>
          <div className="fleet-card-foot">
            {mode === "live" ? "localhost:8090" : dict[lang].sidebar_server_hint}
          </div>
        </div>
        <button className="logout">
          <Icon name="LogOut" size={16} />
          <span>{dict[lang].sidebar_logout}</span>
        </button>
      </div>
    </aside>
  );
}

function Header({ page, mode, health, lang, setLang}) {
  const titles = {
    overview: { t: dict[lang].header_overview_title, s: dict[lang].header_overview_sub },
    reports:  { t: dict[lang].header_reports_title,  s: `${dict[lang].header_reports_sub} ${health?.session_count ?? 0}${dict[lang].overview_count_suffix}` },
    live:     { t: dict[lang].header_live_title,     s: dict[lang].header_live_sub },
  };
  const cur = titles[page];
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  const handleManualAnalyze = async () => {
    if (!confirm(dict[lang].confirm_manual_analyze)) return;

    const result = await window.Api.triggerAnalysis();
    if (result.ok) {
      alert(dict[lang].alert_analyze_done);
      location.reload();
    } else {
      alert(dict[lang].alert_error + result.detail);
    }
  };

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
            <span className="link-label">{dict[lang].header_backend_connected}</span>
            <span className="link-meta">localhost:8090</span>
          </div>
        ) : (
          <div className="link-pill warn">
            <span className="link-dot warn" />
            <span className="link-label">{dict[lang].header_sample_mode}</span>
            <span className="link-meta">{dict[lang].header_server_down}</span>
          </div>
        )}
        <div className="time-pill">
          <Icon name="Clock" size={14} />
          <span>{fmtClock(now)}</span>
        </div>
        <button 
          className="btn" 
          onClick={() => setLang(lang === 'ko' ? 'en' : 'ko')}
          style={{ padding: "4px 8px", fontWeight: "bold", marginLeft: "8px" }}
        >
          {lang === 'ko' ? '🇺🇸 EN' : '🇰🇷 KR'}
        </button>

        <button className="icon-btn" title={dict[lang].header_refresh} onClick={() => location.reload()}>
          <Icon name="RefreshCw" size={16} />
        </button>
        <div className="user-chip">
          <div className="avatar">{lang === "ko" ? "관" : "A"}</div>
          <div className="user-meta">
            <div className="user-name">{dict[lang].header_admin_name}</div>
            <div className="user-role">{dict[lang].header_admin_role}</div>
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

function App() {
  const [page, setPage] = useState("overview");
  const [mode, setMode] = useState("sample");
  const [health, setHealth] = useState(null);
  const [lang, setLang] = useState("ko");
  useEffect(() => {
    let alive = true;
    (async () => {
      const m = await window.Api.getMode();
      const h = await window.Api.getHealth();
      if (!alive) return;
      setMode(m);
      setHealth(h);
    })();
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div className="app" data-screen-label={`Mobicare · ${page}`}>
      <Sidebar page={page} setPage={setPage} mode={mode} health={health} lang={lang} />
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
