// Dummy data for the wheelchair robot admin dashboard
const REPORT_SUMMARIES = [
  { title: "급제동 후 IMU 임계치 초과", body: "복도 B-3 구간에서 보행자 회피 중 급제동 발생. IMU 가속도 2.3g 기록." },
  { title: "Localization 손실 (재획득 12s)", body: "엘리베이터 입구 근처에서 LiDAR feature 부족으로 위치 추정 실패." },
  { title: "비상 정지 버튼 작동", body: "사용자가 SOS 버튼을 직접 눌러 자율주행 즉시 종료. 정상 회수 완료." },
  { title: "위험구역 진입 경고", body: "계단실 근접 zone 진입 감지. 자동으로 회피 경로 재계획." },
  { title: "장애물 회피 지연", body: "동적 장애물 추적이 0.6s 지연되어 안전거리 미달 발생." },
  { title: "센서 헬스 저하 (LiDAR)", body: "LiDAR 패킷 손실률 7%. 케이블 점검 권장." },
  { title: "수동 모드 전환 (보호자 요청)", body: "보호자가 태블릿에서 수동 모드 전환 요청. 정상 처리." },
  { title: "경사로 속도 자동 감속", body: "5도 이상 경사 감지로 0.4 m/s까지 자동 감속." },
  { title: "도킹 실패 후 재시도 성공", body: "충전 도크 정렬 실패 1회 후 재시도하여 정상 도킹 완료." },
  { title: "복도 좌회전 시 진동 이상", body: "복도 A-1 좌회전 구간에서 캐스터 진동 감지. 정비 권장." },
];
// web/src/data.jsx
export const dict = {
  ko: {
    title: "자율주행 휠체어 관제",
    tab_overview: "대시보드",
    tab_live: "실시간 모니터링",
    tab_reports: "진단 보고서",
    btn_stop: "원격 정지 실행",
    status_moving: "이동 중",
    status_stopped: "정지됨",
    // 필요한 텍스트를 계속 추가하세요...
  },
  en: {
    title: "Autonomous Wheelchair Control",
    tab_overview: "Overview",
    tab_live: "Live Monitor",
    tab_reports: "Diagnostics",
    btn_stop: "Execute Remote Stop",
    status_moving: "Moving",
    status_stopped: "Stopped",
    // 필요한 텍스트를 계속 추가하세요...
  }
};
const LEVELS = ["fatal", "warning", "warning", "warning", "warning", "warning"];

function makeReports(n = 24) {
  const out = [];
  const now = new Date("2026-05-08T09:42:00");
  for (let i = 0; i < n; i++) {
    const dt = new Date(now.getTime() - i * (1000 * 60 * (23 + (i * 17) % 240)));
    const level = LEVELS[(i * 3) % LEVELS.length];
    const conf = level === "fatal" ? 78 + ((i * 7) % 18) : 62 + ((i * 11) % 35);
    const meta = REPORT_SUMMARIES[i % REPORT_SUMMARIES.length];
    out.push({
      id: `RPT-2026-${String(2400 - i).padStart(4, "0")}`,
      level,
      datetime: dt.toISOString(),
      confidence: conf,
      has_md: true,
      log_count: 8 + ((i * 5) % 26),
      title: meta.title,
      summary: meta.body,
      location: ["복도 B-3", "엘리베이터 1F", "병실 304 앞", "재활실 입구", "복도 A-1", "로비"][i % 6],
      wheelchair: `WC-${String(7 + (i % 4)).padStart(3, "0")}`,
      user: ["김OO", "이OO", "박OO", "정OO"][i % 4],
    });
  }
  return out;
}

const REPORTS = makeReports(24);

const STATS = {
  total_recent: 14,
  fatal_recent: 2,
  warning_recent: 12,
  avg_confidence: 84,
  by_day: [
    { day: "5/02", fatal: 0, warning: 3 },
    { day: "5/03", fatal: 1, warning: 4 },
    { day: "5/04", fatal: 0, warning: 2 },
    { day: "5/05", fatal: 0, warning: 5 },
    { day: "5/06", fatal: 1, warning: 3 },
    { day: "5/07", fatal: 0, warning: 6 },
    { day: "5/08", fatal: 2, warning: 12 },
  ],
};

