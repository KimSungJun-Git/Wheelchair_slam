# Wheelchair Admin Dashboard

ROS2 자율주행 휠체어의 운행 로그(`~/wheelchair_ws/driving_data/`)를 읽어
관리자/보호자/정비 담당이 보는 웹 대시보드.

```
wheelchair_admin_dashboard/
├── server.py          # FastAPI 백엔드 (단일 스크립트)
├── README.md
└── web/
    ├── Dashboard.html
    ├── sample_data/   # 백엔드 없이 미리보기용 샘플
    └── src/
        ├── api.jsx
        ├── shell.jsx
        ├── overview.jsx
        ├── reports.jsx
        ├── live.jsx
        └── styles.css
```

---

## 1. 백엔드 (server.py) 실행

```bash
pip install fastapi uvicorn
python3 server.py
# 기본 포트 8090. 데이터 폴더는 ~/wheelchair_ws/driving_data
```

옵션:

```bash
python3 server.py --port 8090 --data-dir ~/wheelchair_ws/driving_data
python3 server.py --reload                          # dev autoreload
WHEELCHAIR_DATA_DIR=/path/to/data python3 server.py # 환경변수
```

CORS는 `*`로 열려 있어 정적 호스팅된 웹 페이지에서 바로 호출 가능.

### 엔드포인트

| Method | Path | 설명 |
|---|---|---|
| GET | `/api/health` | 폴더 존재·세션 개수·최신 파일 |
| GET | `/api/reports` | 보고서 메타 목록 (id, 시간, action 카운트, AI 신뢰도) |
| GET | `/api/report/{id}` | 세션 상세 (events + raw_lines + markdown) |
| GET | `/api/events?hours=24` | 시간 윈도우 통계 (by_day, by_hour, by_severity, reasons, sessions) |
| GET | `/api/live` | 최신 세션의 마지막 pose + 이벤트 스트림 |

### 스키마 처리

`log_collector_node.py` 출력의 한 줄(`{action, reason, pose, zone, ...}`)을 그대로 받아:

1. `(timestamp, source, action, reason)` 4-튜플로 메시지 중복 제거
2. `action ∈ {blocked, modified, sos}`만 사건으로 추출
3. 같은 `(action, reason_key)`가 5초 내 반복되면 1건으로 디듀플 (`agent_analyzer.py`와 동일 규칙)
4. `reason`의 콜론 분기(`imu_기울기:roll=…`)는 키만 분리해 라벨링
5. `_report.md`에서 정규식으로 `AI 신뢰도 | 75%` 추출

---

## 2. 프런트엔드 실행

### 옵션 A — 백엔드와 같이 (권장)

```bash
cd wheelchair_admin_dashboard
python3 server.py &
cd web
python3 -m http.server 8000
# → http://localhost:8000/Dashboard.html
```

좌상단 "백엔드 연결됨 · localhost:8090" 배지가 뜨면 라이브 데이터입니다.

### 옵션 B — 샘플 모드 (백엔드 없이 미리보기)

`Dashboard.html`을 그대로 정적 호스팅하면, `localhost:8090`이 죽어 있을 때
`web/sample_data/[주행로그]_*.json`을 클라이언트에서 직접 파싱해 같은 화면을
보여줍니다. 헤더에 "샘플 모드" 배지가 표시됩니다.

```bash
cd web && python3 -m http.server 8000
```

> file:// 로 열면 `fetch('sample_data/...')` 가 차단되니 반드시 로컬 서버로 띄워주세요.

---

## 3. 화면 구성

- **개요** — 24/72/168시간 윈도우 토글, action 기반 위험/주의 스택 차트, reason 키 별 막대, SLAM 좌표 히트맵
- **보고서** — 세션 카드 목록(필터: 위험/주의 + 신뢰도 슬라이더 + 검색) ↔ 우측 마크다운 렌더 + 큰 신뢰도 막대 + 원본 JSON Lines 토글. 신뢰도 50% 미만이면 "추가 데이터 수집 필요" 배너
- **실시간 모니터** — `/api/live` 2Hz 폴링, 로봇 현재 pose + 이동 궤적, 최근 30개 이벤트 스트림(신규는 슬라이드인), 원격 정지(확인 다이얼로그 → `/sos_trigger` 발행 자리)

---

## 4. 다음 단계 (백엔드 보강 메모)

- `/api/live`는 현재 "최신 JSON 파일의 마지막 줄"을 폴링하는 방식. 진짜 실시간을 원하면 ROS2 노드(`amcl_pose`, `safety_action`, `sos_trigger` 직접 구독)에서 SSE / WebSocket으로 push하도록 확장.
- 원격 정지 버튼은 UI만 준비됨. 실제 토픽 발행은 별도 ROS2 브리지(rosbridge_server) 또는 server.py 안에 `rclpy` 노드를 띄워 처리.
- 보호자 공유는 dialog UI만 있으므로, SMTP/카카오톡 알림 어댑터를 `/api/share/{report_id}` POST로 추가.
