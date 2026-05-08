// ─── 3. Map Component ─────────────────────────────────────────────
// world 좌표(meters)를 SVG 픽셀로 변환. AMCL/odom의 (x, y, yaw)를 직접 받음.
function worldToScreen(wx, wy, mapConfig) {
  const px = (wx - mapConfig.origin_x) * mapConfig.pixels_per_meter;
  // ROS는 y+가 위, SVG는 y+가 아래라 뒤집기
  const py = mapConfig.svg_height - (wy - mapConfig.origin_y) * mapConfig.pixels_per_meter;
  return { x: px, y: py };
}

function SlamMap({
  width = 800, height = 480,
  showPath = true,
  // ⭐ 변경(2025): 휠체어 아이콘 일단 비표시. 다시 켜고 싶으면 호출부에서 showRobot={true} 명시.
  showRobot = false,
  // robotWorld: { x, y, yaw } in meters/radians (AMCL pose)
  // null이면 기본 위치 표시
  robotWorld = null,
  mapConfig = DEFAULT_MAP_CONFIG,
  pathProgress = 0.35,
  showObstacles = false,
  destination = null,
}) {
  const C = TOKENS.color;
  const pathD = 'M 180 380 L 180 240 L 400 240 L 560 240 L 680 240 L 680 150', pathLength = 720;

  // world 좌표 → 화면 픽셀 변환
  const robotScreen = robotWorld
    ? worldToScreen(robotWorld.x, robotWorld.y, mapConfig)
    : { x: 180, y: 380 };
  // ROS yaw: 반시계가 +. SVG rotate는 시계방향이 +. 그리고 y축 뒤집힘 보정.
  const headingDeg = robotWorld
    ? -(robotWorld.yaw * 180 / Math.PI)
    : 0;

  return (
    <svg viewBox="0 0 800 480" width="100%" height="100%" preserveAspectRatio="xMidYMid slice" style={{ display: 'block', background: C.mapBg }}>
      <rect x="0" y="0" width="800" height="480" fill={C.mapFloor} opacity="0.3" />
      <path d="M40 40 L 760 40 L 760 440 L 40 440 Z M40 140 L 720 140 M40 340 L 720 340 M150 40 L 150 140 M300 40 L 300 140 M450 40 L 450 140 M620 40 L 620 140" fill="none" stroke={C.mapWall} strokeWidth="2.5" strokeLinecap="round" />
      <rect x="360" y="215" width="80" height="50" fill={C.primarySoft} stroke={C.primary} strokeWidth="2" />
      <text x="400" y="243" textAnchor="middle" fontSize="12" fill={C.primaryDark} fontWeight="800">간호스테이션</text>

      {showPath && <><path d={pathD} fill="none" stroke={C.mapPathGhost} strokeWidth="6" strokeDasharray="2 10" /><path d={pathD} fill="none" stroke={C.mapPath} strokeWidth="5.5" strokeDasharray={pathLength} strokeDashoffset={pathLength * (1 - pathProgress)} /></>}
      {destination && <g transform={`translate(${destination.x}, ${destination.y})`}><circle r="14" fill={C.accent} opacity="0.2"/><circle r="8" fill={C.accent} /></g>}
      {showObstacles && <g transform="translate(560, 240)"><circle r="16" fill={C.danger} opacity="0.3"/><circle r="8" fill={C.danger} /></g>}
      {showRobot && (
        <g transform={`translate(${robotScreen.x}, ${robotScreen.y}) rotate(${headingDeg})`} style={{ transition: 'transform 0.15s linear' }}>
          {/* 라이브 위치 펄스 (RViz 느낌) */}
          <circle r="28" fill={C.primary} opacity="0.12">
            <animate attributeName="r" values="22;32;22" dur="2s" repeatCount="indefinite" />
            <animate attributeName="opacity" values="0.18;0.06;0.18" dur="2s" repeatCount="indefinite" />
          </circle>
          <circle r="20" fill={C.surface} opacity="0.9" />
          <circle r="16" fill={C.mapRobot} />
          <path d="M 0 -14 L 6 -2 L -6 -2 Z" fill={C.surface} />
        </g>
      )}
    </svg>
  );
}

