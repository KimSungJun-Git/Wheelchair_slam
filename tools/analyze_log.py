import sys
import json
import re
from datetime import datetime
from pathlib import Path
import chromadb
import requests
from sentence_transformers import SentenceTransformer

DB_PATH = Path.home() / "wheelchair_ws" / "tools" / "chroma_db"
THINK_LOG = Path.home() / "wheelchair_ws" / "tools" / "last_thinking.log"

model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2", device="cpu")
client = chromadb.PersistentClient(path=str(DB_PATH))
collection = client.get_collection("wheelchair_ctx")

SYSTEM_PROMPT = """You are debugging the wheelchair_robot ROS2 Nav2 system.

Project context (auto-retrieved from the actual codebase):
{context}

ANALYSIS PRINCIPLES:
1. Only flag REAL safety events: blocked, sos, imu_emergency, imu_lost,
   ultrasonic_lost, lidar_lost, odom_lost, localization_emergency.
2. Ignore the following — they are NORMAL behavior, not problems:
   - "allowed" events (the robot is moving correctly)
   - Small variations in F/L/R distance readings (lidar/ultrasonic noise)
   - Angular velocity changes (the robot is turning)
   - Korean text in zone field (e.g. "일반구역" means "normal zone" — NOT an error)
3. If the session has NO blocked/sos/emergency events, it is a CLEAN session.
   Write "None observed" for problem-related sections. DO NOT invent issues.
4. Reference specific node names (mode_switch_node, safety_stop_node) and
   exact `time` values from the logs. Output in English."""

USER_TEMPLATE = """LOGS:
{logs}

OUTPUT FORMAT (MANDATORY):

## 1. Timeline
List ONLY blocked/sos/emergency events using the `time` field.
If none exist, write "No critical events in this session."

## 2. Critical Problems

## 3. Root Causes
Mark each with confidence: [HIGH] / [MEDIUM] / [LOW]

## 4. Safety Risks

## 5. Code Fixes

## 6. Parameter Changes

If a section has no content, write exactly "None observed".
DO NOT invent issues from "allowed" events or normal sensor noise.
Begin with `## 1. Timeline` immediately."""

def dedupe_log(raw):
    unique, last_pose = [], None
    for line in raw.split('\n'):
        try:
            e = json.loads(line)
            ts = e.get("timestamp")
            if isinstance(ts, (int, float)):
                e["time"] = datetime.fromtimestamp(ts).strftime("%H:%M:%S.%f")[:-3]
                e.pop("timestamp", None)  # raw 숫자 제거 → R1 혼란 방지
            if e.get("source") != "Navigation" or e.get("pose") != last_pose:
                unique.append(json.dumps(e, ensure_ascii=False))
                last_pose = e.get("pose")
        except Exception:
            if line.strip():
                unique.append(line)
    return '\n'.join(unique[-200:])

def extract_keywords(log_text):
    keywords = set()
    for line in log_text.split('\n'):
        try:
            e = json.loads(line)
            if e.get("reason"):
                keywords.add(e["reason"].split(":")[0].strip())
            if e.get("source"):
                keywords.add(e["source"])
            if e.get("action") in ("blocked", "sos"):
                keywords.add(e["action"])
        except Exception:
            pass
    return " ".join(keywords)

def filter_critical_events(log_text):
    """Critical 이벤트만 추출. allowed는 최근 5개만 샘플."""
    critical, allowed_sample = [], []
    for line in log_text.split('\n'):
        try:
            e = json.loads(line)
            action = e.get("action", "")
            if action in ("blocked", "sos") or e.get("source") == "sos_trigger":
                critical.append(line)
            elif action == "allowed":
                allowed_sample.append(line)
        except Exception:
            if line.strip():
                critical.append(line)
    # critical 전부 + allowed 샘플 5개만 (중복 라이다 데이터 노이즈 방지)
    return '\n'.join(critical + allowed_sample[-5:])

def get_context(log_text, top_k=5):
    query = extract_keywords(log_text) or log_text[:500]
    print(f"🔍 RAG query: {query}")
    emb = model.encode([query]).tolist()
    res = collection.query(query_embeddings=emb, n_results=top_k)
    docs = res.get("documents")
    if not docs or not docs[0]:
        return ""
    return "\n---\n".join(docs[0])

def analyze(log_path):
    raw = Path(log_path).read_text()
    log_excerpt = dedupe_log(raw)
    log_excerpt = filter_critical_events(log_excerpt)

    # critical 이벤트가 0개면 일찍 종료
    critical_count = sum(1 for line in log_excerpt.split('\n')
                         if '"action": "blocked"' in line or '"action": "sos"' in line)
    print(f"📊 Critical events found: {critical_count}")

    context = get_context(log_excerpt, top_k=5)

    print("🤖 Calling deepseek-r1:7b with thinking enabled (60-120s)...")
    r = requests.post("http://localhost:11434/api/chat", json={
        "model": "deepseek-r1:7b",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT.format(context=context)},
            {"role": "user", "content": USER_TEMPLATE.format(logs=log_excerpt)},
        ],
        "stream": False,
        "think": True,
        "options": {
            "num_predict": 4096,
            "num_ctx": 8192,
            "temperature": 0.2,
        }
    }, timeout=900)

    data = r.json()
    msg = data.get("message", {})
    answer = msg.get("content", "")
    thinking = msg.get("thinking", "")

    if not thinking:
        m = re.search(r'<think>(.*?)</think>', answer, re.DOTALL)
        if m:
            thinking = m.group(1).strip()
            answer = re.sub(r'<think>.*?</think>', '', answer, flags=re.DOTALL).strip()

    THINK_LOG.write_text(thinking if thinking else "(no thinking returned)")

    print("\n" + "=" * 60)
    print(answer)
    print("=" * 60)
    print(f"\n💭 Reasoning trace -> {THINK_LOG}")
    print(f"💭 Thinking length: {len(thinking)} chars")

    out_path = Path(log_path).with_name(Path(log_path).stem + "_r1_diagnosis.md")
    out_path.write_text(answer, encoding="utf-8")
    print(f"💾 Saved: {out_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_log.py <log_file>")
        sys.exit(1)
    analyze(sys.argv[1])
