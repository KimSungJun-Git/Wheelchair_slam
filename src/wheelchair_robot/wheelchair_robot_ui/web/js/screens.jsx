// ─── 4. Screens (Home, Search, Nav, Alert, Joystick) ──────────────
function HomeScreen({ t, onSearch, onGoHome, onSOS, onEndSession }) {
  return (
    <Frame>
      <StatusBar />
      <div style={{ padding: '24px 28px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div><div style={{ fontSize: 18, color: TOKENS.color.inkMuted, fontWeight: 700 }}>{t.hello}, 김민지님</div><div style={{ fontSize: 36, fontWeight: 800, letterSpacing: -0.5, marginTop: 6, color: TOKENS.color.primaryDark }}>{t.wheresToday}</div></div>
        <div style={{ display: 'flex', gap: 10 }}><Pill tone="success" icon="signal" size="lg">{t.caregiver}</Pill></div>
      </div>
      <div style={{ padding: '0 28px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, flex: 1 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <BigButton icon="search" tone="primary" subtitle="병동·시설 검색하기" onClick={onSearch}>{t.search}</BigButton>
          <BigButton icon="home" tone="soft" subtitle="대기소로 이동" onClick={onGoHome}>{t.goHome}</BigButton>
          <Card pad={16} style={{ marginTop: 4 }}>
            <div style={{ fontSize: 17, fontWeight: 800, color: TOKENS.color.inkMuted, marginBottom: 10 }}>{t.favorites}</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <button onClick={onSearch} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '16px', background: TOKENS.color.surfaceAlt, border: 'none', borderRadius: 14, cursor: 'pointer', textAlign: 'left', fontFamily: 'inherit' }}>
                <Icon name="bed" size={24} color={TOKENS.color.primary} />
                <div><div style={{ fontSize: 17, fontWeight: 800, color: TOKENS.color.primaryDark }}>{t.myRoom}</div><div style={{ fontSize: 14, color: TOKENS.color.inkMuted, fontWeight: 600 }}>302호</div></div>
              </button>
              <button onClick={onSearch} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '16px', background: TOKENS.color.surfaceAlt, border: 'none', borderRadius: 14, cursor: 'pointer', textAlign: 'left', fontFamily: 'inherit' }}>
                <Icon name="leaf" size={24} color={TOKENS.color.primary} />
                <div><div style={{ fontSize: 17, fontWeight: 800, color: TOKENS.color.primaryDark }}>{t.rehab}</div><div style={{ fontSize: 14, color: TOKENS.color.inkMuted, fontWeight: 600 }}>2층</div></div>
              </button>
            </div>
          </Card>
        </div>
        <Card pad={0} style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column', cursor: 'pointer', border: `2px solid ${TOKENS.color.line}` }} onClick={onSearch}>
          <div style={{ padding: '14px 18px', borderBottom: `2px solid ${TOKENS.color.line}`, display: 'flex', justifyContent: 'space-between', background: TOKENS.color.surfaceAlt }}>
            <span style={{ fontSize: 17, fontWeight: 800, color: TOKENS.color.primaryDark }}>{t.map}</span><Pill tone="primary" size="sm">실시간</Pill>
          </div>
          <div style={{ flex: 1, background: TOKENS.color.mapBg, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <SlamMap width={480} height={300} showPath={false} pathProgress={0} />
          </div>
        </Card>
      </div>
      
      {/* ⭐ 하단 영역: 중복 제거 및 버튼 나란히 배치 */}
      <div style={{ padding: '16px 28px 24px', display: 'flex', gap: 16 }}>
        <button onClick={onSOS} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '16px 28px', background: TOKENS.color.danger, color: '#fff', border: 'none', borderRadius: 999, fontSize: 19, fontWeight: 800, cursor: 'pointer', fontFamily: 'inherit', boxShadow: '0 8px 16px rgba(229,72,77,0.25)' }}>
          <Icon name="sos" size={26} stroke={2.5} /> {t.sos}
        </button>
        <button onClick={onEndSession} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '16px 28px', background: TOKENS.color.primary, color: '#fff', border: 'none', borderRadius: 999, fontSize: 18, fontWeight: 800, cursor: 'pointer', fontFamily: 'inherit', boxShadow: '0 8px 16px rgba(0,47,108,0.25)' }}>
          <Icon name="check" size={24} stroke={2.5} /> ✨ 오늘의 주행 요약
        </button>
      </div>

    </Frame>
  );
}

