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

SYSTEM_PROMPT = """
You are debugging and analyzing an autonomous wheelchair ROS2/Nav2 system.

Project Context:
{context}

SYSTEM CONFIGURATION:
System:
  Drive Mode: "Autonomous"
  Map Mode: "Localization"
  Software Version: "v1.4.2"

Hardware:
  Platform: "Autonomous Wheelchair"
  Sensors:
    - LiDAR
    - IMU
    - Ultrasonic Sensor
    - Encoder
    - Camera

ANALYSIS PRINCIPLES:
1. Only detect REAL safety-critical events:
   - blocked
   - sos
   - imu_emergency
   - imu_lost
   - ultrasonic_lost
   - lidar_lost
   - odom_lost
   - localization_emergency

2. Ignore NORMAL robot behavior:
   - "allowed" events
   - normal steering/angular velocity changes
   - small LiDAR/Ultrasonic fluctuations
   - normal localization corrections
   - Korean zone names such as "일반구역" (normal zone)

3. If NO critical safety event exists:
   - Mark the session as CLEAN
   - Write "None observed" in related sections
   - Never invent issues

CRITICAL CONTRADICTION CHECK: 
If you mention "SOS", "blocked", or "emergency" anywhere in your summary, YOU MUST LIST THEIR EXACT TIMESTAMPS in Section 2 and analyze them in Section 4. Do NOT say "No critical events occurred" if you found an SOS or blocked event.

4. Use exact references from the logs:
   - node names
   - timestamps (`time`)

5. Cross-validate sensors:
   - Determine whether the issue is:
     a) real physical obstacle
     b) sensor noise
     c) localization instability
     d) emergency logic overreaction

6. Evaluate response latency:
   - obstacle detection timing
   - slowdown timing
   - blocked/SOS timing
   - recovery timing

7. Focus on passenger safety:
   - sudden stop risk
   - collision possibility
   - passenger instability
   - excessive jerk

8. Include ROS2/Nav2 technical analysis:
   - costmap tuning (inflation radius, obstacle layer behavior)
   - controller frequency
   - EKF tuning & sensor fusion reliability
   - QoS delays & callback timing

9. Include hardware maintenance analysis:
   - motor encoder health
   - caster wheel condition
   - cable communication stability
   - LiDAR cleanliness
   - ultrasonic sensor alignment

10. Distinguish the root cause between:
   - software issue
   - sensor issue
   - hardware issue
   - environmental issue

11. Prioritize realistic robotics engineering analysis.
Do NOT generate generic AI explanations. Write strictly in English.
"""

USER_TEMPLATE = """
SESSION LOGS:
{logs}

OUTPUT FORMAT (MANDATORY):

# Autonomous Wheelchair Log Analysis Report

## 1. Session Overview
Provide a brief summary of the session:
- Overall driving status
- Driving stability
- Occurrence of emergency events
- Overall system health

---

## 2. Timeline & Latency Analysis
Rules:
- Analyze only blocked/sos/emergency events.
- Must use exact `time` values.
- Include analysis of delay times between events.
- Analyze the flow: obstacle → slowdown → emergency.

Include:
- Chronological order of events
- Reaction speed
- Potential control delays
- Emergency response latency

If no events occurred:
"No critical events occurred during this session."

---

## 3. Critical Problem Analysis (Sensor Cross-Validation)
Multi-sensor based analysis:
- LiDAR
- IMU
- Ultrasonic
- Encoder

Analysis details:
- Is it a real collision risk?
- Is it sensor noise?
- Is it a localization issue?
- Is it a false positive?

Mandatory:
- Cross-validate sensor data to explain the situation.
- Perform logic-based analysis, not mere assumptions.

If no issues:
"None observed"

---

## 4. Root Cause Analysis
Analyze each cause using the format below:

- [HIGH] 
- [MEDIUM] 
- [LOW] 

Cause types:
- Sensor issue
- Software issue
- Environmental issue
- Hardware issue
- Nav2 configuration issue

Mandatory: Must be based on actual logs.

---

## 5. Safety Risks & Maintenance Checklist
Include:
- Passenger risk level
- Risk of sudden stops
- Collision probability
- Rollover possibility

Maintenance items:
- LiDAR condition
- Ultrasonic sensor alignment
- Encoder status
- Caster wheels
- Communication cables
- IMU calibration status

If no issues:
"None observed"

---

## 6. Code Fix Proposals
Write in an actionable format:
- Debug logging
- Filtering logic
- Debounce
- Hysteresis
- Watchdog
- Timeout handling

If possible:
- Include specific ROS2 node names.
- Include Nav2-related code improvements.

If no issues:
"None observed"

---

## 7. ROS2 / Nav2 / EKF Improvement Suggestions
Include specific parameter suggestions:
- inflation_radius
- obstacle_range
- raytrace_range
- controller_frequency
- EKF sensor weights
- QoS settings

Include:
- Why it is necessary
- What effect it will have

Example:
- Reduction of unnecessary emergency stops
- Stabilization of obstacle detection
- Reduction of localization drift

If no issues:
"None observed"

---

## 8. Final Summary
Briefly summarize:
- The most critical issue
- Actual risk level
- Priority items to fix
- System stability evaluation

If the session is normal:
"Overall, it was a stable autonomous driving session."

IMPORTANT RULES:
- NEVER analyze "allowed" events as problems.
- NEVER exaggerate normal sensor noise as a problem.
- Analyze based ONLY on actual logs.
- DO NOT invent issues.
- Analyze at the level of an actual ROS2/Nav2 engineer.
- ALL output MUST be in English.

Begin immediately with:
# Autonomous Wheelchair Log Analysis Report
"""

def dedupe_log(raw):
    unique, last_pose = [], None
    for line in raw.split('\n'):
        try:
            e = json.loads(line)
            ts = e.get("timestamp")
            if isinstance(ts, (int, float)):
                e["time"] = datetime.fromtimestamp(ts).strftime("%H:%M:%S.%f")[:-3]
                e.pop("timestamp", None)
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
    raw = Path(log_path).read_text(encoding="utf-8")
    log_excerpt = dedupe_log(raw)
    log_excerpt = filter_critical_events(log_excerpt)

    # 1. 치명적 이벤트 개수 카운트
    critical_count = sum(1 for line in log_excerpt.split('\n')
                         if any(k in line for k in ["blocked", "sos", "emergency", "lost", "sos_trigger"]))
    print(f"📊 Critical events found: {critical_count}")

    # 2. 치명적 이벤트가 하나도 없다면, AI가 환각을 일으키지 않도록 강제 클린 문자열로 교체
    if critical_count == 0:
        log_excerpt = "CLEAN_SESSION_NO_ERRORS"
        print("✅ No critical errors found. Passing clean session flag to AI.")

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

    THINK_LOG.write_text(thinking if thinking else "(no thinking returned)", encoding="utf-8")

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