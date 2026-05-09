// API client + offline parser.
// First tries the FastAPI server at API_BASE. If unreachable, falls back to
// parsing bundled sample_data/*.json client-side using the same normalization
// rules as server.py — so the design preview works without a backend.

const API_BASE = "http://localhost:8090";

const REASON_LABEL = {
  imu_lost: "IMU 연결 끊김",
  imu_emergency: "IMU 비상(기울기·충격)",
  imu_기울기: "IMU 기울기 초과",
  ultrasonic_lost: "초음파 연결 끊김",
  lidar_lost: "라이다 연결 끊김",
  odom_lost: "오도메트리 끊김",
  localization_emergency: "위치 추정 실패",
  obstacle_front: "전방 장애물",
};
const ACTION_LABEL = {
  blocked: "비상정지",
  modified: "명령수정",
  sos: "SOS",
  allowed: "정상통과",
};
const ACTION_SEVERITY = {
  sos: "critical",
  blocked: "critical",
  modified: "warning",
  allowed: "info",
};
const DEDUP_WINDOW_SEC = 5.0;

const SAMPLE_FILES = [
  "sample_data/[주행로그]_2026-05-06_21-41-01.json",
];

let _cache = null;
let _serverUp = null;

async function probeServer() {
  if (_serverUp !== null) return _serverUp;
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 700);
    const r = await fetch(`${API_BASE}/api/health`, { signal: ctrl.signal });
    clearTimeout(t);
    _serverUp = r.ok;
  } catch (_e) {
    _serverUp = false;
  }
  return _serverUp;
}

function normalizeReason(raw) {
  raw = (raw || "").trim();
  if (!raw) return { key: "", raw: "" };
  const first = raw.split(",")[0].trim();
  const key = first.split(":")[0].trim();
  return { key, raw };
}

function dedupMessages(logs) {
  const seen = new Set();
  const out = [];
  for (const l of logs) {
    const k = `${l.timestamp}|${l.source}|${l.action}|${l.reason}`;
    if (seen.has(k)) continue;
    seen.add(k);
    out.push(l);
  }
  return out;
}

function parseJsonl(text) {
  const markers = [];
  const logs = [];
  for (const line of text.split("\n")) {
    const t = line.trim();
    if (!t) continue;
    try {
      const obj = JSON.parse(t);
      if (obj._event_marker) markers.push(obj);
      else logs.push(obj);
    } catch (_e) {}
  }
  return { markers, logs };
}

function summarize(filename, jsonText, mdText) {
  const sessionId = filename.replace(/\.json$/, "").split("/").pop();
  const { logs: rawLogs } = parseJsonl(jsonText);
  const logs = dedupMessages(rawLogs);

  if (!logs.length) {
    return {
      id: sessionId,
      filename: filename.split("/").pop(),
      started_at: null,
      ended_at: null,
      duration_sec: 0,
      total: 0,
      counts: { blocked: 0, modified: 0, sos: 0, allowed: 0 },
      events: [],
      reasons: {},
      confidence: null,
      has_md: !!mdText,
      raw_lines: [],
    };
  }

  const tss = logs.map((l) => l.timestamp).filter(Boolean);
  const started = Math.min(...tss);
  const ended = Math.max(...tss);

  const counts = { blocked: 0, modified: 0, sos: 0, allowed: 0 };
  for (const l of logs) counts[l.action] = (counts[l.action] || 0) + 1;

  const events = [];
  let lastKey = null;
  let lastT = 0;
  for (const l of logs) {
    if (!["blocked", "modified", "sos"].includes(l.action)) continue;
    const { key, raw } = normalizeReason(l.reason || "");
    const ts = l.timestamp || 0;
    const k = `${l.action}|${key}`;
    if (k === lastKey && ts - lastT < DEDUP_WINDOW_SEC) continue;
    const pose = l.pose || {};
    const zoneRaw = l.zone || "";
    events.push({
      ts,
      action: l.action,
      severity: ACTION_SEVERITY[l.action] || "info",
      reason_key: key,
      reason_label: REASON_LABEL[key] || key || "원인불명",
      reason_raw: raw,
      pose: { x: pose.x ?? null, y: pose.y ?? null, yaw: pose.yaw ?? null },
      zone: zoneRaw.split("|")[0].trim() || null,
      source: l.source || null,
    });
    lastKey = k;
    lastT = ts;
  }

  const reasons = {};
  for (const e of events) {
    if (e.reason_key) reasons[e.reason_key] = (reasons[e.reason_key] || 0) + 1;
  }

  let confidence = null;
  if (mdText) {
    const m = mdText.match(/AI\s*신뢰도[\s|:🎯]*[\|\s]*(\d+)\s*%?/);
    if (m) confidence = parseInt(m[1], 10);
  }

  return {
    id: sessionId,
    filename: filename.split("/").pop(),
    started_at: started,
    ended_at: ended,
    duration_sec: ended - started,
    total: logs.length,
    counts,
    events,
    reasons,
    confidence,
    has_md: !!mdText,
    raw_lines: logs.slice(0, 2000),
    raw_truncated: logs.length > 2000,
    markdown: mdText || null,
  };
}

