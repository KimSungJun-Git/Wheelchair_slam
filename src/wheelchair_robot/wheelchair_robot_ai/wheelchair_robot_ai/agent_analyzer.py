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
ACTION_LABEL = {
    "blocked":  "🚨 비상정지",
    "modified": "⚠️ 명령수정",
    "sos":      "🆘 SOS",
    "allowed":  "✅ 정상통과",
}

REASON_LABEL = {
    "imu_lost":               "IMU 연결 끊김",
    "imu_emergency":          "IMU 비상(기울기·충격)",
    "ultrasonic_lost":        "초음파 연결 끊김",
    "lidar_lost":             "라이다 연결 끊김",
    "odom_lost":              "오도메트리 끊김",
    "localization_emergency": "위치 추정 실패",
    "obstacle_front":         "전방 장애물",
}

DEDUP_WINDOW_SEC = 5.0  # 같은 사건이 N초 이내 반복되면 1건으로 묶음


def split_reasons(reason_str):
    """콤마로 합쳐진 reason을 개별 센서로 분리 (정렬된 튜플로 반환)"""
    if not reason_str:
        return tuple()
    return tuple(sorted(r.strip() for r in reason_str.split(",") if r.strip()))


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
    
    # 메시지 단위 카운트
    action_counter = Counter(log.get("action", "unknown") for log in all_logs)
    
    # 시간 범위
    timestamps = [log.get("timestamp") for log in all_logs if log.get("timestamp")]
    duration = ""
    if timestamps:
        start = datetime.fromtimestamp(min(timestamps)).strftime("%H:%M:%S")
        end = datetime.fromtimestamp(max(timestamps)).strftime("%H:%M:%S")
        duration = f" ({start} ~ {end})"
    
    # 사건 단위 디듀플
    event_logs = [l for l in all_logs if l.get("action") in ("blocked", "modified", "sos")]
    unique_events = deduplicate_events(event_logs)
    
    # 센서별 이상 카운트 (콤마 분리된 reason을 모두 분해)
    sensor_counter = Counter()
    for evt in unique_events:
        for r in evt["reasons"]:
            sensor_counter[r] += 1
    
    # ===== 마크다운 작성 =====
    lines = []
    lines.append(f"## 📋 이벤트 요약{duration}")
    lines.append("")
    lines.append(f"- **총 메시지: {total}개**")
    
    # 메시지 단위 카운트
    for action, count in action_counter.most_common():
        label = ACTION_LABEL.get(action, action)
        lines.append(f"- {label}: {count}개")
    
    # 센서별 이상 (사건 단위)
    if sensor_counter:
        lines.append("")
        lines.append(f"### 🔧 감지된 이상 (실제 사건 {len(unique_events)}건)")
        for reason, count in sensor_counter.most_common():
            label = REASON_LABEL.get(reason, reason)
            lines.append(f"- {label} (`{reason}`): {count}건")
    
    # 모든 사건 위치 표시 (제한 없음)
    if unique_events:
        lines.append("")
        lines.append(f"### 📍 사건 발생 위치 (전체 {len(unique_events)}건)")
        for evt in unique_events:
            label = ACTION_LABEL.get(evt["action"], evt["action"])
            time_str = datetime.fromtimestamp(evt["timestamp"]).strftime("%H:%M:%S")
            reason_labels: list[str] = [
                REASON_LABEL.get(r, r) for r in evt["reasons"] if isinstance(r, str) and r
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
    
    all_logs = []
    
    with open(latest_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                log = json.loads(line)
                if log.get("_event_marker"):
                    continue
                all_logs.append(log)
            except json.JSONDecodeError:
                pass
    
    if not all_logs:
        print("\033[92m🟢 [완벽] 수집된 로그가 없습니다.\033[0m")
        sys.exit(0)
    
    # 요약은 전체 로그로 (메시지 카운트 정확하게)
    summary, unique_events = build_summary(all_logs)
    print("\033[96m" + summary + "\033[0m\n")
    
    if not unique_events:
        print("\033[92m🟢 [완벽] 분석할 사건이 없습니다. 안전 주행!\033[0m")
        sys.exit(0)
    
    # LLM에는 디듀플된 사건 raw + 정상 통과 샘플 10개만
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
        input_variables=["logs"],
        template="""
[중요 규칙 - 반드시 지킬 것]
- 반드시 한국어로만 답변하세요.
- 영어, 중국어, 일본어, 한자(漢字)를 절대 사용하지 마세요.
- 전문 용어도 모두 한국어로 풀어 쓰세요. (예: sensor → 센서, system → 시스템)
- 'pose' 필드의 위치(x, y)를 반드시 분석에 활용하세요.
- 같은 좌표에서 반복 발생 → 정적 장애물, 좌표가 다양 → 동적 요인 또는 센서 이상.
- 'reason'에 콤마로 여러 센서가 섞여 있으면 각각을 모두 언급하세요.
- 위 규칙을 어기면 답변이 폐기됩니다.

당신은 자율주행 휠체어 로봇의 수석 AI 엔지니어입니다.
아래 로그를 분석하고 반드시 아래의 마크다운 표 양식으로 대답하세요.

[운행 로그]
{logs}

## 📊 AI 디버깅 리포트
| 항목 | 분석 결과 |
|---|---|
| 🎯 AI 신뢰도 | [0~100]% (반드시 숫자만 적을 것) |
| 🚨 핵심 원인 | (1~2줄 요약, 한국어로) |
| 🛠️ 조언 | (해결책, 한국어로) |
"""
    )
    chain = prompt | llm
    response = chain.invoke({"logs": state.get("raw_logs", "")})
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
    
    # 터미널 출력
    print("\033[96m\n================= [ 🤖 AI 분석 완료 ] =================\033[0m\n")
    print(report_content)
    
    # 신뢰도 추출 (표 형식 `|` 와 헤딩 형식 `:` 둘 다 매칭)
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
    
    # 리포트 저장
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