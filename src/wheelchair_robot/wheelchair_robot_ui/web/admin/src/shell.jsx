// Shell: sidebar + header + page router
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

function App() {
  // --- 1. 로그인 상태 관리 추가 ---
  const [isLoggedIn, setIsLoggedIn] = useState(() => {
    return sessionStorage.getItem('admin_logged_in') === 'true';
  });

  const [page, setPage] = useState("overview");
  const [mode, setMode] = useState("sample");
  const [health, setHealth] = useState(null);

  // --- 2. 새로고침 시 로그인 상태 확인 ---
  const [userId, setUserId] = useState('');
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  // --- 3. 로그인 / 로그아웃 처리 함수 ---
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

  // 기존 API 헬스체크
  useEffect(() => {
    if (!isLoggedIn) return; // 로그인 전에는 백엔드 통신 안 함
    
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
  }, [isLoggedIn]); // 로그인 상태가 바뀔 때 다시 실행


  // --- 4. 렌더링 분기: 로그인이 안 되어 있으면 로그인 화면 렌더링 ---
  if (!isLoggedIn) {
    return (
      <div className="login-container">
        <div className="login-box">
          <h2>SMAC 관제 시스템</h2>
          <p>관리자 계정으로 로그인하세요</p>
          <form onSubmit={handleLogin}>
            <div className="input-group">
              <input 
                type="text" 
                placeholder="아이디" 
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                autoFocus
              />
            </div>
            <div className="input-group">
              <input 
                type="password" 
                placeholder="비밀번호" 
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            {loginError && <div className="error-msg">{loginError}</div>}
            <button type="submit" className="login-btn">로그인</button>
          </form>
        </div>
      </div>
    );
  }

  // --- 5. 로그인 성공 시 기존 대시보드 렌더링 ---
  return (
    <div className="app" data-screen-label={`Mobicare · ${page}`}>
      {/* Sidebar 컴포넌트에 로그아웃 함수를 전달합니다 */}
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