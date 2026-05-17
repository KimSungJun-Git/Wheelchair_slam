const { useState: useS, useEffect: useE, useRef: useR, useMemo: useM } = React;

function LiveMap({ pose, history, lang }) {
  const W = 900, H = 540;
  const all = [...history, pose].filter((p) => p && p.x != null);
  if (!all.length) {
    return <div className="live-map empty"><div className="empty-msg">{dict[lang].live_pose_waiting}</div></div>;
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

function eventLabel(action, lang) {
  const map = {
    sos: dict[lang].live_tag_sos,
    blocked: dict[lang].live_tag_blocked,
    modified: dict[lang].live_tag_modified,
    allowed: dict[lang].live_tag_allowed,
  };
  return map[action] || action;
}

function LivePage({ lang }) {
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

  if (!snap) return <div className="loading">{dict[lang].live_loading}</div>;

  const zone = snap.zone || "—";
  const zoneTone = zone.includes("위험") ? "critical" : zone.includes("비상") ? "critical" : "ok";
  const mode = snap.mode || "auto";

  return (
    <div className="page live">
      <div className="live-grid">
        <div className="live-left card">
          <div className="card-head">
            <div>
              <div className="card-title">{dict[lang].live_title}</div>
              <div className="card-sub">{dict[lang].live_sub}</div>
            </div>
            <div className="live-badges">
              <div className={`badge ${mode === "auto" ? "ok" : "warn"}`}>
                <Icon name={mode === "auto" ? "Cpu" : "Hand"} size={12} />
                {mode === "auto" ? dict[lang].live_mode_auto : dict[lang].live_mode_manual}
              </div>
              <div className={`badge ${zoneTone}`}>
                <Icon name="Map" size={12} /> {zone}
              </div>
              <div className={`badge ${snap.connected ? "ok" : "danger"}`}>
                <span className={`pulse-dot ${snap.connected ? "ok" : "danger"}`} />
                {snap.connected ? dict[lang].live_connected : dict[lang].live_disconnected}
              </div>
            </div>
          </div>
          <LiveMap pose={snap.pose} history={history} lang={lang} />
          <div className="live-readouts">
            <div className="ro"><div className="ro-l">x</div><div className="ro-v mono">{fmtNum(snap.pose?.x)}</div></div>
            <div className="ro"><div className="ro-l">y</div><div className="ro-v mono">{fmtNum(snap.pose?.y)}</div></div>
            <div className="ro"><div className="ro-l">yaw</div><div className="ro-v mono">{fmtNum(snap.pose?.yaw)} rad</div></div>
            <div className="ro"><div className="ro-l">{dict[lang].live_vel_linear}</div><div className="ro-v mono">{fmtNum(snap.velocity?.linear)} m/s</div></div>
            <div className="ro"><div className="ro-l">{dict[lang].live_vel_angular}</div><div className="ro-v mono">{fmtNum(snap.velocity?.angular)} rad/s</div></div>
          </div>
        </div>

        <div className="live-right">
          <div className="card stream-card">
            <div className="card-head">
              <div>
                <div className="card-title">{dict[lang].live_stream_title}</div>
                <div className="card-sub">{dict[lang].live_stream_sub}</div>
              </div>
              <div className="muted-meta">{events.length}{dict[lang].live_count_suffix}</div>
            </div>
            <div className="stream">
              {tagged.length === 0 && <div className="empty-msg pad">{dict[lang].live_stream_idle}</div>}
              {tagged.map((e) => (
                <div key={e._key} className={`stream-item ${e._new ? "fresh" : ""}`}>
                  <span className={`stream-dot ${eventTone(e.action)}`} />
                  <div className="stream-body">
                    <div className="stream-row">
                      <span className={`stream-tag ${eventTone(e.action)}`}>{eventLabel(e.action, lang)}</span>
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
                  <div className="stop-title">{dict[lang].live_remote_stop}</div>
                  <div className="stop-sub">{dict[lang].live_remote_stop_sub}</div>
                </div>
              </button>
            ) : (
              <div className="stop-active">
                <Icon name="OctagonAlert" size={22} />
                <div>
                  <div className="stop-title">{dict[lang].live_stop_sent}</div>
                  <div className="stop-sub">{dict[lang].live_stop_wait}</div>
                </div>
                <button className="btn ghost sm" onClick={() => setStopped(false)}>{dict[lang].live_stop_release}</button>
              </div>
            )}
          </div>
        </div>
      </div>

      {confirmStop && (
        <div className="modal-back" onClick={() => setConfirmStop(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head danger">
              <Icon name="OctagonAlert" size={18} /> {dict[lang].live_confirm_title}
            </div>
            <div className="modal-body">
              <p>{dict[lang].live_confirm_body}</p>
              <p className="mute small">{dict[lang].live_confirm_action}</p>
            </div>
            <div className="modal-foot">
              <button className="btn ghost" onClick={() => setConfirmStop(false)}>{dict[lang].common_cancel}</button>
              <button className="btn danger" onClick={() => {
                  setConfirmStop(false);
                  setStopped(true);
                  fetch('http://localhost:8090/api/remote_stop', { method: 'POST' });
                }}>
                  <Icon name="Hand" size={14} /> {dict[lang].live_confirm_execute}
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