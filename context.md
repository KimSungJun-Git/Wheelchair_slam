# 프로젝트 개발 맥락 및 메모리

## 1. 개발 환경 (Environment)
- **OS:** Ubuntu 22.04
- **Framework:** ROS 2 Humble
- **Target Hardware:** Stella N2 / 자율주행 휠체어 로봇 플랫폼
- **주요 라이브러리:** Nav2 Stack, Cartographer (SLAM)

## 2. 핵심 아키텍처 및 설정 (Architecture)
- **SLAM:** 병원 내부 맵 빌드를 위해 Cartographer 파라미터 최적화 적용 중.
- **Navigation:** Nav2 Keepout filter를 활성화하여 동적/정적 진입 금지 구역 관리.
- **Safety:** 제어부 단에서 센서 데이터를 실시간으로 감지하여 안전 정지(Safety stop)를 수행하는 독립 노드 운영.

## 3. 주요 해결 과제 및 에러 로그 (Memory)
- **[이력]** 개발 초기 발생했던 SSH 원격 연결 타임아웃 문제는 포트 포워딩 및 방화벽 규칙 재설정으로 해결 완료.
- **[이력]** 로컬 LLM 환경 테스트를 위해 Ollama 및 Docker 기반의 개발 도구 연동 완료.

## 4. AI 가이드라인 (Rules)
- Python 노드를 작성할 때는 의무적으로 `typing` 모듈을 사용해 명시적 타입 힌팅을 채택할 것.
- 모든 ROS 2 컴포넌트는 `rclpy` 표준 객체 지향 패턴(Class 구조)을 지킬 것.
- 답변을 줄 때는 코드 스니펫과 함께 시스템 구조적 관점의 설명을 포함할 것.