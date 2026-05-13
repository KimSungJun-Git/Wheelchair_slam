
const { useState, useEffect } = React;

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

function Sidebar({ page, setPage, mode, health, onLogout }) {
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
        <div className="nav-label">관리</div>
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
            <span>{mode === "live" ? "API 연결됨" : "샘플 모드"}</span>
          </div>
          <div className="fleet-card-row mute">
            <span>세션 {health?.session_count ?? "—"}</span>
          </div>
          <div className="fleet-card-foot">
            {mode === "live" ? "localhost:8090" : "server.py 실행 시 라이브"}
          </div>
        </div>
        <button className="logout" onClick={onLogout}>
          <Icon name="LogOut" size={16} />
          <span>로그아웃</span>
        </button>
      </div>
    </aside>
  );
}

function Header({ page, mode, health }) {
  const titles = {
    overview: { t: "개요", s: "주행 데이터 통계 — driving_data 기반" },
    reports: { t: "AI 사고 보고서", s: `Qwen 분석 — 세션 ${health?.session_count ?? 0}건` },
    live: { t: "실시간 모니터", s: "최근 세션 로그 폴링 (1Hz)" },
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
            <span className="link-label">백엔드 연결됨</span>
            <span className="link-meta">localhost:8090</span>
          </div>
        ) : (
          <div className="link-pill warn">
            <span className="link-dot warn" />
            <span className="link-label">샘플 모드</span>
            <span className="link-meta">server.py 미실행</span>
          </div>
        )}
        <div className="time-pill">
          <Icon name="Clock" size={14} />
          <span>{fmtClock(now)}</span>
        </div>
        <button className="icon-btn" title="새로고침" onClick={() => location.reload()}>
          <Icon name="RefreshCw" size={16} />
        </button>
        <div className="user-chip">
          <div className="avatar">관</div>
          <div className="user-meta">
            <div className="user-name">관리자</div>
            <div className="user-role">시설관리팀</div>
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
  const [loginError, setLoginError] = useState('');

  const [page, setPage] = useState("overview");
  const [mode, setMode] = useState("sample");
  const [health, setHealth] = useState(null);

  const [alerts, setAlerts] = useState([]);

  // 알림을 추가하는 함수 (8초 뒤 자동 삭제)
  const addAlert = (type, title, message) => {
    const id = Date.now() + Math.random();
    const time = new Date().toLocaleTimeString('ko-KR');
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
      addAlert('sos', '🚨 환자 SOS 긴급 호출!', `환자가 구조를 요청했습니다: ${msg.data}`);
    });

    safetyListener.subscribe((msg) => {
      try {
        const data = JSON.parse(msg.data);
        if (data.action === 'blocked') {
           addAlert('error', '⚠️ 휠체어 비상 정지', `센서 오류 및 장애물 감지: ${data.reason}`);
        }
      } catch(e) {}
    });

    return () => {
      sosListener.unsubscribe();
      safetyListener.unsubscribe();
    };
  }, [isLoggedIn]); 

  const handleLogin = (e) => {
    e.preventDefault();
    if (userId === 'smac' && password === '0000') {
      setIsLoggedIn(true);
      sessionStorage.setItem('admin_logged_in', 'true');
      setLoginError('');
    } else {
      setLoginError('아이디 또는 비밀번호가 올바르지 않습니다.');
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
        {/* ... (기존 로그인 UI 화면 동일) ... */}
        <div className="login-box">
          <h2>SMAC 관제 시스템</h2>
          <p>관리자 계정으로 로그인하세요</p>
          <form onSubmit={handleLogin}>
            <div className="input-group">
              <input type="text" placeholder="아이디" value={userId} onChange={(e) => setUserId(e.target.value)} autoFocus />
            </div>
            <div className="input-group">
              <input type="password" placeholder="비밀번호" value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
            {loginError && <div className="error-msg">{loginError}</div>}
            <button type="submit" className="login-btn">로그인</button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="app" data-screen-label={`Mobicare · ${page}`}>
      
      {/* ⭐️ 실시간 팝업 알림 렌더링 (화면 맨 위에 떠있음) ⭐️ */}
      <ToastAlerts alerts={alerts} removeAlert={(id) => setAlerts(prev => prev.filter(a => a.id !== id))} />

      <Sidebar page={page} setPage={setPage} mode={mode} health={health} onLogout={handleLogout} />
      <div className="main">
        <Header page={page} mode={mode} health={health} />
        <div className="content">
          {page === "overview" && <OverviewPage />}
          {page === "reports" && <ReportsPage />}
          {page === "live" && <LivePage />}
        </div>
      </div>
    </div>
  );
}

window.App = App;
window.Icon = Icon;