async function loadSamples() {
  if (_cache) return _cache;
  const out = [];
  for (const path of SAMPLE_FILES) {
    try {
      const json = await fetch(path).then((r) => r.text());
      const mdPath = path.replace(/\.json$/, "_report.md");
      let md = null;
      try {
        md = await fetch(mdPath).then((r) => (r.ok ? r.text() : null));
      } catch (_e) {}
      out.push(summarize(path, json, md));
    } catch (e) {
      console.error("sample load failed", path, e);
    }
  }
  _cache = out;
  return out;
}

function bucketEvents(events, hours) {
  const cutoff = Date.now() / 1000 - hours * 3600;
  const recent = events.filter((e) => e.ts >= cutoff);

  const byDay = {};
  const byHour = {};
  const reasonC = {};
  const sev = { critical: 0, warning: 0, info: 0 };

  for (const e of events) {
    sev[e.severity] = (sev[e.severity] || 0) + 1;
    if (e.reason_key) reasonC[e.reason_key] = (reasonC[e.reason_key] || 0) + 1;
    const d = new Date(e.ts * 1000);
    const dayKey = `${String(d.getMonth() + 1).padStart(2, "0")}/${String(
      d.getDate()
    ).padStart(2, "0")}`;
    const hourKey = `${dayKey} ${String(d.getHours()).padStart(2, "0")}:00`;
    if (!byDay[dayKey]) byDay[dayKey] = { day: dayKey, critical: 0, warning: 0 };
    if (e.severity === "critical" || e.severity === "warning")
      byDay[dayKey][e.severity]++;
    if (!byHour[hourKey])
      byHour[hourKey] = { hour: hourKey, critical: 0, warning: 0, info: 0 };
    byHour[hourKey][e.severity] = (byHour[hourKey][e.severity] || 0) + 1;
  }

  return {
    by_day: Object.values(byDay).sort((a, b) => a.day.localeCompare(b.day)),
    by_hour: Object.values(byHour).sort((a, b) => a.hour.localeCompare(b.hour)),
    by_severity: sev,
    reasons: Object.entries(reasonC)
      .map(([key, count]) => ({
        key,
        label: REASON_LABEL[key] || key,
        count,
      }))
      .sort((a, b) => b.count - a.count),
    total_events: events.length,
    recent_count: recent.length,
  };
}

// Public API ----------------------------------------------------------------

const Api = {
  REASON_LABEL,
  ACTION_LABEL,
  ACTION_SEVERITY,

  async getMode() {
    const up = await probeServer();
    return up ? "live" : "sample";
  },

  async getHealth() {
    if (await probeServer()) {
      return fetch(`${API_BASE}/api/health`).then((r) => r.json());
    }
    const samples = await loadSamples();
    return {
      ok: true,
      mode: "sample",
      data_dir: "(브라우저 샘플 모드 — server.py 미실행)",
      exists: true,
      session_count: samples.length,
      latest: samples[0]?.filename || null,
    };
  },

  async getReports() {
    if (await probeServer()) {
      return fetch(`${API_BASE}/api/reports`).then((r) => r.json());
    }
    const samples = await loadSamples();
    return {
      reports: samples.map(({ events, raw_lines, markdown, ...rest }) => rest),
      count: samples.length,
    };
  },

  async getReport(id) {
    if (await probeServer()) {
      return fetch(`${API_BASE}/api/report/${encodeURIComponent(id)}`).then((r) =>
        r.json()
      );
    }
    const samples = await loadSamples();
    const s = samples.find((x) => x.id === id) || samples[0];
    return s;
  },

  async getEvents(hours = 24) {
    if (await probeServer()) {
      return fetch(`${API_BASE}/api/events?hours=${hours}`).then((r) => r.json());
    }
    const samples = await loadSamples();
    const all = [];
    const sessions = [];
    let confSum = 0;
    let confN = 0;
    for (const s of samples) {
      sessions.push({
        id: s.id,
        started_at: s.started_at,
        duration_sec: s.duration_sec,
        counts: s.counts,
        confidence: s.confidence,
      });
      if (s.confidence != null) {
        confSum += s.confidence;
        confN++;
      }
      for (const e of s.events) all.push({ ...e, session_id: s.id });
    }
    const buckets = bucketEvents(all, hours);
    return {
      window_hours: hours,
      ...buckets,
      events: all,
      sessions,
      avg_confidence: confN ? Math.round(confSum / confN) : null,
      session_count: sessions.length,
    };
  },

  async getLive() {
    if (await probeServer()) {
      return fetch(`${API_BASE}/api/live`).then((r) => r.json());
    }
    const samples = await loadSamples();
    if (!samples.length) return { connected: false, events: [], pose: null };
    const s = samples[0];
    const last = s.raw_lines[s.raw_lines.length - 1] || {};
    const pose = last.pose || {};
    return {
      connected: true,
      session_id: s.id,
      pose: { x: pose.x, y: pose.y, yaw: pose.yaw },
      velocity: last.velocity || {},
      zone_raw: last.zone || "",
      zone: (last.zone || "").split("|")[0].trim() || null,
      events: s.events.slice(-30).reverse(),
      last_log_ts: last.timestamp,
    };
  },
};

window.Api = Api;
