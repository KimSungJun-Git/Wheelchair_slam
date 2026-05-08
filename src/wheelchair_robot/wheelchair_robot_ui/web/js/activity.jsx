// ─── 2.5 시스템 활동 로그 (Activity Log) ──────────────────────────
const ActivityContext = React.createContext(null);

function ActivityProvider({ children }) {
  const [activities, setActivities] = React.useState([]);
  const idRef = React.useRef(1);

  // status: 'active' | 'completed' | 'cancelled' | 'failed'
  const startActivity = React.useCallback((label, meta = {}) => {
    const id = idRef.current++;
    setActivities(prev => [{ id, label, status: 'active', startedAt: new Date(), endedAt: null, ...meta }, ...prev].slice(0, 50));
    return id;
  }, []);

  const updateActivity = React.useCallback((id, patch) => {
    setActivities(prev => prev.map(a => a.id === id
      ? { ...a, ...patch, endedAt: patch.status && patch.status !== 'active' ? new Date() : a.endedAt }
      : a));
  }, []);

  const completeActivity = React.useCallback((id, note) => updateActivity(id, { status: 'completed', note }), [updateActivity]);
  const cancelActivity   = React.useCallback((id, note) => updateActivity(id, { status: 'cancelled', note: note || '사용자 취소' }), [updateActivity]);
  const failActivity     = React.useCallback((id, note) => updateActivity(id, { status: 'failed', note }), [updateActivity]);

  const logEvent = React.useCallback((label, meta = {}) => {
    const id = idRef.current++;
    const now = new Date();
    setActivities(prev => [{ id, label, status: 'completed', startedAt: now, endedAt: now, ...meta }, ...prev].slice(0, 50));
    return id;
  }, []);

  const cancelAllActive = React.useCallback((note) => {
    setActivities(prev => prev.map(a => a.status === 'active'
      ? { ...a, status: 'cancelled', note: note || '사용자 취소', endedAt: new Date() }
      : a));
  }, []);

  const clearAll = React.useCallback(() => setActivities([]), []);

  const value = { activities, startActivity, updateActivity, completeActivity, cancelActivity, failActivity, logEvent, cancelAllActive, clearAll };
  return <ActivityContext.Provider value={value}>{children}</ActivityContext.Provider>;
}

const useActivity = () => React.useContext(ActivityContext);

