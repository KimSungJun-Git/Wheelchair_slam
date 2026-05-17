const { useState: useStateR, useEffect: useEffectR, useMemo: useMemoR } = React;

function ConfidenceBar({ value, size = "lg", lang = "ko" }) {
  if (value == null) return <div className="conf-empty">{window.dict[lang].reports_conf_unknown}</div>;
  const tone = value >= 80 ? "ok" : value >= 50 ? "warn" : "danger";
  return (
    <div className={`conf-block ${size}`}>
      <div className="conf-row">
        <span className="conf-num">{value}<span className="conf-pct">%</span></span>
        <span className={`conf-grade ${tone}`}>{value >= 80 ? window.dict[lang].overview_conf_good : value >= 50 ? window.dict[lang].overview_conf_ok : window.dict[lang].overview_conf_low}</span>
      </div>
      <div className="conf-track">
        <div className={`conf-fill ${tone}`} style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

function ReportCard({ r, active, onClick, lang = "ko" }) {
  const counts = r.counts || {};
  const critical = (counts.blocked || 0) + (counts.sos || 0);
  const warning = counts.modified || 0;
  return (
    <button className={`rep-card ${active ? "active" : ""}`} onClick={onClick}>
      <div className="rep-card-row">
        <div className="rep-date">{fmtDate(r.started_at)}</div>
        <div className={`rep-level ${critical > 0 ? "critical" : warning > 0 ? "warning" : "info"}`}>
          {critical > 0 ? window.dict[lang].reports_level_critical : warning > 0 ? window.dict[lang].reports_level_warning : window.dict[lang].reports_level_normal}
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

function ReportsPage({ lang = "ko" }) {
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
      if (window.ros && window.ROSLIB) {
        const rotationTopic = new window.ROSLIB.Topic({
          ros: window.ros,
          name: '/request_log_rotation',
          messageType: 'std_msgs/String'
        });
        rotationTopic.publish(new window.ROSLIB.Message({ data: 'rotate' }));
        console.log("🔄 로그 파일 분리 요청 전송 완료! 백그라운드 수집을 유지한 채 분석을 시작합니다.");
      } else {
        console.warn("⚠️ ROS 연결 객체(window.ros)를 찾을 수 없어 로그 파일 분리를 건너뜁니다.");
      }

      await new Promise(resolve => setTimeout(resolve, 1000));

      const res = await fetch(`http://${window.location.hostname}:8090/api/deep_analyze`, { method: 'POST' });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        setDeepStatus({ status: 'error', error: errData.detail || window.dict[lang].deep_err_server });
        return;
      }

      const data = await res.json();
      const { job_id, target } = data;
      setDeepStatus({ status: 'running', target });

      const poll = setInterval(async () => {
        const statusRes = await fetch(`http://${window.location.hostname}:8090/api/deep_analyze/${job_id}`);
        const statusData = await statusRes.json();

        if (statusData.status === 'done') {
          clearInterval(poll);
          setDeepStatus({ status: 'done', ok: statusData.ok, target: statusData.target });
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
              🤖 최신 로그 R1 깊은 진단
            </button>

            {deepStatus && (
              <div style={{ marginTop: '10px', fontSize: '13px', fontWeight: '500' }}>
                {deepStatus.status === 'starting' && <span style={{color: '#d97706'}}>{window.dict[lang].deep_starting}</span>}
                {deepStatus.status === 'running' && <span style={{color: '#2563eb'}}>{window.dict[lang].deep_running}</span>}
                {deepStatus.status === 'done' && <span style={{color: '#16a34a'}}>{window.dict[lang].deep_done}</span>}
                {deepStatus.status === 'error' && <span style={{color: '#dc2626'}}>{window.dict[lang].deep_failed} {deepStatus.error}</span>}
              </div>
            )}
          </div>

          <div className="rep-filters">
            <div className="filter-row">
              <Icon name="Search" size={14} className="search-icon" />
              <input
                className="search-input"
                  placeholder={window.dict[lang].reports_search}
                value={filter.q}
                onChange={(e) => setFilter({ ...filter, q: e.target.value })}
              />
            </div>
            <div className="filter-row seg">
              {[
                  ["all", window.dict[lang].reports_filter_all],
                  ["critical", window.dict[lang].reports_filter_critical],
                  ["warning", window.dict[lang].reports_filter_warning],
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
                  <span>{window.dict[lang].reports_conf_gte}</span>
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
                {filtered.length} / {list.length}{window.dict[lang].reports_shown_count}
            </div>
          </div>

          <div className="rep-list">
            {filtered.map((r) => (
                <ReportCard key={r.id} r={r} active={r.id === selectedId} onClick={() => setSelectedId(r.id)} lang={lang} />
            ))}
              {!filtered.length && <div className="empty-msg pad">{window.dict[lang].reports_empty}</div>}
          </div>
        </div>

        <div className="rep-right">
          {!detail ? (
              <div className="loading">{window.dict[lang].reports_loading}</div>
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

function ReportDetail({ report, showRaw, setShowRaw, shareOpen, setShareOpen, lang = "ko" }) {
  const [activeTab, setActiveTab] = useStateR('basic');

  const counts = report.counts || {};
  const critical = (counts.blocked || 0) + (counts.sos || 0);
  const warning = counts.modified || 0;
  const sev = critical > 0 ? "critical" : warning > 0 ? "warning" : "info";

  const lowConf = report.confidence != null && report.confidence < 50;

  const handlePrint = () => {
    const targetMd = activeTab === 'basic'
      ? (report?.markdown || window.dict[lang].rp_fail_basic)
      : (report?.deep_markdown || window.dict[lang].rp_fail_deep);

    let printHtml = targetMd;
    if (window.marked) {
      if (typeof window.marked.parse === 'function') {
        printHtml = window.marked.parse(targetMd, { breaks: true, gfm: true });
      } else if (typeof window.marked === 'function') {
        printHtml = window.marked(targetMd, { breaks: true, gfm: true });
      }
    } else {
      printHtml = `<pre>${targetMd}</pre>`;
    }

    const printWindow = window.open('', '_blank');
    printWindow.document.write(`
      <html>
        <head>
          <title>${report.filename} - ${activeTab === 'basic' ? window.dict[lang].rp_basic_rep : window.dict[lang].rp_deep_rep}</title>
          <style>
            @media print {
              @page { margin: 15mm 20mm; }
              body { margin: 0; }
              table, pre, blockquote { page-break-inside: avoid; }
              h1, h2, h3 { page-break-after: avoid; }
            }
            body { font-family: 'Pretendard', '-apple-system', 'Segoe UI', sans-serif; line-height: 1.6; color: #1f2937; padding: 40px; max-width: 800px; margin: 0 auto; }
            h1, h2, h3 { color: #111827; border-bottom: 2px solid #f3f4f6; padding-bottom: 8px; margin-top: 32px; }
            h1 { font-size: 24px; border-bottom: none; margin-top: 0; }
            table { border-collapse: collapse; width: 100%; margin: 24px 0; font-size: 14px; }
            th, td { border: 1px solid #e5e7eb; padding: 12px 16px; text-align: left; }
            th { background-color: #f9fafb; font-weight: 700; color: #374151; }
            blockquote { border-left: 4px solid #3b82f6; margin: 24px 0; padding: 16px 20px; background-color: #eff6ff; color: #1e3a8a; border-radius: 0 8px 8px 0; }
            pre { background: #f8fafc; padding: 16px; border-radius: 8px; overflow-x: auto; font-size: 13px; border: 1px solid #e2e8f0; }
            code { background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-family: 'JetBrains Mono', monospace; color: #ef4444; }
            .print-header { text-align: center; margin-bottom: 40px; padding-bottom: 24px; border-bottom: 3px solid #111827; }
            .print-header h1 { border: none; margin: 0 0 12px 0; padding: 0; font-size: 28px; }
            .print-meta { font-size: 15px; color: #4b5563; font-weight: 500; }
            .badge { display: inline-block; padding: 4px 10px; margin-top: 10px; border-radius: 999px; font-size: 13px; font-weight: bold; background: #e0e7ff; color: #1d4ed8; }
          </style>
        </head>
        <body>
          <div class="print-header">
            <h1>${report.filename}</h1>
            <div class="print-meta">${fmtDate(report.started_at)} → ${fmtDate(report.ended_at)}<br/><span class="badge">${window.dict[lang].reports_ai_confidence}: ${report.confidence ?? '-'}%</span></div>
          </div>
          ${printHtml}
        </body>
      </html>
    `);
    printWindow.document.close();
    printWindow.focus();
    setTimeout(() => { printWindow.print(); printWindow.close(); }, 250);
  };

  return (
    <div className="detail">
      <div className="detail-head">
        <div className="detail-head-left">
          <div className={`level-badge ${sev}`}>{sev === "critical" ? window.dict[lang].reports_level_critical : sev === "warning" ? window.dict[lang].reports_level_warning : window.dict[lang].reports_level_normal}</div>
          <div>
            <div className="detail-title">{report.filename}</div>
            <div className="detail-sub">
              {fmtDate(report.started_at)} → {fmtDate(report.ended_at)} · {Math.round(report.duration_sec)}s · {report.total} {window.dict[lang].reports_msg_count}
            </div>
          </div>
        </div>
        <div className="detail-actions">
          <button className={`btn ghost ${showRaw ? "active" : ""}`} onClick={() => setShowRaw(!showRaw)}>
            <Icon name="Code" size={14} /> {window.dict[lang].reports_raw_log}
          </button>
          <button className="btn ghost" onClick={() => setShareOpen(true)}>
            <Icon name="Share2" size={14} /> {window.dict[lang].reports_share}
          </button>
          <button className="btn primary" onClick={handlePrint}>
            <Icon name="Download" size={14} /> {window.dict[lang].reports_pdf}
          </button>
        </div>
      </div>

      <div className="detail-confidence">
        <div className="dc-left">
          <div className="dc-label">{window.dict[lang].reports_ai_confidence}</div>
          <ConfidenceBar value={report.confidence} lang={lang} />
        </div>
        <div className="dc-right">
          <div className="kpi"><span className="kpi-l">{window.dict[lang].reports_kpi_estop}</span><span className="kpi-v critical">{counts.blocked || 0}</span></div>
          <div className="kpi"><span className="kpi-l">{window.dict[lang].reports_kpi_sos}</span><span className="kpi-v critical">{counts.sos || 0}</span></div>
          <div className="kpi"><span className="kpi-l">{window.dict[lang].reports_kpi_cmd}</span><span className="kpi-v warning">{counts.modified || 0}</span></div>
          <div className="kpi"><span className="kpi-l">{window.dict[lang].reports_kpi_normal}</span><span className="kpi-v">{counts.allowed || 0}</span></div>
        </div>
      </div>

      {lowConf && (
        <div className="banner danger">
          <Icon name="AlertCircle" size={16} />
          <div>
            <strong>{window.dict[lang].reports_low_conf_title}</strong>
            <div className="banner-sub">{window.dict[lang].reports_low_conf_sub}</div>
          </div>
        </div>
      )}

      {/* --- 원본 로그 보기 vs 탭 보고서 보기 --- */}
      {showRaw ? (
        <div className="raw-pane">
          <div className="raw-head">
            <span>{report?.raw_lines?.length || 0}{window.dict[lang].reports_raw_lines}{report?.raw_truncated ? window.dict[lang].reports_raw_truncated : ""}</span>
          </div>
          <pre className="raw-pre">
            {(report?.raw_lines || []).map((l, i) => JSON.stringify(l)).join("\n")}
          </pre>
        </div>
      ) : (
        <>
          <div className="report-tabs" style={{ marginBottom: '15px', borderBottom: '1px solid var(--line)', display: 'flex', gap: '10px' }}>
            <button
              className={`report-tab-btn ${activeTab === 'basic' ? 'active' : ''}`}
              onClick={() => setActiveTab('basic')}
            >
              {window.dict[lang].rp_basic_rep}
            </button>
            <button
              className={`report-tab-btn ${activeTab === 'deep' ? 'active' : ''}`}
              onClick={() => setActiveTab('deep')}
            >
              {window.dict[lang].rp_deep_rep}
            </button>
          </div>

          <div className="md-body">
            {(() => {
              const targetMd = activeTab === 'basic'
                ? (report?.markdown || window.dict[lang].rp_fail_basic)
                : (report?.deep_markdown || window.dict[lang].rp_fail_deep);

              let html = targetMd;
              if (window.marked) {
                if (typeof window.marked.parse === 'function') {
                  html = window.marked.parse(targetMd);
                } else if (typeof window.marked === 'function') {
                  html = window.marked(targetMd);
                }
              }

              return <div dangerouslySetInnerHTML={{ __html: html }} />;
            })()}
          </div>
        </>
      )}

      {shareOpen && (
        <div className="modal-back" onClick={() => setShareOpen(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">{window.dict[lang].share_modal_title}</div>
            <div className="modal-body">
              <p>{window.dict[lang].share_modal_body}</p>
              <label className="modal-row"><input type="checkbox" defaultChecked /> {window.dict[lang].share_modal_attach_log}</label>
              <label className="modal-row"><input type="checkbox" defaultChecked /> {window.dict[lang].share_modal_attach_pose}</label>
            </div>
            <div className="modal-foot">
              <button className="btn ghost" onClick={() => setShareOpen(false)}>{window.dict[lang].lv_cancel}</button>
              <button className="btn primary" onClick={() => {
                setShareOpen(false);
                alert("보고서가 지정된 담당자 및 보호자에게 전송되었습니다.");
              }}>{window.dict[lang].reports_share}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

window.ReportsPage = ReportsPage;
