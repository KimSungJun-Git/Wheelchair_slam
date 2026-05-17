const { useState: useS, useEffect: useE, useRef: useR, useMemo: useM } = React;

function LiveMap({ pose, history, lang = "ko" }) {
  const W = 900, H = 540;
  const all = [...history, pose].filter((p) => p && p.x != null);
  if (!all.length) {
    return <div className="live-map empty"><div className="empty-msg">{window.dict[lang].lv_wait}</div></div>;
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

function eventLabel(action, lang = "ko") {
  return ({ sos: "SOS", blocked: window.dict[lang].reports_kpi_estop, modified: window.dict[lang].reports_kpi_cmd, allowed: window.dict[lang].reports_level_normal }[action] || action);
}

function LivePage({ lang = "ko" }) {
  const [snap, setSnap] = useS(null);
  const [history, setHistory] = useS([]);
  const [confirmStop, setConfirmStop] = useS(false);
  const [stopped, setStopped] = useS(false);
  const seenRef = useR(new Set());
  
  const [analyzing, setAnalyzing] = useS(false);

  const handleEndSession = async () => {
    if (confirm(window.dict[lang].lv_end_confirm)) {
      setAnalyzing(true);
      try {
        const res = await fetch(`http://${window.location.hostname}:8090/api/analyze_session`, { method: 'POST' });
        if (!res.ok) throw new Error("API error");
        alert(window.dict[lang].lv_end_success);
      } catch (e) {
        alert(window.dict[lang].lv_end_fail);
      }
      setAnalyzing(false);
    }
  };

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

  if (!snap) return <div className="loading">{window.dict[lang].lv_loading}</div>;

  const zone = snap.zone || "—";
  const zoneTone = zone.includes("위험") ? "critical" : zone.includes("비상") ? "critical" : "ok";
  const mode = snap.mode || "auto";

  return (
    <div className="page live">
      <div className="live-grid">
        <div className="live-left card">
          <div className="card-head">
            <div>
              <div className="card-title">{window.dict[lang].lv_loc_title}</div>
              <div className="card-sub">{window.dict[lang].lv_loc_sub}</div>
            </div>
            <div className="live-badges">
              <div className={`badge ${mode === "auto" ? "ok" : "warn"}`}>
                <Icon name={mode === "auto" ? "Cpu" : "Hand"} size={12} />
                {mode === "auto" ? window.dict[lang].ov_auto : window.dict[lang].ov_manual}
              </div>
              <div className={`badge ${zoneTone}`}>
                <Icon name="Map" size={12} /> {zone}
              </div>
              <div className={`badge ${snap.connected ? "ok" : "danger"}`}>
                <span className={`pulse-dot ${snap.connected ? "ok" : "danger"}`} />
                {snap.connected ? window.dict[lang].lv_conn : window.dict[lang].lv_disconn}
              </div>
            </div>
          </div>
          <LiveMap pose={snap.pose} history={history} lang={lang} />
          <div className="live-readouts">
            <div className="ro"><div className="ro-l">x</div><div className="ro-v mono">{fmtNum(snap.pose?.x)}</div></div>
            <div className="ro"><div className="ro-l">y</div><div className="ro-v mono">{fmtNum(snap.pose?.y)}</div></div>
            <div className="ro"><div className="ro-l">yaw</div><div className="ro-v mono">{fmtNum(snap.pose?.yaw)} rad</div></div>
            <div className="ro"><div className="ro-l">{window.dict[lang].lv_linear_vel}</div><div className="ro-v mono">{fmtNum(snap.velocity?.linear)} m/s</div></div>
            <div className="ro"><div className="ro-l">{window.dict[lang].lv_angular_vel}</div><div className="ro-v mono">{fmtNum(snap.velocity?.angular)} rad/s</div></div>
          </div>
        </div>

        <div className="live-right">
          {/* 이벤트 스트림 */}
          <div className="card stream-card">
            <div className="card-head">
              <div>
                <div className="card-title">{window.dict[lang].lv_stream_title}</div>
                <div className="card-sub">{window.dict[lang].lv_stream_sub}</div>
              </div>
              <div className="muted-meta">{events.length}{window.dict[lang].lv_count}</div>
            </div>
            <div className="stream">
              {tagged.length === 0 && <div className="empty-msg pad">{window.dict[lang].lv_standby}</div>}
              {tagged.map((e) => (
                <div key={e._key} className={`stream-item ${e._new ? "fresh" : ""}`}>
                  <span className={`stream-dot ${eventTone(e.action)}`} />
                  <div className="stream-body">
                    <div className="stream-row">
                      <span className={`stream-tag ${eventTone(e.action)}`}>{eventLabel(e.action, lang)}</span>
                      <span className="stream-time">{fmtTime(e.ts)}</span>
                    </div>
                    <div className="stream-msg">{e.reason_key ? (window.dict[lang][`reason_${e.reason_key}`] || e.reason_label) : (e.reason_label || "—")}</div>
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

          {/* 일과 마감 및 AI 분석 버튼 카드 */}
          <div className="card" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '12px', marginBottom: '12px' }}>
            <button 
              className="btn primary" 
              style={{ width: '100%', padding: '14px', fontSize: '15px', justifyContent: 'center' }} 
              onClick={handleEndSession}
              disabled={analyzing}
            >
              {analyzing ? window.dict[lang].lv_end_req : window.dict[lang].lv_end_btn}
            </button>
            <div className="muted-meta" style={{ textAlign: 'center', fontSize: '12px' }}>
              {window.dict[lang].lv_end_desc}
            </div>
          </div>

          {/* 원격 정지 (stop-card) */}
          <div className={`stop-card ${stopped ? "stopped" : ""}`}>
            {!stopped ? (
              <button className="stop-btn" onClick={() => setConfirmStop(true)}>
                <div className="stop-icon">
                  <Icon name="Hand" size={28} strokeWidth={2.5} />
                </div>
                <div className="stop-text">
                  <div className="stop-title">{window.dict[lang].lv_stop_title}</div>
                  <div className="stop-sub">{window.dict[lang].lv_stop_sub}</div>
                </div>
              </button>
            ) : (
              <div className="stop-active">
                <Icon name="OctagonAlert" size={22} />
                <div>
                  <div className="stop-title">{window.dict[lang].lv_stop_sent}</div>
                  <div className="stop-sub">{window.dict[lang].lv_stop_wait}</div>
                </div>
                <button className="btn ghost sm" onClick={() => {
                  setStopped(false);
                  if (window.ros && window.ROSLIB) {
                    const modePub = new window.ROSLIB.Topic({
                      ros: window.ros, name: '/mode_switch', messageType: 'std_msgs/String'
                    });
                    modePub.publish(new window.ROSLIB.Message({ data: 'a' }));
                  }
                }}>{window.dict[lang].lv_release}</button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 원격 정지 모달 */}
      {confirmStop && (
        <div className="modal-back" onClick={() => setConfirmStop(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head danger">
              <Icon name="OctagonAlert" size={18} /> {window.dict[lang].lv_stop_confirm}
            </div>
            <div className="modal-body">
              <p>{window.dict[lang].lv_stop_msg1}</p>
              <p className="mute small">{window.dict[lang].lv_stop_msg2}</p>
            </div>
            <div className="modal-foot">
              <button className="btn ghost" onClick={() => setConfirmStop(false)}>{window.dict[lang].lv_cancel}</button>
              <button className="btn danger" onClick={() => { 
                setConfirmStop(false); 
                setStopped(true); 
                if (window.ros && window.ROSLIB) {
                  const sosPub = new window.ROSLIB.Topic({
                    ros: window.ros, name: '/sos_trigger', messageType: 'std_msgs/String'
                  });
                  sosPub.publish(new window.ROSLIB.Message({ data: 'manual_stop' }));
                }
              }}>
                <Icon name="Hand" size={14} /> {window.dict[lang].lv_execute}
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