// ─── 3.5 도착 모달 & 장애물 근접 표시 ───────────────────────────────
function ArrivalModal({ open, label, onDismiss }) {
  const [remaining, setRemaining] = React.useState(10);
  React.useEffect(() => {
    if (!open) return;
    setRemaining(10);
    const start = Date.now();
    const tick = setInterval(() => {
      const left = Math.max(0, 10 - Math.floor((Date.now() - start) / 1000));
      setRemaining(left);
      if (left <= 0) { clearInterval(tick); onDismiss(); }
    }, 250);
    return () => clearInterval(tick);
  }, [open, onDismiss]);
  if (!open) return null;
  const C = TOKENS.color;
  return (
    <div onClick={onDismiss} style={{
      position: 'absolute', inset: 0, zIndex: 110,
      background: 'rgba(8,28,56,0.55)', backdropFilter: 'blur(4px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: TOKENS.font.sans, cursor: 'pointer',
    }}>
      <div onClick={(e) => e.stopPropagation()} style={{
        width: 560, padding: '40px 44px',
        background: '#fff', borderRadius: 28,
        boxShadow: '0 24px 60px rgba(0,47,108,0.35)',
        textAlign: 'center', position: 'relative',
        animation: 'arrivalIn 0.5s cubic-bezier(0.34, 1.56, 0.64, 1)',
        cursor: 'default',
      }}>
        {/* 큰 체크 아이콘 + ripple */}
        <div style={{ width: 120, height: 120, margin: '0 auto 20px', position: 'relative' }}>
          <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: C.successSoft, animation: 'arrivalRing 1.6s ease-out infinite' }} />
          <div style={{ position: 'absolute', inset: 8, borderRadius: '50%', background: C.successSoft, animation: 'arrivalRing 1.6s ease-out 0.4s infinite' }} />
          <div style={{ position: 'absolute', inset: 16, borderRadius: '50%', background: C.success, display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 8px 24px rgba(16,165,113,0.35)' }}>
            <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12l5 5 9-11"/></svg>
          </div>
        </div>
        <div style={{ fontSize: 16, fontWeight: 800, color: C.success, letterSpacing: 2, marginBottom: 8 }}>도착 완료</div>
        <div style={{ fontSize: 32, fontWeight: 800, color: C.primaryDark, marginBottom: 10, letterSpacing: -0.5 }}>
          {label}에 도착했습니다
        </div>
        <div style={{ fontSize: 16, color: C.inkMuted, fontWeight: 600, marginBottom: 24, lineHeight: 1.5 }}>
          안전하게 도착했어요. 잠시 후 홈 화면으로 이동합니다.
        </div>
        <button onClick={onDismiss} style={{
          display: 'inline-flex', alignItems: 'center', gap: 8,
          padding: '14px 28px', background: C.primary, color: '#fff',
          border: 'none', borderRadius: 999, cursor: 'pointer',
          fontSize: 16, fontWeight: 800, fontFamily: 'inherit',
        }}>
          지금 홈으로 ({remaining}s)
        </button>
        <div style={{ marginTop: 12, fontSize: 12, color: C.inkFaint, fontWeight: 600 }}>
          화면을 누르면 즉시 닫힙니다
        </div>
      </div>
    </div>
  );
}

// 자동차 후방 주차 센서 스타일: 방향별로 빨강/주황/노랑 바가 점등
// 거리(m) → 시각화 정보. 임계값 기반.
// null/Infinity/>= 1m 이면 inactive (회색, 흐릿)
function distToVisual(d) {
  if (d == null || !isFinite(d) || d >= DIST_THRESHOLDS.white) {
    return { active: false, color: '#1E293B', opacity: 0.18, level: 0 };
  }
  if (d < DIST_THRESHOLDS.red) {
    return { active: true, color: '#E5484D', opacity: 1, level: 3 };       // 빨강
  }
  if (d < DIST_THRESHOLDS.orange) {
    return { active: true, color: '#F97316', opacity: 1, level: 2 };       // 주황
  }
  // 0.8 ≤ d < 1.0
  return { active: true, color: '#F8FAFC', opacity: 0.95, level: 1 };      // 불투명 흰색
}

