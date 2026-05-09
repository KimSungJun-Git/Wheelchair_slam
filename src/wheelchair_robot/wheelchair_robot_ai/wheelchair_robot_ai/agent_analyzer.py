#!/usr/bin/env python3
# agent_analyzer.py
import os
import json
import glob
import sys
import re
from typing import TypedDict
from collections import Counter
from datetime import datetime
from langgraph.graph import StateGraph, END
from langchain_ollama import ChatOllama
from langchain_core.prompts import PromptTemplate


class AgentState(TypedDict, total=False):
    raw_logs: str
    analysis_report: str
    summary: str


# ===== 한국어 라벨 매핑 =====
ACTION_LABEL: dict[str, str] = {
    "blocked":  "🚨 비상정지",
    "modified": "⚠️ 명령수정",
    "sos":      "🆘 SOS",
    "allowed":  "✅ 정상통과",
}

REASON_LABEL: dict[str, str] = {
    "imu_lost":               "IMU 연결 끊김",
    "imu_emergency":          "IMU 비상(기울기·충격)",
    "imu_기울기":              "IMU 기울기 초과",
    "ultrasonic_lost":        "초음파 연결 끊김",
    "lidar_lost":             "라이다 연결 끊김",
    "odom_lost":              "오도메트리 끊김",
    "localization_emergency": "위치 추정 실패",
    "obstacle_front":         "전방 장애물",
}

DEDUP_WINDOW_SEC = 5.0  # 같은 사건이 N초 이내 반복되면 1건으로 묶음


def split_reasons(reason_str):
    """콤마로 합쳐진 reason을 분리. 'key:상세값' 형태면 key만 추출."""
    if not reason_str:
        return tuple()
    
    normalized = []
    for r in reason_str.split(","):
        r = r.strip()
        if not r:
            continue
        # 'imu_기울기:roll=-50.8° pitch=22.4°' → 'imu_기울기'
        key = r.split(":")[0].strip()
        if key:
            normalized.append(key)
    
    return tuple(sorted(set(normalized)))


