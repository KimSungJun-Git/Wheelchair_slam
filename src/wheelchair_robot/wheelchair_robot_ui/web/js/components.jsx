// ─── 2. Shared UI Components ──────────────────────────────────────
function Icon({ name, size = 20, stroke = 1.8, color = 'currentColor', style }) {
  const paths = {
    home: <><path d="M3 10l9-7 9 7"/><path d="M5 9v11h14V9"/></>,
    map: <><path d="M9 4L3 6v14l6-2 6 2 6-2V4l-6 2-6-2z"/><path d="M9 4v14M15 6v14"/></>,
    search: <><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></>,
    battery: <><rect x="3" y="7" width="16" height="10" rx="2"/><path d="M21 10v4"/><rect x="5" y="9" width="10" height="6" fill="currentColor" stroke="none" rx="1"/></>,
    signal: <><path d="M4 20h2M9 20h2v-4M14 20h2v-8M19 20h2V6"/></>,
    chevronRight: <path d="M9 6l6 6-6 6"/>,
    chevronLeft: <path d="M15 6l-6 6 6 6"/>,
    arrowRight: <><path d="M5 12h14"/><path d="M13 5l7 7-7 7"/></>,
    pin: <><path d="M12 22s-7-7.5-7-13a7 7 0 0114 0c0 5.5-7 13-7 13z"/><circle cx="12" cy="9" r="2.5"/></>,
    play: <path d="M8 5v14l11-7z" fill="currentColor" stroke="none"/>,
    stop: <rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" stroke="none"/>,
    sos: <><circle cx="12" cy="12" r="9"/><path d="M8 10h2v4H8zM14 10h2v4h-2zM11 10h2v4h-2z" fill="currentColor" stroke="none"/></>,
    bed: <><path d="M3 10V6M21 18v-5a3 3 0 00-3-3H3M3 18h18"/><circle cx="8" cy="10" r="2"/></>,
    alert: <><path d="M12 3l10 18H2L12 3z"/><path d="M12 10v5M12 18v.5" stroke="#fff"/></>,
    leaf: <><path d="M11 20A7 7 0 014 13V4h9a7 7 0 010 14z"/><path d="M11 20c-3-5-3-9 0-13"/></>,
    check: <path d="M5 12l5 5 9-11"/>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, ...style }}>{paths[name]}</svg>;
}

function Pill({ tone = 'neutral', icon, children, size = 'md' }) {
  const C = TOKENS.color;
  const tones = { neutral: { bg: C.surfaceAlt, fg: C.inkDark }, primary: { bg: C.primarySoft, fg: C.primaryDark }, success: { bg: C.successSoft, fg: C.success }, warn: { bg: C.warnSoft, fg: '#8a6500' }, danger: { bg: C.dangerSoft, fg: C.danger } };
  const s = tones[tone] || tones.neutral;
  const pad = size === 'lg' ? '10px 16px' : size === 'sm' ? '4px 10px' : '6px 12px';
  return <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: pad, borderRadius: TOKENS.radius.pill, background: s.bg, color: s.fg, fontSize: size === 'lg'?16:14, fontWeight: 700 }}>{icon && <Icon name={icon} size={16} stroke={2.2} />} {children}</span>;
}

function Card({ children, style, pad = 20, onClick }) {
  return <div onClick={onClick} style={{ background: TOKENS.color.surface, borderRadius: TOKENS.radius.lg, boxShadow: TOKENS.shadow.sm, border: `1px solid ${TOKENS.color.line}`, padding: pad, ...style }}>{children}</div>;
}

function BigButton({ children, icon, tone = 'primary', onClick, subtitle }) {
  const C = TOKENS.color;
  const t = tone === 'primary' ? { bg: C.primary, fg: '#fff' } : tone === 'soft' ? { bg: C.primarySoft, fg: C.primaryDark } : { bg: C.surface, fg: C.ink, border: `2px solid ${C.line}` };
  return (
    <button onClick={onClick} style={{ display: 'flex', alignItems: 'center', gap: 14, background: t.bg, color: t.fg, border: t.border || 'none', borderRadius: TOKENS.radius.lg, padding: '22px 26px', fontSize: 22, fontWeight: 800, fontFamily: TOKENS.font.sans, cursor: 'pointer', width: '100%', textAlign: 'left', minHeight: 80 }} onMouseDown={e => e.currentTarget.style.transform='scale(0.98)'} onMouseUp={e => e.currentTarget.style.transform=''} onMouseLeave={e => e.currentTarget.style.transform=''}>
      {icon && <Icon name={icon} size={30} stroke={2.5} />}
      <span style={{ display: 'flex', flexDirection: 'column', gap: 3 }}><span>{children}</span>{subtitle && <span style={{ fontSize: 16, fontWeight: 600, opacity: 0.85 }}>{subtitle}</span>}</span>
    </button>
  );
}

function StatusBar() {
  return (
    <div style={{ height: 38, display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 18px', fontSize: 14, fontWeight: 700, color: TOKENS.color.primaryDark, background: 'rgba(255,255,255,0.85)', borderBottom: `1px solid ${TOKENS.color.line}` }}>
      <span>오후 2:34</span>
      <span style={{ display: 'flex', alignItems: 'center', gap: 10 }}><Icon name="signal" size={14} /><span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><Icon name="battery" size={18} /><span>78%</span></span></span>
    </div>
  );
}

function Frame({ children, bg }) {
  return <div style={{ width: 1024, height: 720, background: bg || TOKENS.color.bg, fontFamily: TOKENS.font.sans, color: TOKENS.color.ink, position: 'relative', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>{children}</div>;
}