function fmtTime(d) {
  const h = String(d.getHours()).padStart(2, '0');
  const m = String(d.getMinutes()).padStart(2, '0');
  const s = String(d.getSeconds()).padStart(2, '0');
  return `${h}:${m}:${s}`;
}
function fmtDuration(start, end) {
  const ms = (end || new Date()) - start;
  if (ms < 1000) return `${ms}ms`;
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${s % 60}s`;
}

function StatusDot({ status }) {
  const C = TOKENS.color;
  const map = {
    active:    { bg: C.accent,   ring: 'rgba(59,130,246,0.25)', pulse: true },
    completed: { bg: C.success,  ring: 'rgba(16,165,113,0.18)', pulse: false },
    cancelled: { bg: C.inkFaint, ring: 'rgba(100,116,139,0.18)', pulse: false },
    failed:    { bg: C.danger,   ring: 'rgba(229,72,77,0.2)',   pulse: false },
  };
  const s = map[status] || map.completed;
  return (
    <span style={{ position: 'relative', width: 10, height: 10, display: 'inline-block', flexShrink: 0 }}>
      {s.pulse && <span style={{ position: 'absolute', inset: -6, borderRadius: '50%', background: s.ring, animation: 'actPulse 1.4s ease-out infinite' }} />}
      <span style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: s.bg, boxShadow: `0 0 0 3px ${s.ring}` }} />
    </span>
  );
}

const STATUS_LABEL = {
  active:    { ko: '진행 중' },
  completed: { ko: '완료' },
  cancelled: { ko: '취소됨' },
  failed:    { ko: '실패' },
};

function ActivityRow({ entry, onCancel, now }) {
  const C = TOKENS.color;
  const isActive = entry.status === 'active';
  const isCancelled = entry.status === 'cancelled';
  const isFailed = entry.status === 'failed';
  const borderColor = isActive ? C.accent : isCancelled ? C.inkFaint : isFailed ? C.danger : C.success;
  const pillBg = isActive ? C.primarySoft : isCancelled ? '#E2E8F0' : isFailed ? C.dangerSoft : C.successSoft;
  const pillFg = isActive ? C.primaryDark : isCancelled ? C.inkFaint : isFailed ? C.danger : '#0a6b4a';
  return (
    <div style={{
      display: 'flex', gap: 12, padding: '12px 14px',
      background: isActive ? 'rgba(59,130,246,0.06)' : C.surface,
      borderLeft: `3px solid ${borderColor}`,
      borderRadius: 10,
      opacity: isCancelled ? 0.78 : 1,
    }}>
      <div style={{ paddingTop: 5 }}><StatusDot status={entry.status} /></div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'baseline' }}>
          <div style={{ fontSize: 14, fontWeight: 800, color: C.primaryDark, textDecoration: isCancelled ? 'line-through' : 'none' }}>{entry.label}</div>
          <div style={{ fontSize: 11, color: C.inkFaint, fontWeight: 700, fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>{fmtTime(entry.startedAt)}</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 11, fontWeight: 800, padding: '2px 8px', borderRadius: 999, background: pillBg, color: pillFg }}>{STATUS_LABEL[entry.status].ko}</span>
          <span style={{ fontSize: 11, color: C.inkFaint, fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
            {isActive ? `+${fmtDuration(entry.startedAt, now)}` : fmtDuration(entry.startedAt, entry.endedAt)}
          </span>
          {entry.note && !isActive && (
            <span style={{ fontSize: 11, color: C.inkFaint, fontWeight: 600 }}>· {entry.note}</span>
          )}
          {isActive && onCancel && (
            <button onClick={() => onCancel(entry.id)} style={{
              marginLeft: 'auto', padding: '3px 10px', fontSize: 11, fontWeight: 800,
              background: C.surface, color: C.danger, border: `1.5px solid ${C.dangerSoft}`,
              borderRadius: 999, cursor: 'pointer', fontFamily: 'inherit',
            }}>취소</button>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── 2.6 확인 다이얼로그 ──────────────────────────────────────────
function ConfirmDialog({ open, title, message, confirmText = '확인', cancelText = '취소', tone = 'primary', onConfirm, onCancel }) {
  if (!open) return null;
  const C = TOKENS.color;
  const confirmBg = tone === 'danger' ? C.danger : C.primary;
  return (
    <div style={{
      position: 'absolute', inset: 0, zIndex: 100,
      background: 'rgba(0,47,108,0.45)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      backdropFilter: 'blur(4px)', fontFamily: TOKENS.font.sans,
    }}>
      <div style={{
        width: 460, background: C.surface, borderRadius: 24,
        boxShadow: '0 24px 64px rgba(0,47,108,0.35)',
        padding: 32, display: 'flex', flexDirection: 'column', gap: 16,
      }}>
        <div style={{ fontSize: 24, fontWeight: 800, color: C.primaryDark, letterSpacing: -0.3 }}>{title}</div>
        <div style={{ fontSize: 17, color: C.inkMuted, fontWeight: 600, lineHeight: 1.5 }}>{message}</div>
        <div style={{ display: 'flex', gap: 12, marginTop: 8 }}>
          <button onClick={onCancel} style={{
            flex: 1, padding: '18px', borderRadius: 16, border: `2px solid ${C.line}`,
            background: C.surface, color: C.primaryDark, fontSize: 18, fontWeight: 800,
            cursor: 'pointer', fontFamily: 'inherit',
          }}>{cancelText}</button>
          <button onClick={onConfirm} style={{
            flex: 1.3, padding: '18px', borderRadius: 16, border: 'none',
            background: confirmBg, color: '#fff', fontSize: 18, fontWeight: 800,
            cursor: 'pointer', fontFamily: 'inherit',
            boxShadow: tone === 'danger' ? '0 8px 16px rgba(229,72,77,0.25)' : '0 8px 16px rgba(0,71,171,0.25)',
          }}>{confirmText}</button>
        </div>
      </div>
    </div>
  );
}

function ActivityPanel({ onStop }) {
  const C = TOKENS.color;
  const ctx = useActivity();
  const [open, setOpen] = React.useState(false);
  const [filter, setFilter] = React.useState('all');
  const [now, setNow] = React.useState(Date.now());

  const hasActive = ctx.activities.some(a => a.status === 'active');
  React.useEffect(() => {
    if (!hasActive) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [hasActive]);

  const counts = React.useMemo(() => {
    const c = { all: ctx.activities.length, active: 0, completed: 0, cancelled: 0, failed: 0 };
    ctx.activities.forEach(a => { c[a.status] = (c[a.status] || 0) + 1; });
    return c;
  }, [ctx.activities]);

  const visible = ctx.activities.filter(a => filter === 'all' ? true : a.status === filter);

  // 현재 상태 한 줄: 가장 최근 active 항목, 없으면 가장 최근 항목
  const currentEntry = ctx.activities.find(a => a.status === 'active') || ctx.activities[0];
  const statusText = currentEntry
    ? (currentEntry.status === 'active'
        ? `${currentEntry.label}  ·  +${fmtDuration(currentEntry.startedAt, now)}`
        : `${currentEntry.label}  ·  ${STATUS_LABEL[currentEntry.status].ko}`)
    : '대기 중';

  const TabBtn = ({ k, label }) => (
    <button onClick={() => setFilter(k)} style={{
      padding: '6px 11px', fontSize: 12, fontWeight: 800,
      background: filter === k ? C.primary : 'transparent',
      color: filter === k ? '#fff' : C.inkMuted,
      border: 'none', borderRadius: 999, cursor: 'pointer', fontFamily: 'inherit',
      display: 'flex', alignItems: 'center', gap: 5,
    }}>
      {label}
      <span style={{
        fontSize: 10.5, fontWeight: 800, padding: '1px 6px', borderRadius: 999,
        background: filter === k ? 'rgba(255,255,255,0.25)' : '#E2E8F0',
        color: filter === k ? '#fff' : C.inkMuted,
        fontVariantNumeric: 'tabular-nums', minWidth: 16, textAlign: 'center',
      }}>{counts[k] || 0}</span>
    </button>
  );

  // 미니마이즈 모드: 화면 하단 좌측 한 줄, 우측에 노출되는 정지·홈·기타 버튼 가리지 않도록 좌측 정렬
  if (!open) {
    return (
      <div style={{
        position: 'absolute', right: 16, top: 50, zIndex: 60,
        maxWidth: 360,
        background: 'rgba(255,255,255,0.97)',
        backdropFilter: 'blur(8px)',
        border: `1px solid ${C.line}`,
        borderRadius: 999,
        boxShadow: '0 8px 24px rgba(0,47,108,0.18)',
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '8px 14px 8px 12px',
        fontFamily: TOKENS.font.sans,
        cursor: 'pointer',
      }} onClick={() => setOpen(true)}>
        <span style={{ position: 'relative', width: 10, height: 10, flexShrink: 0 }}>
          <span style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: hasActive ? C.accent : C.success }} />
          {hasActive && <span style={{ position: 'absolute', inset: -4, borderRadius: '50%', background: 'rgba(59,130,246,0.3)', animation: 'actPulse 1.4s ease-out infinite' }} />}
        </span>
        <span style={{
          fontSize: 13, fontWeight: 800,
          color: hasActive ? C.primaryDark : C.inkMuted,
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          fontVariantNumeric: 'tabular-nums',
        }}>
          {statusText}
        </span>
        <span style={{
          marginLeft: 4, padding: '3px 9px', fontSize: 11, fontWeight: 800,
          background: C.surfaceAlt, color: C.primaryDark, borderRadius: 999,
          flexShrink: 0,
        }}>로그 열기</span>
      </div>
    );
  }

  return (
    <div style={{
      position: 'absolute', right: 16, top: 50, zIndex: 60,
      width: 360,
      background: 'rgba(255,255,255,0.98)',
      backdropFilter: 'blur(8px)',
      border: `1px solid ${C.line}`,
      borderRadius: 18,
      boxShadow: '0 16px 40px rgba(0,47,108,0.22)',
      overflow: 'hidden',
      fontFamily: TOKENS.font.sans,
      maxHeight: 460,
      display: 'flex', flexDirection: 'column',
    }}>
      <div onClick={() => setOpen(false)} style={{
        padding: '12px 14px', display: 'flex', alignItems: 'center', gap: 10,
        cursor: 'pointer',
        borderBottom: `1px solid ${C.line}`,
        background: C.surface,
      }}>
        <span style={{ position: 'relative', width: 10, height: 10 }}>
          <span style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: hasActive ? C.accent : C.success }} />
          {hasActive && <span style={{ position: 'absolute', inset: -4, borderRadius: '50%', background: 'rgba(59,130,246,0.3)', animation: 'actPulse 1.4s ease-out infinite' }} />}
        </span>
        <span style={{ fontSize: 14, fontWeight: 800, color: C.primaryDark }}>시스템 활동</span>
        {hasActive ? (
          <span style={{ fontSize: 11, fontWeight: 800, color: C.primaryDark, padding: '2px 8px', background: C.primarySoft, borderRadius: 999 }}>
            {counts.active}건 진행 중
          </span>
        ) : (
          <span style={{ fontSize: 11, fontWeight: 700, color: C.inkFaint }}>대기</span>
        )}
        <span style={{ marginLeft: 'auto', color: C.inkMuted, fontSize: 16, fontWeight: 700 }}>−</span>
      </div>

      <div style={{ padding: '8px 10px', display: 'flex', alignItems: 'center', gap: 4, borderBottom: `1px solid ${C.line}`, background: '#F8FAFC', overflowX: 'auto', flexShrink: 0 }}>
        <TabBtn k="all" label="전체" />
        <TabBtn k="active" label="진행" />
        <TabBtn k="completed" label="완료" />
        <TabBtn k="cancelled" label="취소" />
        {counts.failed > 0 && <TabBtn k="failed" label="실패" />}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 4 }}>
          {hasActive && (
            <button onClick={(e) => { e.stopPropagation(); ctx.cancelAllActive(); }} style={{
              padding: '5px 10px', fontSize: 11, fontWeight: 800,
              background: C.surface, color: C.danger, border: `1.5px solid ${C.dangerSoft}`,
              borderRadius: 999, cursor: 'pointer', fontFamily: 'inherit',
            }}>모두 중지</button>
          )}
          <button onClick={(e) => { e.stopPropagation(); ctx.clearAll(); }} style={{
            padding: '5px 10px', fontSize: 11, fontWeight: 800,
            background: 'transparent', color: C.inkMuted, border: `1.5px solid ${C.line}`,
            borderRadius: 999, cursor: 'pointer', fontFamily: 'inherit',
          }}>지우기</button>
        </div>
      </div>

      <div style={{ overflowY: 'auto', padding: 10, display: 'flex', flexDirection: 'column', gap: 8, flex: 1 }}>
        {visible.length === 0 ? (
          <div style={{ padding: '32px 16px', textAlign: 'center', color: C.inkFaint, fontSize: 13, fontWeight: 600 }}>
            아직 기록된 동작이 없습니다.
          </div>
        ) : (
          visible.map(entry => (
            <ActivityRow key={entry.id} entry={entry} now={now} onCancel={ctx.cancelActivity} />
          ))
        )}
      </div>
    </div>
  );
}