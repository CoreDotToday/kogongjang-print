# 감사장 인쇄 시스템 (kogongjang-print)

> ⚠️ **이 저장소는 아카이브되었습니다** (2026-07-21).
>
> 이 프로젝트의 기능은 **[coredot-printer](https://github.com/CoreDotToday/coredot-printer)** 프린터 서버 v2.5.0+에 통합되었습니다.
>
> - 감사장 조판·인쇄 → 템플릿 조판 API (`POST /print-template`, 감사장 템플릿 기본 제공)
> - 위치·폰트 조정 → 프린터 서버 GUI [템플릿] 탭의 레이아웃 편집기 (v2.7.0+)
> - PDF+SumatraPDF 인쇄 경로는 PIL 조판 + GDI 직접 인쇄로 대체 (SumatraPDF 불필요)
>
> 최신 배포판: [coredot-printer Releases](https://github.com/CoreDotToday/coredot-printer/releases)

기존 코드·문서는 참고용으로 보존됩니다. 좌표 이전 시 주의: 이 프로젝트의 `name_width`/`name_height` 설정값은 폭·높이가 아니라 **끝좌표(x2/y2)** 의미입니다 (상세: coredot-printer의 `docs/superpowers/specs/2026-07-19-template-printing-design.md` §5).
