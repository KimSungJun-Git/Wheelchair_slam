const { useState: useS, useEffect: useE, useRef: useR, useMemo: useM } = React;

function LiveMap({ pose, history }) {
  const W = 900, H = 540;
  const all = [...history, pose].filter((p) => p && p.x != null);
  if (!all.length) {
    return <div className="live-map empty"><div className="empty-msg">위치 데이터 대기 중…</div></div>;
  }
  const xs = all.map((p) => p.x);
  const ys = all.map((p) => p.y);
  const minX = Math.min(...xs, -1.5);
  const maxX = Math.max(...xs, 1.5);
  const minY = Math.min(...ys, -1.5);
  const maxY = Math.max(...ys, 1.5);
  const padX = (maxX - minX) * 0.2 || 1;
  const padY = (maxY - minY) * 0.2 || 1;
  const x0 = minX - padX, x1 = maxX + padX;
  const y0 = minY - padY, y1 = maxY + padY;
  const proj = (x, y) => [
    ((x - x0) / (x1 - x0)) * W,
    H - ((y - y0) / (y1 - y0)) * H,
  ];
  const grid = [];
  for (let g = Math.ceil(x0); g <= Math.floor(x1); g++) {
    const [px] = proj(g, 0);
    grid.push(<line key={`gx${g}`} x1={px} y1={0} x2={px} y2={H} className="grid" />);
  }
  for (let g = Math.ceil(y0); g <= Math.floor(y1); g++) {
    const [, py] = proj(0, g);
    grid.push(<line key={`gy${g}`} x1={0} y1={py} x2={W} y2={py} className="grid" />);
  }
  const pathD = history
    .filter((p) => p.x != null)
    .map((p, i) => {
      const [x, y] = proj(p.x, p.y);
      return `${i === 0 ? "M" : "L"} ${x} ${y}`;
    })
    .join(" ");

  const cur = pose && pose.x != null ? proj(pose.x, pose.y) : null;

  return (
    <div className="live-map">
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet">
        <rect x="0" y="0" width={W} height={H} className="map-bg" />
        <g className="map-grid">{grid}</g>
        <path d={pathD} className="trail" />
        {cur && (
          <g transform={`translate(${cur[0]} ${cur[1]}) rotate(${(-(pose.yaw || 0) * 180) / Math.PI})`}>
            <circle r="22" className="robot-halo" />
            <circle r="14" className="robot-halo2" />
            <circle r="9" className="robot-core" />
            <path d="M 0 -16 L 7 0 L -7 0 Z" className="robot-arrow" />
          </g>
        )}
      </svg>
    </div>
  );
}

function eventTone(action) {
  if (action === "sos" || action === "blocked") return "critical";
  if (action === "modified") return "warning";
  return "info";
}

function eventLabel(action) {
  return ({ sos: "SOS", blocked: "비상정지", modified: "명령수정", allowed: "정상" }[action] || action);
}

