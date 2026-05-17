const { useState: useStateR, useEffect: useEffectR, useMemo: useMemoR } = React;

function ConfidenceBar({ value, size = "lg", lang }) {
  if (value == null) return <div className="conf-empty">{dict[lang || "ko"].reports_conf_unknown}</div>;
  const tone = value >= 80 ? "ok" : value >= 50 ? "warn" : "danger";
  return (
    <div className={`conf-block ${size}`}>
      <div className="conf-row">
        <span className="conf-num">{value}<span className="conf-pct">%</span></span>
        <span className={`conf-grade ${tone}`}>{value >= 80 ? dict[lang || "ko"].overview_conf_good : value >= 50 ? dict[lang || "ko"].overview_conf_ok : dict[lang || "ko"].overview_conf_low}</span>
      </div>
      <div className="conf-track">
        <div className={`conf-fill ${tone}`} style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

function ReportCard({ r, active, onClick, lang }) {
  const counts = r.counts || {};
  const critical = (counts.blocked || 0) + (counts.sos || 0);
  const warning = counts.modified || 0;
  return (
    <button className={`rep-card ${active ? "active" : ""}`} onClick={onClick}>
      <div className="rep-card-row">
        <div className="rep-date">{fmtDate(r.started_at)}</div>
        <div className={`rep-level ${critical > 0 ? "critical" : warning > 0 ? "warning" : "info"}`}>
          {critical > 0 ? dict[lang].reports_level_critical : warning > 0 ? dict[lang].reports_level_warning : dict[lang].reports_level_normal}
        </div>
      </div>
      <div className="rep-id">{r.filename}</div>
      <div className="rep-card-row sm">
        <ConfidenceBar value={r.confidence} size="sm" lang={lang} />
      </div>
      <div className="rep-meta">
        <span><Icon name="AlertOctagon" size={12} /> {critical}</span>
        <span><Icon name="AlertTriangle" size={12} /> {warning}</span>
        <span><Icon name="Database" size={12} /> {r.total}</span>
        <span className="dur">{Math.round(r.duration_sec)}s</span>
      </div>
    </button>
  );
}

function ReportsPage({lang}) {
  const [list, setList] = useStateR([]);
  const [selectedId, setSelectedId] = useStateR(null);
  const [detail, setDetail] = useStateR(null);
  const [showRaw, setShowRaw] = useStateR(false);
  const [filter, setFilter] = useStateR({ severity: "all", minConf: 0, q: "" });
  const [shareOpen, setShareOpen] = useStateR(false);

  const [deepStatus, setDeepStatus] = useStateR(null);

  const runDeepAnalyze = async () => {
    setDeepStatus({ status: 'starting' });
    try {
      const res = await fetch('http://localhost:8090/api/deep_analyze', { method: 'POST' });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        setDeepStatus({ status: 'error', error: errData.detail || dict[lang].deep_error_default });
        return;
      }
      
      const data = await res.json();
      const { job_id, target } = data;
      setDeepStatus({ status: 'running', target });
      
      const poll = setInterval(async () => {
        const statusRes = await fetch(`http://localhost:8090/api/deep_analyze/${job_id}`);
        const statusData = await statusRes.json();
        
        if (statusData.status === 'done') {
          clearInterval(poll);
          setDeepStatus({ status: 'done', ok: statusData.ok, target: statusData.target });
          
          // 분석 완료 후 최신 보고서 목록을 다시 불러옵니다
          window.Api.getReports().then((d) => setList(d.reports || []));
          
        } else if (statusData.status === 'error' || statusData.status === 'timeout') {
          clearInterval(poll);
          setDeepStatus({ status: 'error', error: statusData.error });
        }
      }, 5000);
      
    } catch (error) {
      setDeepStatus({ status: 'error', error: error.message });
    }
  };

  useEffectR(() => {
    window.Api.getReports().then((d) => {
      setList(d.reports || []);
      if (d.reports?.[0]) setSelectedId(d.reports[0].id);
    });
  }, []);

  useEffectR(() => {
    if (!selectedId) return;
    setDetail(null);
    setShowRaw(false);
    window.Api.getReport(selectedId).then(setDetail);
  }, [selectedId]);

  const filtered = useMemoR(() => {
    return list.filter((r) => {
      const c = r.counts || {};
      const critical = (c.blocked || 0) + (c.sos || 0);
      const warning = c.modified || 0;
      if (filter.severity === "critical" && critical === 0) return false;
      if (filter.severity === "warning" && warning === 0) return false;
      if ((r.confidence ?? 0) < filter.minConf) return false;
      if (filter.q && !r.filename.toLowerCase().includes(filter.q.toLowerCase())) return false;
      return true;
    });
  }, [list, filter]);

  return (
    <div className="page reports">
      <div className="rep-grid">
        <div className="rep-left">
          <div style={{ padding: '16px', borderBottom: '1px solid #e5e7eb', backgroundColor: '#f8fafc' }}>
            <button 
              className="btn primary" 
              onClick={runDeepAnalyze}
              disabled={deepStatus?.status === 'running' || deepStatus?.status === 'starting'}
              style={{ width: '100%', justifyContent: 'center' }}
            >
              🤖 {dict[lang].btn_deep_analyze}
            </button>
            
            
            {deepStatus && (
              <div style={{ marginTop: '10px', fontSize: '13px', fontWeight: '500' }}>
                {deepStatus.status === 'starting' && <span style={{color: '#d97706'}}>{dict[lang].deep_starting}</span>}
                {deepStatus.status === 'running' && <span style={{color: '#2563eb'}}>{dict[lang].deep_running} ({deepStatus.target})</span>}
                {deepStatus.status === 'done' && <span style={{color: '#16a34a'}}>{dict[lang].deep_done}</span>}
                {deepStatus.status === 'error' && <span style={{color: '#dc2626'}}>{dict[lang].deep_failed} {deepStatus.error}</span>}
              </div>
            )}
          </div>
          <div className="rep-filters">
            <div className="filter-row">
              <Icon name="Search" size={14} className="search-icon" />
              <input
                className="search-input"
                placeholder={dict[lang].reports_search}
                value={filter.q}
                onChange={(e) => setFilter({ ...filter, q: e.target.value })}
              />
            </div>
            <div className="filter-row seg">
              {[
                ["all", dict[lang].reports_filter_all],
                ["critical", dict[lang].reports_filter_critical],
                ["warning", dict[lang].reports_filter_warning],
              ].map(([k, l]) => (
                <button
                  key={k}
                  className={`seg-btn ${filter.severity === k ? "active" : ""}`}
                  onClick={() => setFilter({ ...filter, severity: k })}
                >
                  {l}
                </button>
              ))}
            </div>
            <div className="filter-row col">
              <div className="slider-head">
                <span>{dict[lang].reports_conf_gte}</span>
                <span className="mono">{filter.minConf}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                step="5"
                value={filter.minConf}
                onChange={(e) => setFilter({ ...filter, minConf: +e.target.value })}
              />
            </div>
            <div className="filter-stat">
              {filtered.length} / {list.length}{dict[lang].reports_shown_count}
            </div>
          </div>

          <div className="rep-list">
            {filtered.map((r) => (
              <ReportCard key={r.id} r={r} active={r.id === selectedId} onClick={() => setSelectedId(r.id)} lang={lang} />
            ))}
            {!filtered.length && <div className="empty-msg pad">{dict[lang].reports_empty}</div>}
          </div>
        </div>

        <div className="rep-right">
          {!detail ? (
            <div className="loading">{dict[lang].reports_loading}</div>
          ) : (
            <ReportDetail
              report={detail}
              showRaw={showRaw}
              setShowRaw={setShowRaw}
              shareOpen={shareOpen}
              setShareOpen={setShareOpen}
              lang={lang}
            />
          )}
        </div>
      </div>
    </div>
  );
}

function ReportDetail({ report, showRaw, setShowRaw, shareOpen, setShareOpen, lang }) {
  const counts = report.counts || {};
  const critical = (counts.blocked || 0) + (counts.sos || 0);
  const warning = counts.modified || 0;
  const sev = critical > 0 ? "critical" : warning > 0 ? "warning" : "info";

  const md = report.markdown || "";
  // Strip the AI confidence row from the table for prettier render (we surface it big)
  const cleanedMd = md;

  const html = useMemoR(() => {
    if (!cleanedMd) return "";
    if (window.marked) return window.marked.parse(cleanedMd, { breaks: true, gfm: true });
    return `<pre>${cleanedMd}</pre>`;
  }, [cleanedMd]);

  const lowConf = report.confidence != null && report.confidence < 50;

  return (
    <div className="detail">
      <div className="detail-head">
        <div className="detail-head-left">
          <div className={`level-badge ${sev}`}>{sev === "critical" ? dict[lang].reports_level_critical : sev === "warning" ? dict[lang].reports_level_warning : dict[lang].reports_level_normal}</div>
          <div>
            <div className="detail-title">{report.filename}</div>
            <div className="detail-sub">
              {fmtDate(report.started_at)} → {fmtDate(report.ended_at)} · {Math.round(report.duration_sec)}s · {report.total} {dict[lang].reports_msg_count}
            </div>
          </div>
        </div>
        <div className="detail-actions">
          <button className={`btn ghost ${showRaw ? "active" : ""}`} onClick={() => setShowRaw(!showRaw)}>
            <Icon name="Code" size={14} /> {dict[lang].reports_raw_log}
          </button>
          <button className="btn ghost" onClick={() => setShareOpen(true)}>
            <Icon name="Share2" size={14} /> {dict[lang].reports_share}
          </button>
          <button className="btn primary" onClick={() => window.print()}>
            <Icon name="Download" size={14} /> {dict[lang].reports_pdf}
          </button>
        </div>
      </div>

      <div className="detail-confidence">
        <div className="dc-left">
          <div className="dc-label">{dict[lang].reports_ai_confidence}</div>
          <ConfidenceBar value={report.confidence} lang={lang} />
        </div>
        <div className="dc-right">
          <div className="kpi"><span className="kpi-l">{dict[lang].reports_kpi_estop}</span><span className="kpi-v critical">{counts.blocked || 0}</span></div>
          <div className="kpi"><span className="kpi-l">{dict[lang].reports_kpi_sos}</span><span className="kpi-v critical">{counts.sos || 0}</span></div>
          <div className="kpi"><span className="kpi-l">{dict[lang].reports_kpi_cmd}</span><span className="kpi-v warning">{counts.modified || 0}</span></div>
          <div className="kpi"><span className="kpi-l">{dict[lang].reports_kpi_normal}</span><span className="kpi-v">{counts.allowed || 0}</span></div>
        </div>
      </div>

      {lowConf && (
        <div className="banner danger">
          <Icon name="AlertCircle" size={16} />
          <div>
            <strong>{dict[lang].reports_low_conf_title}</strong>
            <div className="banner-sub">{dict[lang].reports_low_conf_sub}</div>
          </div>
        </div>
      )}

      {showRaw ? (
        <div className="raw-pane">
          <div className="raw-head">
            <span>{report.raw_lines?.length || 0}{dict[lang].reports_raw_lines}{report.raw_truncated ? dict[lang].reports_raw_truncated : ""}</span>
          </div>
          <pre className="raw-pre">
            {(report.raw_lines || []).map((l, i) => JSON.stringify(l)).join("\n")}
          </pre>
        </div>
      ) : (
        <div className="md-body" dangerouslySetInnerHTML={{ __html: html }} />
      )}

      {shareOpen && (
        <div className="modal-back" onClick={() => setShareOpen(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">{dict[lang].share_modal_title}</div>
            <div className="modal-body">
              <p>{dict[lang].share_modal_body}</p>
              <label className="modal-row"><input type="checkbox" defaultChecked /> {dict[lang].share_modal_attach_log}</label>
              <label className="modal-row"><input type="checkbox" defaultChecked /> {dict[lang].share_modal_attach_pose}</label>
            </div>
            <div className="modal-foot">
              <button className="btn ghost" onClick={() => setShareOpen(false)}>{dict[lang].common_cancel}</button>
              <button className="btn primary" onClick={() => setShareOpen(false)}>{dict[lang].common_send}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

window.ReportsPage = ReportsPage;
