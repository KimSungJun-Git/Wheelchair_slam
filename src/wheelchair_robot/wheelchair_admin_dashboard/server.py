#!/usr/bin/env python3
"""
server.py — Wheelchair Admin Dashboard 백엔드 어댑터.

실행:
    pip install fastapi uvicorn
    python3 server.py

엔드포인트:
    GET /api/health             폴더 상태·세션 개수
    GET /api/reports            보고서 목록 (메타만)
    GET /api/report/{id}        세션 상세 (JSON Lines + _report.md 파싱)
    GET /api/events?hours=24    윈도우 통계 (시간별·일자별·원인별 집계)
    GET /api/live               최신 세션의 마지막 pose + 이벤트 스트림

데이터 소스:
    ~/wheelchair_ws/driving_data/[주행로그]_*.json (+ 같은 이름 *_report.md)
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import subprocess

# ───────────────────────── Config ─────────────────────────

DATA_DIR = Path(os.environ.get(
    "WHEELCHAIR_DATA_DIR",
    os.path.expanduser("~/wheelchair_ws/driving_data"),
))
PORT = int(os.environ.get("PORT", "8090"))

REASON_LABEL: dict[str, str] = {
    "imu_lost": "IMU 연결 끊김",
    "imu_emergency": "IMU 비상(기울기·충격)",
    "imu_기울기": "IMU 기울기 초과",
    "ultrasonic_lost": "초음파 연결 끊김",
    "lidar_lost": "라이다 연결 끊김",
    "odom_lost": "오도메트리 끊김",
    "localization_emergency": "위치 추정 실패",
    "obstacle_front": "전방 장애물",
}
ACTION_SEVERITY = {
    "sos": "critical",
    "blocked": "critical",
    "modified": "warning",
    "allowed": "info",
}
DEDUP_WINDOW_SEC = 5.0

# ───────────────────────── Helpers ─────────────────────────


def list_session_files() -> list[Path]:
    if not DATA_DIR.exists():
        return []
    files = list(DATA_DIR.glob("*.json"))
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files


def session_id(path: Path) -> str:
    return path.stem


def md_path_for(path: Path) -> Path:
    return path.with_name(path.stem + "_report.md")


def parse_jsonl(path: Path) -> tuple[list[dict], list[dict]]:
    """Return (markers, logs). Tolerates partial / malformed lines."""
    markers, logs = [], []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("_event_marker"):
                    markers.append(obj)
                else:
                    logs.append(obj)
    except OSError:
        pass
    return markers, logs


def normalize_reason(raw: str) -> tuple[str, str]:
    raw = (raw or "").strip()
    if not raw:
        return "", ""
    first = raw.split(",")[0].strip()
    key = first.split(":")[0].strip()
    return key, raw


def dedup_messages(logs: list[dict]) -> list[dict]:
    seen: set = set()
    out: list[dict] = []
    for l in logs:
        k = (l.get("timestamp"), l.get("source"), l.get("action"), l.get("reason"))
        if k in seen:
            continue
        seen.add(k)
        out.append(l)
    return out


def extract_events(logs: list[dict]) -> list[dict]:
    events: list[dict] = []
    last_key: tuple | None = None
    last_t = 0.0
    for l in logs:
        action = l.get("action")
        if action not in ("blocked", "modified", "sos"):
            continue
        key, raw = normalize_reason(l.get("reason", ""))
        ts = float(l.get("timestamp") or 0.0)
        k = (action, key)
        if k == last_key and (ts - last_t) < DEDUP_WINDOW_SEC:
            continue
        pose = l.get("pose") or {}
        zone_raw = l.get("zone") or ""
        events.append({
            "ts": ts,
            "action": action,
            "severity": ACTION_SEVERITY.get(action, "info"),
            "reason_key": key,
            "reason_label": REASON_LABEL.get(key, key or "원인불명"),
            "reason_raw": raw,
            "pose": {
                "x": pose.get("x"),
                "y": pose.get("y"),
                "yaw": pose.get("yaw"),
            },
            "zone": (zone_raw.split("|")[0].strip() or None) if zone_raw else None,
            "source": l.get("source"),
        })
        last_key = k
        last_t = ts
    return events


def parse_confidence(md: str | None) -> int | None:
    if not md:
        return None
    # Matches: "🎯 AI 신뢰도 | 75%" or "AI 신뢰도: 75"
    m = re.search(r"AI\s*신뢰도[\s:|🎯]*[\|\s]*(\d+)\s*%?", md)
    return int(m.group(1)) if m else None


def session_summary(path: Path, with_events: bool = False, with_raw: bool = False) -> dict:
    _markers, raw_logs = parse_jsonl(path)
    logs = dedup_messages(raw_logs)
    md = None
    mp = md_path_for(path)
    if mp.exists():
        try:
            md = mp.read_text(encoding="utf-8")
        except OSError:
            md = None

    if not logs:
        return {
            "id": session_id(path),
            "filename": path.name,
            "started_at": None,
            "ended_at": None,
            "duration_sec": 0,
            "total": 0,
            "counts": {"blocked": 0, "modified": 0, "sos": 0, "allowed": 0},
            "confidence": parse_confidence(md),
            "has_md": md is not None,
        }

    tss = [float(ts) for l in logs if (ts := l.get("timestamp"))]
    started = min(tss) if tss else None
    ended = max(tss) if tss else None

    counts = Counter(l.get("action") for l in logs)
    events = extract_events(logs) if with_events else []
    reasons = Counter(e["reason_key"] for e in events if e["reason_key"])

    out: dict[str, Any] = {
        "id": session_id(path),
        "filename": path.name,
        "started_at": started,
        "ended_at": ended,
        "duration_sec": (ended - started) if started and ended else 0,
        "total": len(logs),
        "counts": {
            "blocked": counts.get("blocked", 0),
            "modified": counts.get("modified", 0),
            "sos": counts.get("sos", 0),
            "allowed": counts.get("allowed", 0),
        },
        "confidence": parse_confidence(md),
        "has_md": md is not None,
    }
    if with_events:
        out["events"] = events
        out["reasons"] = dict(reasons)
        out["markdown"] = md
    if with_raw:
        out["raw_lines"] = logs[:2000]
        out["raw_truncated"] = len(logs) > 2000
    return out


# ───────────────────────── App ─────────────────────────

app = FastAPI(title="Wheelchair Admin API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    files = list_session_files()
    return {
        "ok": True,
        "mode": "live",
        "data_dir": str(DATA_DIR),
        "exists": DATA_DIR.exists(),
        "session_count": len(files),
        "latest": files[0].name if files else None,
        "server_time": time.time(),
    }


@app.get("/api/reports")
def reports():
    files = list_session_files()
    out = [session_summary(p, with_events=False, with_raw=False) for p in files]
    return {"reports": out, "count": len(out)}


@app.get("/api/report/{report_id}")
def report(report_id: str):
    for p in list_session_files():
        if session_id(p) == report_id:
            return session_summary(p, with_events=True, with_raw=True)
    raise HTTPException(404, f"report not found: {report_id}")


@app.get("/api/events")
def events(hours: int = 24):
    files = list_session_files()
    sessions: list[dict] = []
    all_events: list[dict] = []
    conf_sum = 0
    conf_n = 0
    for p in files:
        s = session_summary(p, with_events=True, with_raw=False)
        sessions.append({
            "id": s["id"],
            "started_at": s["started_at"],
            "duration_sec": s["duration_sec"],
            "counts": s["counts"],
            "confidence": s["confidence"],
        })
        if s.get("confidence") is not None:
            conf_sum += s["confidence"]
            conf_n += 1
        for e in s.get("events", []):
            all_events.append({**e, "session_id": s["id"]})

    cutoff = time.time() - hours * 3600
    recent = [e for e in all_events if e["ts"] >= cutoff]

    by_day: dict[str, dict] = {}
    by_hour: dict[str, dict] = {}
    reason_c: Counter = Counter()
    sev_c = Counter()

    for e in all_events:
        sev_c[e["severity"]] += 1
        if e.get("reason_key"):
            reason_c[e["reason_key"]] += 1
        d = datetime.fromtimestamp(e["ts"])
        day_key = d.strftime("%m/%d")
        hour_key = d.strftime("%m/%d %H:00")
        by_day.setdefault(day_key, {"day": day_key, "critical": 0, "warning": 0})
        if e["severity"] in ("critical", "warning"):
            by_day[day_key][e["severity"]] += 1
        by_hour.setdefault(hour_key, {"hour": hour_key, "critical": 0, "warning": 0, "info": 0})
        by_hour[hour_key][e["severity"]] = by_hour[hour_key].get(e["severity"], 0) + 1

    return {
        "window_hours": hours,
        "by_day": sorted(by_day.values(), key=lambda r: r["day"]),
        "by_hour": sorted(by_hour.values(), key=lambda r: r["hour"]),
        "by_severity": dict(sev_c),
        "reasons": [
            {"key": k, "label": REASON_LABEL.get(k, k), "count": v}
            for k, v in reason_c.most_common()
        ],
        "total_events": len(all_events),
        "recent_count": len(recent),
        "events": all_events,
        "sessions": sessions,
        "session_count": len(sessions),
        "avg_confidence": round(conf_sum / conf_n) if conf_n else None,
    }


@app.get("/api/live")
def live():
    files = list_session_files()
    if not files:
        return {"connected": False, "events": [], "pose": None}
    p = files[0]
    s = session_summary(p, with_events=True, with_raw=True)
    last = (s.get("raw_lines") or [{}])[-1]
    pose = last.get("pose") or {}
    zone_raw = last.get("zone") or ""
    last_ts = last.get("timestamp") or 0.0
    connected = (time.time() - last_ts) < 30.0  # 30초 내 로그 → "연결됨"
    return {
        "connected": connected,
        "session_id": s["id"],
        "pose": {"x": pose.get("x"), "y": pose.get("y"), "yaw": pose.get("yaw")},
        "velocity": last.get("velocity") or {},
        "zone_raw": zone_raw,
        "zone": (zone_raw.split("|")[0].strip() or None) if zone_raw else None,
        "mode": last.get("mode") or "auto",
        "events": list(reversed(s.get("events", [])[-30:])),
        "last_log_ts": last_ts,
    }


@app.get("/")
def root():
    return JSONResponse({
        "service": "wheelchair-admin-api",
        "data_dir": str(DATA_DIR),
        "endpoints": [
            "/api/health",
            "/api/reports",
            "/api/report/{id}",
            "/api/events?hours=24",
            "/api/live",
        ],
    })
_analyzing = False

@app.post("/api/analyze_session")
def analyze_session():
    global _analyzing
    if _analyzing:
        return {"ok": False, "message": "이미 분석 중입니다."}
    _analyzing = True
    """대시보드에서 명시적 세션 종료 및 AI 분석 트리거"""
    try:
        # ROS 2 agent_analyzer 노드를 백그라운드로 실행
        cmd = "source /opt/ros/humble/setup.bash && source ~/wheelchair_ws/install/setup.bash && ros2 run wheelchair_robot_ai agent_analyzer"
        subprocess.Popen(["bash", "-c", cmd])
        return {"ok": True, "message": "세션 종료 및 AI 분석이 백그라운드에서 시작되었습니다."}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(500, f"분석 실행 실패: {str(e)}")
@app.post("/api/analyze/latest")
def trigger_analysis():
    """최신 주행 로그에 대해 AI 분석 스크립트를 실행합니다."""
    try:
        # run_analyzer.sh 실행 (워크스페이스 내 경로 확인 필요)
        script_path = os.path.expanduser("~/wheelchair_ws/run_analyzer.sh")
        # subprocess를 사용하여 쉘 스크립트 실행
        result = subprocess.run(["bash", script_path], capture_output=True, text=True, check=True)
        return {"ok": True, "message": "AI 분석이 성공적으로 완료되었습니다.", "output": result.stdout}
    except subprocess.CalledProcessError as e:
        raise HTTPException(500, detail=f"분석 스크립트 실행 실패: {e.stderr}")
    except Exception as e:
        raise HTTPException(500, detail=str(e))

# ───────────────────────── Entrypoint ─────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wheelchair Admin Dashboard API")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--data-dir", default=str(DATA_DIR))
    parser.add_argument("--reload", action="store_true", help="dev autoreload")
    args = parser.parse_args()

    DATA_DIR = Path(os.path.expanduser(args.data_dir))
    print(f"📁 data_dir = {DATA_DIR} ({'OK' if DATA_DIR.exists() else '없음'})")
    print(f"🔌 http://{args.host}:{args.port}/api/health")
    uvicorn.run("server:app" if args.reload else app, host=args.host, port=args.port, reload=args.reload)
