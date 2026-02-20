# GUI Phase4 Coder Notes (Release Hardening)

## 1) Summary
- 환경 프로파일을 `dev/stage/prod`로 분리하고, API base 해석 로직을 중앙화했습니다.
- 에러/로그 표준화를 위해 사용자 메시지 + 내부 로그 키를 함께 기록하는 UI 로깅 유틸을 추가했습니다.
- 성능/접근성 보조 점검 커맨드(`npm run check:pa`)를 추가했습니다.
- 기존 탭 구조/핵심 기능(Dashboard/Run Job/Results)의 동작 계약은 유지했습니다.

## 2) Implemented Changes

### 2.1 Environment profiles
- 추가 파일:
  - `ui/.env.development`
  - `ui/.env.staging`
  - `ui/.env.production`
- 추가 코드:
  - `ui/src/config/env.ts`
  - `ui/src/config/env.test.ts`
- 변경 코드:
  - `ui/src/api/client.ts` (환경값 참조를 중앙 config로 변경)
  - `ui/src/vite-env.d.ts` (Vite env 타입 선언 보강)
  - `ui/package.json` (mode 분리 스크립트 추가)

### 2.2 Error/log standardization
- 추가 코드:
  - `ui/src/observability/logging.ts`
- 적용 키:
  - `ui.dashboard.load_failed`
  - `ui.results.load_failed`
  - `ui.run.submit_failed`
  - `ui.run.poll_failed`
  - `ui.api.retry`
- 반영 위치:
  - `ui/src/pages/DashboardPage.tsx`
  - `ui/src/pages/ResultsPage.tsx`
  - `ui/src/pages/RunJobPage.tsx`

### 2.3 Perf/A11y assist command
- 추가 파일:
  - `ui/scripts/check-perf-a11y.mjs`
- 추가 스크립트:
  - `npm run check:pa`
- 체크 항목(보조):
  - 빌드 산출물 gzip JS/CSS 용량 budget
  - 기본 a11y 회귀 가드(ToastProvider/heading 존재 확인)

### 2.4 Docs update
- 업데이트:
  - `docs/GUI_QUICKSTART.md` (mode 분리, build/check 명령 반영)
- 신규:
  - `docs/GUI_PHASE4_CODER_NOTES.md` (본 문서)

## 3) Build & Validation
- UI 단위 테스트 및 빌드 검증을 수행했습니다.
- 실행 커맨드:
  - `npm run test`
  - `npm run build`
  - `npm run check:pa`

## 4) Compatibility / Regression Notes
- 기존 API 경로(`/api/v1/...`) 및 페이지 플로우는 유지됩니다.
- `window.__API_BASE_URL__` 런타임 오버라이드는 유지됩니다.
- mock 모드 활성화 조건(`DEV && VITE_USE_MOCK===true`)은 유지됩니다.

## 5) Risks / Follow-ups
- `check:pa`는 “보조” 체크이며 정식 접근성 감사(axe/lighthouse) 대체가 아닙니다.
- staging API base(`http://localhost:18000`)는 환경별 실제 배포 주소에 맞게 조정이 필요할 수 있습니다.

## 6) Standard Handoff Format

### What changed
- env profile 분리(dev/stage/prod) + 중앙 config 도입
- UI 에러 로그 표준 키 도입(사용자 메시지/내부 로그 동시 확보)
- 성능/접근성 보조 체크 커맨드 추가
- quickstart 문서 업데이트 + 본 coder notes 작성

### Why it changed
- 릴리즈 하드닝 요구사항(환경 분리, 관측성 강화, 최소 품질 게이트)을 충족하기 위함

### How to verify
```bash
cd ~/spline-lstm/ui
npm install
npm run test
npm run build
npm run check:pa
```

### Rollback plan
- 문제가 있을 경우 아래 단위로 되돌릴 수 있습니다.
  1) env 분리: `ui/src/config/env.ts`, `.env.*`, package scripts 롤백
  2) 로깅 표준화: `ui/src/observability/logging.ts` 및 page 호출부 롤백
  3) 보조 체크: `ui/scripts/check-perf-a11y.mjs` + `check:pa` script 제거
