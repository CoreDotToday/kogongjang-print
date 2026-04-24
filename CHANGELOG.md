# Changelog

이 프로젝트의 주요 변경 사항은 이 파일에 기록됩니다.
포맷은 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/)를 따르며,
버전 번호는 [Semantic Versioning](https://semver.org/lang/ko/)을 따릅니다.

## [Unreleased]

## [0.2.0] — 2026-04-23

### Added
- **앱 버전·정보 표시** — 메인 창 하단 상태바에 버전·릴리즈 일자를 상시 표시.
  "정보" 버튼 → 모달 About 다이얼로그(헤더 + 정보/릴리즈 노트 탭). 빌드된
  exe는 Windows 탐색기 "속성 → 세부 정보"에서도 버전·제품명·저작권 확인 가능.
- **GUI 라이브 미리보기 패널** — 메인 창 우측에 A4 비율 썸네일이 항상 표시되며,
  배경/폰트/글자 크기/이름 위치 등 어떤 설정을 바꾸든 300ms 후 자동으로
  다시 그립니다. PIL로 직접 합성하므로 빠르고(렌더 ~50ms) PDF 생성을 거치지
  않습니다. 샘플 이름 입력 칸("홍길동" 기본값), "텍스트 영역 표시" 토글 포함.
- **사용자 폰트 추가 기능** — 폰트 콤보 옆 "추가" 버튼으로 TTF/OTF를
  `data/fonts/`에 복사해 사용. 번들 폰트와 자동 합쳐 드롭다운에 표시되며,
  PDF 인쇄에도 동일한 lookup(`find_font()`)으로 즉시 반영됩니다.
- **`data/` 폴더로 사용자 파일 통합** — 그동안 exe 옆에 흩어져 있던
  설정/배경/출력/로그를 하나의 `data/` 폴더로 모았습니다:
  ```
  감사장인쇄.exe
  data/
    ├── config.json
    ├── backgrounds/
    ├── fonts/
    ├── output/
    └── error.log
  ```
  기존 사용자가 업데이트하면 첫 실행 시 `config.json`/`backgrounds/`/`output/`이
  자동으로 `data/` 안으로 이동됩니다.
- **중복 실행 감지 시 종료/재시작 옵션 다이얼로그** — 기존에는 "이미 실행 중"
  안내만 띄우고 종료됐는데, 이제 세 가지 중에서 선택 가능:
  - **정상 종료 후 시작** — 새 `POST /quit` API로 기존 프로세스에 정상 종료
    요청 → 포트 해제 대기 → 새로 시작 (키오스크 Chrome도 함께 정리).
  - **강제 종료 후 시작** — `netstat`/`tasklist`로 PID·프로세스명을 검증한 뒤
    (`감사장인쇄.exe`/`python.exe`/`pythonw.exe`인 경우에만) `taskkill /F /T`로
    트리 종료. 다른 프로그램은 안전을 위해 거부합니다.
  - **취소**
  - 정상 종료가 응답 없으면 강제 종료 escalate 여부를 추가로 확인.
- **`POST /quit` API** — Flask 서버 + GUI + 키오스크 Chrome을 정상 종료.
  PC 전원에는 영향 없음(PC 종료는 기존 `/shutdown`이 담당).

### Changed
- 폰트/배경 경로 lookup을 `find_font()` / `find_background()`로 통일.
  사용자 폴더 우선, 없으면 번들. PDF 생성 코드도 동일 헬퍼 사용.
- 개발자용 `CLAUDE.md`를 현재 아키텍처(빌드 프로세스, 키오스크 구조,
  Nuitka onefile 경로 처리, `data/` 레이아웃)에 맞게 갱신.

### Fixed
- **설정 파일 손상으로 프로그램이 시작되지 않던 문제** — 정전·강제 종료 등으로
  `config.json` 저장이 중간에 끊기면 파일이 NUL 바이트로 채워져 다음 실행 시
  `JSONDecodeError`로 크래시하던 문제를 해결.
  - `save_config()`를 원자적 저장(임시 파일 → `fsync` → `os.replace`) 방식으로 변경.
  - `load_config()`가 손상된 파일을 감지하면 자동으로 `config.json.corrupt`로
    보존하고 기본값으로 복구.
- **`/close-kiosk` API로 Chrome 키오스크가 확실히 닫히지 않던 문제** —
  `Popen.terminate()`가 메인 프로세스만 종료해 자식(GPU/렌더러/네트워크 등)이
  남는 경우가 있었음. 이제 `taskkill /F /T`로 프로세스 트리 전체를 강제 종료하며
  실패 시 기존 `terminate()`로 폴백.

## [0.1.0] — 2026-03-05

첫 정식 내부 릴리즈. 주요 커밋 요약:

### Added
- Nuitka onefile 빌드 스크립트(`build.py`) 및 customtkinter 전환.
- Windows 시작 시 자동 실행 기능(레지스트리 기반).
- Chrome 키오스크 모드 설정(자동 열기·확대율).
- GUI 내 Flask 로그 뷰어.
- `/close-kiosk` API 및 키오스크 종료 버튼.
- 외부 `backgrounds/` 폴더를 통한 커스텀 배경 템플릿 지원.
- 개발자용 프론트엔드 API 가이드(`docs/frontend-api-guide.md`).

### Changed
- 자동 실행 방식을 VBS 스크립트에서 Windows 레지스트리로 전환.
- 하드코딩된 값들을 `config.json` 기반 설정으로 이관.
- Nuitka 빌드 컴파일러를 Zig에서 MinGW64로 변경.

### Fixed
- Nuitka 빌드에 불필요한 패키지(scipy/numpy 등)가 포함되던 문제.

---

*이 이전 히스토리(초기 프로토타입, 기관별 배경 추가 등)는
[git log](https://github.com/)에서 확인할 수 있습니다.*