function LivePage() {
  const [snap, setSnap] = useS(null);
  const [history, setHistory] = useS([]);
  const [confirmStop, setConfirmStop] = useS(false);
  const [stopped, setStopped] = useS(false);
  const seenRef = useR(new Set());

  useE(() => {
    let alive = true;
    const tick = async () => {
      const d = await window.Api.getLive();
      if (!alive) return;
      setSnap(d);
      if (d.pose && d.pose.x != null) {
        setHistory((h) => {
          const last = h[h.length - 1];
          if (last && last.x === d.pose.x && last.y === d.pose.y) return h;
          return [...h, d.pose].slice(-200);
        });
      }
    };
    tick();
    const t = setInterval(tick, 2000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  const events = snap?.events || [];

  const tagged = useM(() => {
    return events.map((e, i) => {
      const k = `${e.ts}|${e.action}|${e.reason_key}`;
      const isNew = !seenRef.current.has(k);
      if (isNew) seenRef.current.add(k);
      return { ...e, _key: k, _new: isNew && i < 5 };
    });
  }, [events]);

  if (!snap) return <div className="loading">실시간 데이터 연결 중…</div>;

  const zone = snap.zone || "—";
  const zoneTone = zone.includes("위험") ? "critical" : zone.includes("비상") ? "critical" : "ok";
  const mode = snap.mode || "auto";

  return (
    <div className="page live">
      <div className="live-grid">
        <div className="live-left card">
          <div className="card-head">
            <div>
              <div className="card-title">실시간 위치</div>
              <div className="card-sub">SLAM 좌표 갱신 (2Hz 폴링)</div>
            </div>
            <div className="live-badges">
              <div className={`badge ${mode === "auto" ? "ok" : "warn"}`}>
                <Icon name={mode === "auto" ? "Cpu" : "Hand"} size={12} />
                {mode === "auto" ? "자율주행" : "수동"}
              </div>
              <div className={`badge ${zoneTone}`}>
                <Icon name="Map" size={12} /> {zone}
              </div>
              <div className={`badge ${snap.connected ? "ok" : "danger"}`}>
                <span className={`pulse-dot ${snap.connected ? "ok" : "danger"}`} />
                {snap.connected ? "연결됨" : "끊김"}
              </div>
            </div>
          </div>
          <LiveMap pose={snap.pose} history={history} />
          <div className="live-readouts">
            <div className="ro"><div className="ro-l">x</div><div className="ro-v mono">{fmtNum(snap.pose?.x)}</div></div>
            <div className="ro"><div className="ro-l">y</div><div className="ro-v mono">{fmtNum(snap.pose?.y)}</div></div>
            <div className="ro"><div className="ro-l">yaw</div><div className="ro-v mono">{fmtNum(snap.pose?.yaw)} rad</div></div>
            <div className="ro"><div className="ro-l">선속도</div><div className="ro-v mono">{fmtNum(snap.velocity?.linear)} m/s</div></div>
            <div className="ro"><div className="ro-l">각속도</div><div className="ro-v mono">{fmtNum(snap.velocity?.angular)} rad/s</div></div>
          </div>
        </div>

        <div className="live-right">
          <div className="card stream-card">
            <div className="card-head">
              <div>
                <div className="card-title">이벤트 스트림</div>
                <div className="card-sub">최근 30건 · 신규는 위로 슬라이드</div>
              </div>
              <div className="muted-meta">{events.length}건</div>
            </div>
            <div className="stream">
              {tagged.length === 0 && <div className="empty-msg pad">대기 중…</div>}
              {tagged.map((e) => (
                <div key={e._key} className={`stream-item ${e._new ? "fresh" : ""}`}>
                  <span className={`stream-dot ${eventTone(e.action)}`} />
                  <div className="stream-body">
                    <div className="stream-row">
                      <span className={`stream-tag ${eventTone(e.action)}`}>{eventLabel(e.action)}</span>
                      <span className="stream-time">{fmtTime(e.ts)}</span>
                    </div>
                    <div className="stream-msg">{e.reason_label || "—"}</div>
                    {e.pose && e.pose.x != null && (
                      <div className="stream-meta mono">
                        x={fmtNum(e.pose.x)} y={fmtNum(e.pose.y)}{e.zone ? ` · ${e.zone}` : ""}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className={`stop-card ${stopped ? "stopped" : ""}`}>
            {!stopped ? (
              <button className="stop-btn" onClick={() => setConfirmStop(true)}>
                <div className="stop-icon">
                  <Icon name="Hand" size={28} strokeWidth={2.5} />
                </div>
                <div className="stop-text">
                  <div className="stop-title">원격 정지</div>
                  <div className="stop-sub">현재 주행 즉시 중단 · /sos_trigger 발행</div>
                </div>
              </button>
            ) : (
              <div className="stop-active">
                <Icon name="OctagonAlert" size={22} />
                <div>
                  <div className="stop-title">정지 명령 전송됨</div>
                  <div className="stop-sub">관제실 확인 대기 중…</div>
                </div>
                <button className="btn ghost sm" onClick={() => setStopped(false)}>해제</button>
              </div>
            )}
          </div>
        </div>
      </div>

      {confirmStop && (
        <div className="modal-back" onClick={() => setConfirmStop(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head danger">
              <Icon name="OctagonAlert" size={18} /> 원격 정지 확인
            </div>
            <div className="modal-body">
              <p>휠체어를 즉시 정지시킵니다. 사용자가 탑승 중이라면 충격이 발생할 수 있습니다.</p>
              <p className="mute small">조치: <span className="mono">/sos_trigger</span> 토픽으로 <span className="mono">"manual_stop"</span> 발행</p>
            </div>
            <div className="modal-foot">
              <button className="btn ghost" onClick={() => setConfirmStop(false)}>취소</button>
              <button className="btn danger" onClick={() => { setConfirmStop(false); setStopped(true); }}>
                <Icon name="Hand" size={14} /> 정지 실행
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function fmtNum(v) {
  if (v == null || Number.isNaN(v)) return "—";
  return Number(v).toFixed(2);
}
function fmtTime(ts) {
  if (!ts) return "—";
  const d = new Date(ts * 1000);
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

window.LivePage = LivePage;