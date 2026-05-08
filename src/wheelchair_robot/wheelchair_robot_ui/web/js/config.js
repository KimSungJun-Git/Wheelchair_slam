// ─── 0. ROS / 센서 / 맵 설정 ──────────────────────────────────────
// 운영 환경에 맞게 조정하는 상수들. 코드 수정 없이 이 블록만 만지면 됨.
const ROS_CONFIG = {
  url: 'ws://localhost:9090',  // rosbridge_websocket 주소
};

// 거리 임계값 (meters) — 색상 분기 기준
const DIST_THRESHOLDS = {
  red: 0.5,     // <50cm: 빨강 (위험)
  orange: 0.8,  // 50~80cm: 주황 (주의)
  white: 1.0,   // 80~100cm: 불투명 흰색 (관심)
  // ≥1m: 표시 안 함 (안전)
};

// 맵 좌표 변환 — /map 토픽이 들어오면 자동으로 갱신되는 React state로 관리.
//   토픽이 안 들어오면 아래 기본값 사용.
const DEFAULT_MAP_CONFIG = {
  origin_x: -10.0,        // map.yaml의 origin[0]
  origin_y: -10.0,        // map.yaml의 origin[1]
  pixels_per_meter: 30,   // SVG 1m당 픽셀
  svg_width: 800,
  svg_height: 480,
};

// 라이다 각도 → 5방향 분류 (라이다 0rad이 정면, 반시계가 +)
//   휠체어 정면 ±20°가 'front', 좌측 등.
const LIDAR_SECTORS = [
  { key: 'front',      from: -20, to:  20 },
  { key: 'frontLeft',  from:  20, to:  60 },
  { key: 'left',       from:  60, to: 100 },
  { key: 'frontRight', from: -60, to: -20 },
  { key: 'right',      from: -100, to: -60 },
];

// ─── 1. 블루 테마 토큰 적용 (60:30:10 비율) ────────────────────────
const TOKENS = {
  color: {
    bg: '#F8FAFC', surface: '#FFFFFF', surfaceAlt: '#BFDBFE', surfaceDark: '#191970',
    primary: '#0047AB', primaryDark: '#002F6C', primarySoft: '#BFDBFE', accent: '#3B82F6',
    ink: '#002F6C', inkMuted: '#10367D', inkFaint: '#64748B',
    success: '#10A571', successSoft: '#D8F1E5', warn: '#E6A100', warnSoft: '#FEF08A', danger: '#E5484D', dangerSoft: '#FEE2E2',
    mapBg: '#F1F5F9', mapWall: '#002F6C', mapFloor: '#E2E8F0', mapPath: '#3B82F6', mapPathGhost: '#BFDBFE', mapObstacle: '#E5484D', mapRobot: '#191970',
    line: '#BFDBFE', lineStrong: '#3B82F6',
  },
  radius: { sm: 8, md: 14, lg: 20, xl: 28, pill: 999 },
  shadow: { sm: '0 1px 2px rgba(0,47,108,0.06)', md: '0 4px 14px rgba(0,47,108,0.1)', lg: '0 10px 30px rgba(0,47,108,0.15)' },
  font: { sans: `'Pretendard', sans-serif` },
};

const I18N = { ko: { hello: '안녕하세요', wheresToday: '오늘은 어디로 갈까요?', caregiver: '보호자 연결됨', search: '목적지 검색', goHome: '대기소로 자동 귀환', favorites: '즐겨찾기', myRoom: '내 병실', rehab: '재활치료실', map: '실시간 맵', sos: 'SOS', startRoute: '경로 시작', manual: '수동', auto: '자율', stop: '정지', obstacle: '장애물 감지' } };

// 목적지 라벨 매핑 (활동 로그 표시용) - mode_switch_node.py의 destinations 키와 매칭
const DEST_LABELS = {
  emergency: '응급실(Emergency)',
  room_101: '101호',
  room_102: '102호',
  home: '대기소',
};

// 센서 헬스 표시용 라벨
const SENSOR_LABELS = {
  lidar: '라이다',
  imu: 'IMU',
  odom: '모터',
  ultrasonic_front: '초음파(전)',
  ultrasonic_left: '초음파(좌)',
  ultrasonic_right: '초음파(우)',
};