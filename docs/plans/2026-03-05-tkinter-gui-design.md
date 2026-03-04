# Tkinter GUI + Flask 통합 설계

## 목표
기존 감사장 인쇄 시스템에 Tkinter GUI를 추가하여 설정 관리와 서버 제어를 편리하게 하고, Nuitka로 단일 exe 배포.

## 구조

```
gui.py              ← 메인 진입점 (Tkinter + Flask 통합)
app.py              ← Flask 라우트, PDF 생성 (config.json에서 설정 로드)
config.json         ← 설정 자동 저장/로드
```

## GUI 기능
- 배경 템플릿 드롭다운 (static/images/background_*.png 자동 스캔)
- 폰트 선택 드롭다운
- 글자 크기, 이름 위치(X, Y) 조정
- SumatraPDF 경로 설정 (자동 탐지 + 찾아보기)
- 서버 포트 설정
- 서버 시작/중지 버튼
- 상태 표시
- 시스템 트레이 최소화 (pystray)

## app.py 변경
- 하드코딩 제거 → config.json에서 읽기
- background.png 심볼릭링크 불필요 → 설정된 파일 직접 사용
- SumatraPDF 경로 config에서 읽기

## config.json
```json
{
  "background": "background_kogongjang.png",
  "font": "nanum.ttf",
  "font_size": 24,
  "name_x": 20,
  "name_y": 300,
  "name_width": 500,
  "name_height": 350,
  "sumatra_path": "auto",
  "port": 5000
}
```

## 빌드
```bash
nuitka --standalone --onefile --enable-plugin=tk-inter gui.py
```