// Heatmap incident points relative to a SLAM map (0..100 grid)
const HEAT_POINTS = [
  { x: 22, y: 34, level: "warning", label: "복도 B-3" },
  { x: 23, y: 35, level: "warning" },
  { x: 24, y: 33, level: "fatal", label: "복도 B-3 급제동" },
  { x: 58, y: 28, level: "warning", label: "엘리베이터 1F" },
  { x: 60, y: 27, level: "warning" },
  { x: 60, y: 30, level: "warning" },
  { x: 78, y: 62, level: "fatal", label: "계단실 근접" },
  { x: 41, y: 70, level: "warning", label: "재활실 입구" },
  { x: 42, y: 71, level: "warning" },
  { x: 14, y: 78, level: "warning", label: "병실 304" },
  { x: 36, y: 18, level: "warning", label: "로비" },
  { x: 37, y: 19, level: "warning" },
  { x: 70, y: 80, level: "warning", label: "재활실 후문" },
];

const SAMPLE_MD = `# 사고 분석 보고서 — RPT-2026-2400

**발생 일시**: 2026-05-08 09:24:11 KST
**휠체어**: WC-008 / **사용자**: 김OO
**위치**: 3층 복도 B-3 (x=12.4, y=8.7)
**AI 신뢰도**: \`86%\`

---

## 1. 요약

자율주행 모드로 3층 복도 B-3 구간을 통과하던 중, 보행자 갑작스러운 진입으로
급제동이 발생했습니다. **IMU 가속도 2.3g**가 기록되었으며, 안전 임계치 1.8g를
초과했습니다. 사용자 부상은 없었으며 휠체어 회수 후 정상 운행 재개했습니다.

## 2. 타임라인

| 시각 | 이벤트 | 모드 | 비고 |
|---|---|---|---|
| 09:24:08 | 정상 주행 | 자율 | 0.8 m/s |
| 09:24:10 | 보행자 감지 (1.4m) | 자율 | YOLO conf 0.92 |
| 09:24:11 | 급제동 명령 | 자율 | -3.1 m/s² |
| 09:24:11 | IMU 임계 초과 | 자율 | 2.3g |
| 09:24:13 | 정지 완료 | 수동 | 사용자 의식 정상 |

## 3. 원인 분석

- 보행자가 **사각지대(우측 후방)**에서 진입하여 LiDAR 감지 지연
- 복도 폭 2.1m에서 보행자 거리 1.4m → 안전 마진 부족
- 회피 경로 재계획 시간(0.4s) 동안 감속만으로 대응 불가

## 4. 권장 조치

1. **즉시**: 해당 구간 최대 속도를 0.6 m/s로 일시 제한
2. **단기**: 사각지대 보강을 위한 추가 초음파 센서 점검
3. **중장기**: B-3 구간 보행자 동선과의 분리 검토

> **정비 담당 메모**: WC-008은 지난주에도 동일 구간에서 유사 이벤트 1건.
> 케이스 패턴 분석 권장.`;

// Real-time event templates
const EVENT_TEMPLATES = [
  { type: "nav_status", label: "경로 재계획 완료", level: "info" },
  { type: "zone_change", label: "일반구역 → 위험구역 진입", level: "warning" },
  { type: "zone_change", label: "위험구역 → 일반구역 복귀", level: "info" },
  { type: "safety_alert", label: "보행자 근접 감지 (1.6m)", level: "warning" },
  { type: "sensor_health", label: "LiDAR 패킷 손실률 3%", level: "info" },
  { type: "nav_status", label: "도킹 시퀀스 시작", level: "info" },
  { type: "imu_emergency", label: "IMU 가속도 2.1g 초과", level: "fatal" },
  { type: "localization_lost", label: "Localization 일시 손실", level: "fatal" },
  { type: "sos", label: "사용자 SOS 버튼 작동", level: "fatal" },
  { type: "safety_alert", label: "급경사(5°) 감지 — 자동 감속", level: "warning" },
  { type: "nav_status", label: "목적지 도착", level: "info" },
  { type: "sensor_health", label: "배터리 잔량 62%", level: "info" },
];

window.DASH = {
  REPORTS,
  STATS,
  HEAT_POINTS,
  SAMPLE_MD,
  EVENT_TEMPLATES,
};