function ObstacleProximity({ distances }) {
  // distances: { front, frontLeft, frontRight, left, right }  단위: meters
  // 각 방향이 null 또는 Infinity면 안전한 것으로 간주
  const dists = distances || {};
  const dirs = ['left', 'frontLeft', 'front', 'frontRight', 'right'];

  // 각 방향별 시각화 계산
  const visuals = {};
  let maxLevel = 0;
  let nearestKey = null;
  let nearestDist = Infinity;
  dirs.forEach(k => {
    const v = distToVisual(dists[k]);
    visuals[k] = v;
    if (v.level > maxLevel) maxLevel = v.level;
    const d = dists[k];
    if (d != null && isFinite(d) && d < nearestDist) {
      nearestDist = d;
      nearestKey = k;
    }
  });

  const active = maxLevel > 0;
  const dirLabel = { front: '전방', frontLeft: '좌전방', frontRight: '우전방', left: '좌측', right: '우측' };
  const dirColor = maxLevel >= 3 ? '#E5484D' : maxLevel === 2 ? '#F97316' : '#F8FAFC';

  // SVG wedge: 휠체어 중심 5방향 부채꼴.
  //   ring 1(원거리, 80~100cm), ring 2(50~80cm), ring 3(<50cm)
  //   해당 방향 거리값이 ring 임계값 안쪽이면 그 ring이 점등됨
  const Wedge = ({ key_, startAngle, endAngle, ring }) => {
    const cx = 90, cy = 110;
    const radii = { 1: [78, 92], 2: [60, 76], 3: [42, 58] };
    const [r1, r2] = radii[ring];
    const toRad = (d) => (d - 90) * Math.PI / 180;
    const p1 = { x: cx + r2 * Math.cos(toRad(startAngle)), y: cy + r2 * Math.sin(toRad(startAngle)) };
    const p2 = { x: cx + r2 * Math.cos(toRad(endAngle)),   y: cy + r2 * Math.sin(toRad(endAngle)) };
    const p3 = { x: cx + r1 * Math.cos(toRad(endAngle)),   y: cy + r1 * Math.sin(toRad(endAngle)) };
    const p4 = { x: cx + r1 * Math.cos(toRad(startAngle)), y: cy + r1 * Math.sin(toRad(startAngle)) };
    const largeArc = endAngle - startAngle > 180 ? 1 : 0;
    const path = `M${p1.x},${p1.y} A${r2},${r2} 0 ${largeArc} 1 ${p2.x},${p2.y} L${p3.x},${p3.y} A${r1},${r1} 0 ${largeArc} 0 ${p4.x},${p4.y} Z`;

    const v = visuals[key_];
    const lit = v.active && v.level >= ring;
    // ring 1=흰, 2=주황, 3=빨강
    const ringColor = ring === 3 ? '#E5484D' : ring === 2 ? '#F97316' : '#F8FAFC';
    return (
      <path
        d={path}
        fill={lit ? ringColor : '#1E293B'}
        opacity={lit ? (ring === 1 ? 0.85 : 1) : 0.18}
        style={lit && ring >= 2 ? { animation: `obstaclePulse${ring} ${1 - ring * 0.2}s ease-in-out infinite` } : undefined}
      />
    );
  };

  return (
    <div style={{
      position: 'absolute', left: 16, bottom: 16, zIndex: 8,
      background: 'rgba(15,23,42,0.92)', backdropFilter: 'blur(6px)',
      padding: 14, borderRadius: 20,
      border: `1px solid ${active ? dirColor : 'rgba(148,163,184,0.25)'}`,
      boxShadow: active && maxLevel >= 3 ? `0 0 24px ${dirColor}88, 0 8px 24px rgba(0,0,0,0.3)` : '0 8px 24px rgba(0,0,0,0.25)',
      transition: 'border-color 0.3s, box-shadow 0.3s',
      fontFamily: TOKENS.font.sans,
      width: 220,
      animation: active && maxLevel >= 3 ? 'obstacleShake 0.4s ease-in-out infinite' : undefined,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <span style={{ fontSize: 11, fontWeight: 800, color: '#94A3B8', letterSpacing: 1.5 }}>주변 장애물</span>
        <span style={{ fontSize: 10, fontWeight: 700, color: active ? dirColor : '#64748B', padding: '2px 8px', borderRadius: 999, background: active ? `${dirColor}22` : 'rgba(148,163,184,0.12)' }}>
          {active ? '감지됨' : '안전'}
        </span>
      </div>
      <svg viewBox="0 0 180 140" width="100%" height="124" style={{ display: 'block' }}>
        {[3, 2, 1].map(ring => (
          <React.Fragment key={ring}>
            <Wedge key_="left"        startAngle={-100} endAngle={-60} ring={ring} />
            <Wedge key_="frontLeft"   startAngle={-60}  endAngle={-20} ring={ring} />
            <Wedge key_="front"       startAngle={-20}  endAngle={20}  ring={ring} />
            <Wedge key_="frontRight"  startAngle={20}   endAngle={60}  ring={ring} />
            <Wedge key_="right"       startAngle={60}   endAngle={100} ring={ring} />
          </React.Fragment>
        ))}
        {/* 휠체어 아이콘 (중심) */}
        <circle cx="90" cy="110" r="14" fill="#F8FAFC" stroke="#3B82F6" strokeWidth="2" />
        <path d="M84,108 L96,108 M85,113 L95,113" stroke="#3B82F6" strokeWidth="2" strokeLinecap="round" />
      </svg>
      <div style={{ marginTop: 4, display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
        <span style={{ fontSize: 13, fontWeight: 800, color: active ? dirColor : '#64748B' }}>
          {active ? `${dirLabel[nearestKey] || ''} 접근` : '주변 양호'}
        </span>
        {active && isFinite(nearestDist) && (
          <span style={{ fontSize: 14, fontWeight: 800, color: '#F8FAFC', fontVariantNumeric: 'tabular-nums' }}>
            {nearestDist.toFixed(2)}m
          </span>
        )}
      </div>
    </div>
  );
}