function SearchScreen({ t, onBack, onGoHome, onStartRoute }) {
  return (
    <Frame>
      <StatusBar />
      <div style={{ padding: '20px 28px', display: 'flex', alignItems: 'center', gap: 12 }}>
        <button onClick={onBack} style={{ width: 56, height: 56, borderRadius: 28, border: `2px solid ${TOKENS.color.line}`, background: TOKENS.color.surface, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Icon name="chevronLeft" size={28} color={TOKENS.color.primaryDark} /></button>
        <button onClick={onGoHome} style={{ width: 56, height: 56, borderRadius: 28, border: `2px solid ${TOKENS.color.line}`, background: TOKENS.color.surface, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }} title="홈으로"><Icon name="home" size={26} color={TOKENS.color.primaryDark} /></button>
        <div style={{ fontSize: 28, fontWeight: 800, color: TOKENS.color.primaryDark, marginLeft: 4 }}>{t.search}</div>
      </div>
      <div style={{ padding: '0 28px', flex: 1, display: 'grid', gridTemplateColumns: '1.1fr 1fr', gap: 20 }}>
        <div>
          <div style={{ fontSize: 15, fontWeight: 800, color: TOKENS.color.inkMuted, marginBottom: 12 }}>추천 목적지</div>
          {/* Python 노드에 있는 좌표 딕셔너리 키값 ('emergency', 'room_101', 'room_102' 등)을 전달하도록 구성 */}
          <Card pad={16} style={{ display: 'flex', alignItems: 'center', gap: 16, cursor: 'pointer', border: `2px solid ${TOKENS.color.primary}` }} onClick={() => onStartRoute('emergency')}>
            <div style={{ width: 52, height: 52, borderRadius: 16, background: TOKENS.color.primary, color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Icon name="bed" size={26} stroke={2.5} /></div>
            <div style={{ flex: 1 }}><div style={{ fontSize: 19, fontWeight: 800, color: TOKENS.color.primaryDark }}>응급실(Emergency)</div><div style={{ fontSize: 15, color: TOKENS.color.inkMuted, fontWeight: 600 }}>1층 서관 · 120m</div></div>
            <Icon name="chevronRight" size={28} color={TOKENS.color.primary} />
          </Card>
          <div style={{ height: 10 }} />
          <Card pad={16} style={{ display: 'flex', alignItems: 'center', gap: 16, cursor: 'pointer', border: `2px solid ${TOKENS.color.line}` }} onClick={() => onStartRoute('room_101')}>
            <div style={{ width: 52, height: 52, borderRadius: 16, background: TOKENS.color.surfaceAlt, color: TOKENS.color.primaryDark, display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Icon name="bed" size={26} stroke={2.5} /></div>
            <div style={{ flex: 1 }}><div style={{ fontSize: 19, fontWeight: 800, color: TOKENS.color.primaryDark }}>101호</div><div style={{ fontSize: 15, color: TOKENS.color.inkMuted, fontWeight: 600 }}>2층 동관 · 65m</div></div>
            <Icon name="chevronRight" size={28} color={TOKENS.color.inkMuted} />
          </Card>
        </div>
        <Card pad={0} style={{ display: 'flex', flexDirection: 'column', border: `2px solid ${TOKENS.color.line}` }}>
          <div style={{ flex: 1, background: TOKENS.color.mapBg }}><SlamMap width={460} height={320} showPath={true} pathProgress={0} destination={{ x: 680, y: 150, label: '목적지' }} /></div>
          <div style={{ padding: '16px 20px', borderTop: `2px solid ${TOKENS.color.line}`, display: 'flex', alignItems: 'center', gap: 12, background: TOKENS.color.surfaceAlt }}>
            <div style={{ flex: 1 }}><div style={{ fontSize: 14, color: TOKENS.color.inkMuted, fontWeight: 700 }}>거리 · ETA</div><div style={{ fontSize: 22, fontWeight: 800, color: TOKENS.color.primaryDark }}>128m · 2분 20초</div></div>
            <button onClick={() => onStartRoute('emergency')} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '18px 28px', background: TOKENS.color.primary, color: '#fff', border: 'none', borderRadius: 999, fontSize: 18, fontWeight: 800, cursor: 'pointer', fontFamily: 'inherit', boxShadow: TOKENS.shadow.md }}>
              {t.startRoute} <Icon name="arrowRight" size={24} stroke={2.5} />
            </button>
          </div>
        </Card>
      </div>
    </Frame>
  );
}

function NavScreen({ t, mode, distances, robotWorld, mapConfig, onBack, onGoHome, onStop, onManual, onAuto }) {
  return (
    <Frame bg={TOKENS.color.mapFloor}>
      <div style={{ position: 'absolute', inset: 0, background: TOKENS.color.mapBg }}>
        <SlamMap width={1024} height={720} showPath={true} pathProgress={0.42} destination={{ x: 680, y: 150, label: '이동중' }} robotWorld={robotWorld} mapConfig={mapConfig} />
      </div>
      <div style={{ position: 'relative', zIndex: 2, display: 'flex', padding: '20px 24px', gap: 12 }}>
        <button onClick={onBack} style={{ width: 56, height: 56, borderRadius: 28, background: 'rgba(255,255,255,0.95)', border: `2px solid ${TOKENS.color.line}`, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Icon name="chevronLeft" size={28} color={TOKENS.color.primaryDark} /></button>
        <button onClick={onGoHome} style={{ width: 56, height: 56, borderRadius: 28, background: 'rgba(255,255,255,0.95)', border: `2px solid ${TOKENS.color.line}`, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }} title="홈으로"><Icon name="home" size={26} color={TOKENS.color.primaryDark} /></button>
        <Card pad={0} style={{ padding: '16px 24px', background: TOKENS.color.primary, color: '#fff', display: 'flex', alignItems: 'center', gap: 12 }}><Icon name="pin" size={26} stroke={2.5} /> <span style={{ fontWeight: 800, fontSize: 20 }}>목적지로 이동 중</span></Card>
      </div>
      <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, padding: 24, zIndex: 2, display: 'flex', justifyContent: 'center', gap: 16 }}>
        <div style={{ display: 'flex', gap: 12, background: 'rgba(255,255,255,0.98)', padding: 12, borderRadius: 28, boxShadow: TOKENS.shadow.lg, border: `2px solid ${TOKENS.color.line}` }}>
          <div style={{ display: 'flex', background: TOKENS.color.surfaceAlt, borderRadius: 999, padding: 4 }}>
            <button onClick={onManual} style={{ padding: '18px 28px', border: 'none', borderRadius: 999, background: mode === 'manual' ? TOKENS.color.primary : 'transparent', color: mode === 'manual' ? '#fff' : TOKENS.color.primaryDark, fontSize: 18, fontWeight: 800, cursor: 'pointer', fontFamily: 'inherit' }}>{t.manual}</button>
            <button onClick={onAuto} style={{ padding: '18px 28px', border: 'none', borderRadius: 999, background: mode === 'auto' ? TOKENS.color.primary : 'transparent', color: mode === 'auto' ? '#fff' : TOKENS.color.primaryDark, fontSize: 18, fontWeight: 800, cursor: 'pointer', fontFamily: 'inherit' }}>{t.auto}</button>
          </div>
          <button onClick={onStop} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '18px 32px', background: TOKENS.color.danger, color: '#fff', border: 'none', borderRadius: 999, fontSize: 18, fontWeight: 800, cursor: 'pointer', fontFamily: 'inherit', boxShadow: '0 4px 12px rgba(229,72,77,0.3)' }}><Icon name="stop" size={22} stroke={2.5} /> {t.stop}</button>
        </div>
      </div>
      <ObstacleProximity distances={distances} />
    </Frame>
  );
}

// 알림 사유별 헤더·메시지·아이콘·색상 매핑
// reason: 'obstacle_too_close' | 'obstacle_cleared' | 'keepout_violation'
//       | 'imu_emergency' | 'localization_lost' | 'user_stop' | 'sos' | null
const ALERT_INFO = {
  obstacle_too_close: {
    title: '⚠️ 전방 장애물 감지',
    subtitle: '안전을 위해 자율 주행이 일시 중단되었습니다.',
    tone: 'warn',
  },
  keepout_violation: {
    title: '🚫 금지구역 진입',
    subtitle: '진입할 수 없는 구역입니다. 다른 경로를 선택하세요.',
    tone: 'danger',
  },
  imu_emergency: {
    title: '🚨 휠체어 자세 위험',
    subtitle: '기울기 또는 충격이 감지되어 정지했습니다. 휠체어 상태를 확인하세요.',
    tone: 'danger',
  },
  localization_lost: {
    title: '📍 위치 추적 분실',
    subtitle: '현재 위치를 찾을 수 없습니다. 시스템이 재인식을 시도 중입니다.',
    tone: 'danger',
  },
  user_stop: {
    title: '🛑 사용자 정지',
    subtitle: '주행이 정지되었습니다. 다음 동작을 선택하세요.',
    tone: 'warn',
  },
  sos: {
    title: '🆘 SOS 호출됨',
    subtitle: '보호자와 관제실에 알림이 전달되었습니다.',
    tone: 'danger',
  },
  default: {
    title: '주행 일시 중단',
    subtitle: '다음 동작을 선택하세요.',
    tone: 'warn',
  },
};

function AlertScreen({ t, alertReason, robotWorld, mapConfig, onResume, onManual, onBack, onGoHome, onGoHomeBase }) {
  const info = ALERT_INFO[alertReason] || ALERT_INFO.default;
  const C = TOKENS.color;
  // tone에 따라 헤더 배경·테두리·아이콘 색상 분기
  const isDanger = info.tone === 'danger';
  const headerBg = isDanger ? C.dangerSoft : C.warnSoft;
  const headerBorder = isDanger ? C.danger : C.warn;
  const headerFg = isDanger ? '#7a1f22' : '#6b4a00';
  const iconBg = isDanger ? C.danger : C.warn;
  // imu_emergency·localization_lost는 자율 재개가 위험할 수 있어 비활성화
  const resumeDisabled = alertReason === 'imu_emergency' || alertReason === 'localization_lost' || alertReason === 'keepout_violation';
  return (
    <Frame>
      <StatusBar />
      <div style={{ background: headerBg, padding: '20px 32px', display: 'flex', alignItems: 'center', gap: 18, borderBottom: `2px solid ${headerBorder}` }}>
        <button onClick={onBack} style={{ width: 48, height: 48, borderRadius: 24, border: `2px solid ${headerBorder}`, background: '#fff', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Icon name="chevronLeft" size={24} color={headerFg} /></button>
        <button onClick={onGoHome} style={{ width: 48, height: 48, borderRadius: 24, border: `2px solid ${headerBorder}`, background: '#fff', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }} title="홈으로"><Icon name="home" size={22} color={headerFg} /></button>
        <div style={{ width: 56, height: 56, borderRadius: 28, background: iconBg, color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}><Icon name="alert" size={30} stroke={2.5} /></div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0, flex: 1 }}>
          <div style={{ fontSize: 22, fontWeight: 800, color: headerFg, letterSpacing: -0.3, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{info.title}</div>
          <div style={{ fontSize: 14, fontWeight: 700, color: headerFg, opacity: 0.85, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{info.subtitle}</div>
        </div>
      </div>
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '1.3fr 1fr', gap: 20, padding: 24 }}>
        <Card pad={0} style={{ display: 'flex', flexDirection: 'column', border: `2px solid ${TOKENS.color.line}` }}><SlamMap width={600} height={400} showPath={true} showObstacles={true} pathProgress={0.45} destination={{ x: 680, y: 150, label: '목적지' }} robotWorld={robotWorld} mapConfig={mapConfig} /></Card>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <Card pad={24} style={{ border: `2px solid ${TOKENS.color.line}` }}>
            <div style={{ fontSize: 16, color: TOKENS.color.inkMuted, fontWeight: 800, marginBottom: 16 }}>권장 조치</div>
            {!resumeDisabled && <>
              <BigButton tone="primary" icon="check" subtitle="우회 경로로 주행 재개" onClick={onResume}>자율 주행 재개</BigButton>
              <div style={{ height: 12 }} />
            </>}
            <BigButton tone="soft" icon="home" subtitle="직접 안전하게 조작" onClick={onManual}>{t.manual} 모드 전환</BigButton>
            <div style={{ height: 12 }} />
            <BigButton tone="soft" icon="home" subtitle="대기소로 자동 돌아가기" onClick={onGoHomeBase}>홈으로 이동</BigButton>
          </Card>
        </div>
      </div>
    </Frame>
  );
}

// ─── 5. 수동 주행 화면 (조이스틱 & 토픽 반복 발행) ────────────────
function JoystickScreen({ t, robotWorld, mapConfig, onBack, onGoHome, setMode, cmdVelPub }) {
  const C = TOKENS.color;
  const [activeBtn, setActiveBtn] = React.useState(null);
  const intervalRef = React.useRef(null);

  // 설정 속도
  const SPEED_LINEAR = 0.3; // m/s
  const SPEED_ANGULAR = 0.5; // rad/s

  const publishCmd = (dir) => {
    if (!cmdVelPub) return;
    let twist = new ROSLIB.Message({ linear: {x:0, y:0, z:0}, angular: {x:0, y:0, z:0} });
    if (dir === 'fwd') twist.linear.x = SPEED_LINEAR;
    if (dir === 'rev') twist.linear.x = -SPEED_LINEAR;
    if (dir === 'left') twist.angular.z = SPEED_ANGULAR;
    if (dir === 'right') twist.angular.z = -SPEED_ANGULAR;
    cmdVelPub.publish(twist);
  };

  const startMove = (dir) => {
    setActiveBtn(dir);
    publishCmd(dir); // 첫 발송
    // 누르고 있는 동안 파이썬 timeout(0.5s)에 걸리지 않게 0.1초마다 반복 전송
    if (intervalRef.current) clearInterval(intervalRef.current);
    intervalRef.current = setInterval(() => publishCmd(dir), 100);
  };

  const stopMove = () => {
    setActiveBtn(null);
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (cmdVelPub) {
      cmdVelPub.publish(new ROSLIB.Message({ linear: {x:0, y:0, z:0}, angular: {x:0, y:0, z:0} }));
    }
  };

  const bindEvents = (dir) => ({
    onMouseDown: () => startMove(dir), onMouseUp: stopMove, onMouseLeave: stopMove,
    onTouchStart: (e) => { e.preventDefault(); startMove(dir); }, onTouchEnd: (e) => { e.preventDefault(); stopMove(); },
  });

  return (
    <Frame bg={C.bg}>
      <div style={{ display: 'flex', justifyContent: 'space-between', padding: '24px 28px', gap: 20 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <button onClick={onBack} style={{ width: 64, height: 64, borderRadius: 32, background: C.surface, border: `2px solid ${C.lineStrong}`, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}>
              <Icon name="chevronLeft" size={32} color={C.primaryDark} stroke={2.5} />
            </button>
            <button onClick={onGoHome} style={{ width: 64, height: 64, borderRadius: 32, background: C.surface, border: `2px solid ${C.lineStrong}`, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }} title="홈으로">
              <Icon name="home" size={28} color={C.primaryDark} stroke={2.5} />
            </button>
            <div>
              <div style={{ fontSize: 28, fontWeight: 800, color: C.primaryDark }}>수동 주행 모드</div>
              <div style={{ fontSize: 16, color: C.inkMuted, fontWeight: 600, marginTop: 4 }}>화면의 큰 버튼을 눌러 직접 조작하세요.</div>
            </div>
          </div>
          <button onClick={() => { setMode(); onBack(); }} style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, padding: '16px 28px', background: C.primary, color: '#fff', border: 'none', borderRadius: 999, fontSize: 18, fontWeight: 800, cursor: 'pointer', width: 'fit-content', boxShadow: TOKENS.shadow.sm }}>
            <Icon name="play" size={20} stroke={2.5} /> 자율 모드로 복귀
          </button>
        </div>

        <Card pad={0} style={{ width: 320, height: 180, overflow: 'hidden', border: `3px solid ${C.primarySoft}`, display: 'flex', flexDirection: 'column', boxShadow: TOKENS.shadow.md }}>
          <div style={{ padding: '10px 16px', background: C.primaryDark, color: '#fff', fontSize: 15, fontWeight: 800, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}><Icon name="map" size={18} /> 주변 미니맵</span>
            <span style={{ color: C.warnSoft, fontSize: 13 }}>수동 제어 중</span>
          </div>
          <div style={{ flex: 1, background: C.mapBg }}>
             <SlamMap width="100%" height="100%" showPath={false} robotWorld={robotWorld} mapConfig={mapConfig} />
          </div>
        </Card>
      </div>

      <div style={{ flex: 1, padding: '0 28px 28px', display: 'flex', flexDirection: 'column', gap: 20 }}>
        <button {...bindEvents('fwd')} style={{ flex: 1.5, borderRadius: 32, border: 'none', background: activeBtn === 'fwd' ? C.primaryDark : C.primary, color: '#fff', fontSize: 40, fontWeight: 800, fontFamily: 'inherit', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16, cursor: 'pointer', transition: 'background 0.1s', boxShadow: activeBtn === 'fwd' ? 'inset 0 10px 20px rgba(0,0,0,0.4)' : `0 16px 40px rgba(0,71,171,0.25)` }}>
          <Icon name="arrowRight" size={72} stroke={3} style={{ transform: 'rotate(-90deg)' }} />
          누르고 있으면 전진
        </button>

        <div style={{ display: 'flex', gap: 20, flex: 1 }}>
          <button {...bindEvents('left')} style={{ flex: 1, borderRadius: 28, border: `3px solid ${activeBtn === 'left' ? C.primary : C.primarySoft}`, background: activeBtn === 'left' ? C.primarySoft : C.surface, color: C.primaryDark, fontSize: 26, fontWeight: 800, fontFamily: 'inherit', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, cursor: 'pointer', transition: 'all 0.1s' }}>
            <Icon name="arrowRight" size={56} stroke={2.5} style={{ transform: 'rotate(180deg)' }} /> 왼쪽 틀기
          </button>
          <button {...bindEvents('rev')} style={{ flex: 1.2, borderRadius: 28, border: 'none', background: activeBtn === 'rev' ? '#c83a3f' : C.danger, color: '#fff', fontSize: 30, fontWeight: 800, fontFamily: 'inherit', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, cursor: 'pointer', transition: 'background 0.1s', boxShadow: activeBtn === 'rev' ? 'inset 0 8px 16px rgba(0,0,0,0.3)' : '0 8px 24px rgba(229,72,77,0.25)' }}>
            <Icon name="arrowRight" size={56} stroke={3} style={{ transform: 'rotate(90deg)' }} /> 누르고 있으면 후진
          </button>
          <button {...bindEvents('right')} style={{ flex: 1, borderRadius: 28, border: `3px solid ${activeBtn === 'right' ? C.primary : C.primarySoft}`, background: activeBtn === 'right' ? C.primarySoft : C.surface, color: C.primaryDark, fontSize: 26, fontWeight: 800, fontFamily: 'inherit', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, cursor: 'pointer', transition: 'all 0.1s' }}>
            <Icon name="arrowRight" size={56} stroke={2.5} /> 오른쪽 틀기
          </button>
        </div>
      </div>
    </Frame>
  );
}