def deduplicate_messages(all_logs):
    """
    log_collector가 스냅샷마다 과거 30초 데이터를 중복 저장하는 문제 해결.
    timestamp + source + action + reason 조합이 같으면 같은 메시지로 간주.
    """
    seen = set()
    deduped = []
    for log in all_logs:
        key = (
            log.get("timestamp"),
            log.get("source"),
            log.get("action"),
            log.get("reason"),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(log)
    return deduped


def deduplicate_events(event_logs):
    """같은 종류의 사건이 5초 이내 연속되면 1건으로 묶음"""
    unique = []
    last_key = None
    last_time = 0
    
    for log in event_logs:
        action = log.get("action")
        reasons = split_reasons(log.get("reason", ""))
        ts = log.get("timestamp", 0)
        
        key = (action, reasons)
        if key == last_key and (ts - last_time) < DEDUP_WINDOW_SEC:
            continue
        
        pose = log.get("pose") or {}
        unique.append({
            "action": action,
            "reasons": list(reasons),
            "x": pose.get("x"),
            "y": pose.get("y"),
            "timestamp": ts,
            "raw": log,
        })
        last_key = key
        last_time = ts
    
    return unique


def build_summary(all_logs):
    """전체 로그에서 룰 기반 통계 요약 생성 (LLM 거치지 않음)"""
    total = len(all_logs)
    
    action_counter = Counter(log.get("action", "unknown") for log in all_logs)
    
    timestamps = [log.get("timestamp") for log in all_logs if log.get("timestamp")]
    duration = ""
    if timestamps:
        start = datetime.fromtimestamp(min(timestamps)).strftime("%H:%M:%S")
        end = datetime.fromtimestamp(max(timestamps)).strftime("%H:%M:%S")
        duration = f" ({start} ~ {end})"
    
    # 사건 단위 디듀플
    event_logs = [l for l in all_logs if l.get("action") in ("blocked", "modified", "sos")]
    unique_events = deduplicate_events(event_logs)
    
    # 센서별 이상 카운트
    sensor_counter: Counter = Counter()
    for evt in unique_events:
        for r in evt["reasons"]:
            sensor_counter[r] += 1
    
    lines = []
    lines.append(f"## 📋 이벤트 요약{duration}")
    lines.append("")
    lines.append(f"- **총 메시지: {total}개** (중복 제거 후)")
    
    for action, count in action_counter.most_common():
        label = ACTION_LABEL.get(action, action)
        lines.append(f"- {label}: {count}개")
    
    if sensor_counter:
        lines.append("")
        lines.append(f"### 🔧 감지된 이상 (실제 사건 {len(unique_events)}건)")
        for reason, count in sensor_counter.most_common():
            label = REASON_LABEL.get(reason, reason)
            lines.append(f"- {label} (`{reason}`): {count}건")
    
    if unique_events:
        lines.append("")
        lines.append(f"### 📍 사건 발생 위치 (전체 {len(unique_events)}건)")
        for evt in unique_events:
            label = ACTION_LABEL.get(evt["action"], evt["action"])
            time_str = datetime.fromtimestamp(evt["timestamp"]).strftime("%H:%M:%S")
            reason_labels: list[str] = [
                REASON_LABEL.get(r, r) for r in evt["reasons"]
                if isinstance(r, str) and r
            ]
            reason_str = ", ".join(reason_labels) if reason_labels else "원인불명"
            xy = f"x={evt['x']}, y={evt['y']}" if evt['x'] is not None else "위치불명"
            lines.append(f"- {time_str} {label} @ `{xy}` — {reason_str}")
    
    return "\n".join(lines), unique_events


def read_logs(state: AgentState):
    log_dir = os.path.expanduser('~/wheelchair_ws/driving_data')
    list_of_files = glob.glob(f'{log_dir}/*.json')
    
    if not list_of_files:
        print("\033[93m\n[알림] 분석할 로그 파일이 없습니다.\033[0m")
        sys.exit(0)
    
    latest_file = max(list_of_files, key=os.path.getmtime)
    print(f"\033[90m📄 분석 대상: {os.path.basename(latest_file)}\033[0m")
    
    raw_logs_list = []
    
    with open(latest_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                log = json.loads(line)
                if log.get("_event_marker"):
                    continue
                raw_logs_list.append(log)
            except json.JSONDecodeError:
                pass
    
    if not raw_logs_list:
        print("\033[92m🟢 [완벽] 수집된 로그가 없습니다.\033[0m")
        sys.exit(0)
    
    # ⭐ 핵심: log_collector가 중복 저장한 메시지를 먼저 제거
    before_count = len(raw_logs_list)
    all_logs = deduplicate_messages(raw_logs_list)
    after_count = len(all_logs)
    
    if before_count != after_count:
        print(f"\033[90m🔁 중복 메시지 {before_count - after_count}개 제거 ({before_count} → {after_count})\033[0m")
    
    summary, unique_events = build_summary(all_logs)
    print("\033[96m" + summary + "\033[0m\n")
    
    if not unique_events:
        print("\033[92m🟢 [완벽] 분석할 사건이 없습니다. 안전 주행!\033[0m")
        sys.exit(0)
    
    deduped_raw = [evt["raw"] for evt in unique_events]
    allowed_sample = [l for l in all_logs if l.get("action") == "allowed"][-10:]
    logs_for_llm = deduped_raw + allowed_sample
    
    return {
        "raw_logs": json.dumps(logs_for_llm, indent=2, ensure_ascii=False),
        "summary": summary,
        "analysis_report": "",
    }


def analyze_logs(state: AgentState):
    llm = ChatOllama(model="qwen2.5:7b", temperature=0.0)
    
    prompt = PromptTemplate(
    input_variables=["stats"],
    template="""
You are a UX analyst for autonomous wheelchair systems.
Analyze the pre-computed statistics below and output ONLY the JSON object.

Rules:
- Express findings as possibilities, not assertions.
- Every finding must reference evidence from the stats.
- If a metric is missing or zero, set "insufficient_data": true.
- Preserve Korean destination labels (응급실/101호/102호/대기소) verbatim.
- All string values MUST be written in Korean only. NEVER use Chinese characters.

[STATS]
{stats}

[OUTPUT — JSON only, no prose]
{{
  "movement_pattern_summary": "",
  "repeated_intervention_zones": [],
  "discomfort_zones": [],
  "improvement_suggestions": [],
  "overall_stability": {{"level": "high|medium|low", "reason": ""}},
  "insufficient_data": false
}}
"""
)
    chain = prompt | llm
    response = chain.invoke({"stats": state.get("raw_logs", "")})
    return {"analysis_report": response.content}


def main(args=None):
    print("\033[96m🔄 AI가 데이터를 분석 중입니다. 잠시만 기다려주세요...\033[0m")
    
    workflow = StateGraph(AgentState)
    workflow.add_node("read", read_logs)
    workflow.add_node("analyze", analyze_logs)
    workflow.set_entry_point("read")
    workflow.add_edge("read", "analyze")
    workflow.add_edge("analyze", END)
    
    app = workflow.compile()
    
    result = app.invoke({
        "raw_logs": "",
        "analysis_report": "",
        "summary": "",
    })
    report_content = result.get("analysis_report", "")
    
    print("\033[96m\n================= [ 🤖 AI 분석 완료 ] =================\033[0m\n")
    print(report_content)
    
    confidence_match = re.search(r'🎯\s*AI\s*신뢰도[\s:|]*(\d+)', report_content)
    if confidence_match:
        confidence = int(confidence_match.group(1))
        if confidence < 50:
            print("\033[91m\n[경고] AI 신뢰도가 50% 미만입니다. 데이터가 부족할 수 있습니다.\033[0m")
            try:
                user_input = input("\033[93m❓ 추가 센서 로그를 제공하시겠습니까? (Y/N): \033[0m")
                if user_input.lower() == 'y':
                    print("\033[92m[시스템] 추가 데이터 수집 모드 활성화 대기...\033[0m")
                else:
                    print("\033[90m[시스템] 기존 분석 결과로 마감합니다.\033[0m")
            except EOFError:
                pass
    
    print("\033[96m\n=======================================================\033[0m\n")
    
    try:
        log_dir = os.path.expanduser('~/wheelchair_ws/driving_data')
        latest_json = max(glob.glob(f'{log_dir}/*.json'), key=os.path.getmtime)
        report_filename = os.path.basename(latest_json).replace('.json', '_report.md')
        report_path = os.path.join(log_dir, report_filename)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(result.get("summary", ""))
            f.write("\n\n---\n\n")
            f.write(report_content)
        print(f"\033[92m💾 분석 리포트 저장: {report_filename}\033[0m")
    except Exception as e:
        print(f"\033[91m⚠️ 리포트 저장 실패: {e}\033[0m")


if __name__ == "__main__":
    main()