const { useState, useEffect, useMemo } = React;
const { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Legend } = window.Recharts;

function StatCard({ label, value, sub, accent, foot, icon }) {
  return (
    <div className={`stat ${accent || ""}`}>
      <div className="stat-head">
        <div className="stat-label">{label}</div>
        {icon && <div className="stat-icon"><Icon name={icon} size={16} /></div>}
      </div>
      <div className="stat-value">{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
      {foot && <div className="stat-foot">{foot}</div>}
    </div>
  );
}

function HeatMap({ events }) {
  // Plot events on a coordinate plane normalized to a 320x220 viewport
  const pts = events.filter((e) => e.pose && e.pose.x != null && e.pose.y != null);
  if (!pts.length) {
    return (
      <div className="heatmap empty">
        <div className="empty-msg">위치 데이터가 있는 사고가 없습니다</div>
      </div>
    );
  }
  const xs = pts.map((p) => p.pose.x);
  const ys = pts.map((p) => p.pose.y);
  const minX = Math.min(...xs, -1.5);
  const maxX = Math.max(...xs, 1.5);
  const minY = Math.min(...ys, -1.5);
  const maxY = Math.max(...ys, 1.5);
  const padX = (maxX - minX) * 0.15 || 1;
  const padY = (maxY - minY) * 0.15 || 1;
  const x0 = minX - padX, x1 = maxX + padX;
  const y0 = minY - padY, y1 = maxY + padY;

  const W = 800, H = 440;
  const proj = (x, y) => [
    ((x - x0) / (x1 - x0)) * W,
    H - ((y - y0) / (y1 - y0)) * H,
  ];

  // Group nearby points to size dot by frequency
  const buckets = new Map();
  for (const p of pts) {
    const k = `${Math.round(p.pose.x * 10)}_${Math.round(p.pose.y * 10)}`;
    if (!buckets.has(k))
      buckets.set(k, { x: p.pose.x, y: p.pose.y, count: 0, severity: p.severity, reason: p.reason_label, ts: p.ts });
    const b = buckets.get(k);
    b.count++;
    if (p.severity === "critical") b.severity = "critical";
  }

  const gridLines = [];
  for (let gx = Math.ceil(x0); gx <= Math.floor(x1); gx++) {
    const [px] = proj(gx, 0);
    gridLines.push(<line key={`vx${gx}`} x1={px} y1={0} x2={px} y2={H} className="grid" />);
  }
  for (let gy = Math.ceil(y0); gy <= Math.floor(y1); gy++) {
    const [, py] = proj(0, gy);
    gridLines.push(<line key={`vy${gy}`} x1={0} y1={py} x2={W} y2={py} className="grid" />);
  }
  const [ox, oy] = proj(0, 0);

  return (
    <div className="heatmap">
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet">
        <rect x="0" y="0" width={W} height={H} className="map-bg" />
        <g className="map-grid">{gridLines}</g>
        <line x1={0} y1={oy} x2={W} y2={oy} className="axis" />
        <line x1={ox} y1={0} x2={ox} y2={H} className="axis" />
        {[...buckets.values()].map((b, i) => {
          const [px, py] = proj(b.x, b.y);
          const r = 6 + Math.min(18, b.count * 2.5);
          return (
            <g key={i}>
              <circle cx={px} cy={py} r={r} className={`dot-halo ${b.severity}`} />
              <circle cx={px} cy={py} r={5} className={`dot ${b.severity}`} />
              {b.count > 1 && <text x={px} y={py + 3} textAnchor="middle" className="dot-num">{b.count}</text>}
            </g>
          );
        })}
      </svg>
      <div className="heatmap-legend">
        <span><span className="lg-dot critical" /> 비상정지·SOS</span>
        <span><span className="lg-dot warning" /> 명령수정</span>
        <span className="mute">SLAM 좌표 (m)</span>
      </div>
    </div>
  );
}

function ReasonBars({ reasons }) {
  const total = reasons.reduce((s, r) => s + r.count, 0) || 1;
  if (!reasons.length) return <div className="empty-msg pad">집계된 원인이 없습니다</div>;
  return (
    <div className="reason-list">
      {reasons.map((r) => (
        <div key={r.key} className="reason-row">
          <div className="reason-row-head">
            <span className="reason-label">{r.label}</span>
            <span className="reason-count">{r.count}건</span>
          </div>
          <div className="reason-bar-wrap">
            <div
              className={`reason-bar ${classifyReason(r.key)}`}
              style={{ width: `${(r.count / total) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function classifyReason(key) {
  if (key === "obstacle_front") return "obstacle";
  if (key.startsWith("imu_") || key === "imu_기울기") return "imu";
  if (key === "lidar_lost" || key === "ultrasonic_lost" || key === "odom_lost") return "sensor";
  if (key === "localization_emergency") return "loc";
  return "other";
}

function OverviewPage() {
  const [data, setData] = useState(null);
  const [hours, setHours] = useState(24);

  useEffect(() => {
    let alive = true;
    setData(null);
    window.Api.getEvents(hours).then((d) => alive && setData(d));
    return () => { alive = false; };
  }, [hours]);

  if (!data) return <div className="loading">데이터 불러오는 중…</div>;

  const sev = data.by_severity || {};
  const critical = sev.critical || 0;
  const warning = sev.warning || 0;
  const conf = data.avg_confidence;
  const confGrade = conf == null ? "—" : conf >= 80 ? "양호" : conf >= 50 ? "보통" : "낮음";
  const confTone = conf == null ? "" : conf >= 80 ? "ok" : conf >= 50 ? "warn" : "danger";

  const chartData = data.by_day.length
    ? data.by_day
    : [{ day: "—", critical: 0, warning: 0 }];

  return (
    <div className="page overview">
      <div className="row-stats">
        <StatCard
          label={`최근 ${hours}h 이벤트`}
          value={data.recent_count}
          sub={`전체 세션 ${data.session_count}건`}
          icon="ActivitySquare"
          foot={
            <div className="split-foot">
              <span className="chip critical"><span className="chip-dot" />위험 {critical}</span>
              <span className="chip warning"><span className="chip-dot" />주의 {warning}</span>
            </div>
          }
        />
        <StatCard
          label="평균 AI 신뢰도"
          value={conf == null ? "—" : `${conf}%`}
          sub={`Qwen 분석 — ${confGrade}`}
          accent={confTone}
          icon="Sparkles"
          foot={
            conf != null && (
              <div className="conf-bar">
                <div className={`conf-bar-fill ${confTone}`} style={{ width: `${conf}%` }} />
              </div>
            )
          }
        />
        <StatCard
          label="휠체어 연결"
          value={data.session_count > 0 ? "온라인" : "오프라인"}
          sub={data.sessions[0] ? `최근 세션 ${fmtDate(data.sessions[0].started_at)}` : "데이터 없음"}
          accent="info"
          icon="Wifi"
          foot={
            <div className="mode-row">
              <span className="mode-pill">자율주행</span>
              <span className="mode-pill ghost">수동</span>
            </div>
          }
        />
        <StatCard
          label="저장된 보고서"
          value={data.session_count}
          sub="driving_data 폴더"
          icon="FolderArchive"
          foot={
            <div className="mute small">최신 .md 자동 파싱</div>
          }
        />
      </div>

      <div className="row-2">
        <div className="card">
          <div className="card-head">
            <div>
              <div className="card-title">일자별 이벤트</div>
              <div className="card-sub">위험(빨강) · 주의(주황) 스택</div>
            </div>
            <div className="seg">
              {[24, 72, 168].map((h) => (
                <button key={h} className={`seg-btn ${hours === h ? "active" : ""}`} onClick={() => setHours(h)}>
                  {h === 24 ? "24h" : h === 72 ? "3d" : "7d"}
                </button>
              ))}
            </div>
          </div>
          <div style={{ height: 280 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
                <CartesianGrid stroke="#e5e9f0" vertical={false} />
                <XAxis dataKey="day" stroke="#6b7280" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="#6b7280" fontSize={12} tickLine={false} axisLine={false} allowDecimals={false} />
                <Tooltip cursor={{ fill: "rgba(15,23,42,0.04)" }} contentStyle={{ borderRadius: 8, border: "1px solid #e5e9f0", fontSize: 12 }} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="critical" stackId="a" fill="#dc2626" name="위험" radius={[3, 3, 0, 0]} />
                <Bar dataKey="warning" stackId="a" fill="#ea7c1c" name="주의" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <div>
              <div className="card-title">감지된 이상 원인</div>
              <div className="card-sub">reason 키 별 집계</div>
            </div>
          </div>
          <ReasonBars reasons={data.reasons} />
        </div>
      </div>

      <div className="card">
        <div className="card-head">
          <div>
            <div className="card-title">사고 발생 위치 히트맵</div>
            <div className="card-sub">SLAM 좌표(pose.x / pose.y) — 점 크기는 빈도</div>
          </div>
          <div className="muted-meta">{data.events.filter((e) => e.pose && e.pose.x != null).length}개 좌표</div>
        </div>
        <HeatMap events={data.events} />
      </div>
    </div>
  );
}

function fmtDate(ts) {
  if (!ts) return "—";
  const d = new Date(ts * 1000);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

window.OverviewPage = OverviewPage;
window.fmtDate = fmtDate;
