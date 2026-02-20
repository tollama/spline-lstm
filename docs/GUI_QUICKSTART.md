# GUI_QUICKSTART

`~/spline-lstm` GUI(React + Vite + TypeScript) 실행 가이드입니다.

## 1) 위치

- UI 경로: `ui/`
- 엔트리: `ui/src/main.tsx`
- 화면(탭) 3종:
  - Dashboard (상태)
  - Run Job (실행 + 상태/로그 폴링)
  - Results (리포트/메트릭)

## 2) 실행 모드 분리 (dev / stage / prod)

GUI는 `.env.<mode>` 기반으로 환경 프로파일을 분리합니다.

- `development` → `VITE_APP_PROFILE=dev`
- `staging` → `VITE_APP_PROFILE=stage`
- `production` → `VITE_APP_PROFILE=prod`

### A. dev(real/mock) - 기본 개발 모드

```bash
cd ~/spline-lstm/ui
npm install
npm run dev
```

브라우저: <http://localhost:4173>

### B. stage 모드

```bash
cd ~/spline-lstm/ui
npm run dev:stage
```

### C. mock 강제 확인

`ui/.env.development`에서 `VITE_USE_MOCK=true`를 사용하거나, 일시적으로 아래처럼 실행합니다.

```bash
VITE_USE_MOCK=true npm run dev
```

- mock 모드는 `import.meta.env.DEV && VITE_USE_MOCK===true`일 때만 활성화됩니다.
- stage/prod 빌드에서는 자동 mock 폴백을 하지 않습니다.

## 3) API Base URL

기본 API 주소는 `http://localhost:8000` 입니다.

백엔드 스켈레톤 실행은 [`docs/BACKEND_API_SKELETON.md`](./BACKEND_API_SKELETON.md)를 참고하세요.

필요 시 런타임에서 아래 전역값으로 오버라이드할 수 있습니다.

```js
window.__API_BASE_URL__ = "http://localhost:8000";
```

## 4) `/api/v1` 계약 엔드포인트

파일: `ui/src/api/client.ts`

- `GET /api/v1/dashboard/summary`
- `POST /api/v1/pipelines/spline-tsfm:run`
- `GET /api/v1/jobs/{job_id}`
- `GET /api/v1/jobs/{job_id}/logs?offset=0&limit=200`
- `POST /api/v1/jobs/{job_id}:cancel`
- `GET /api/v1/runs/{run_id}/metrics`
- `GET /api/v1/runs/{run_id}/artifacts`
- `GET /api/v1/runs/{run_id}/report`

결과 화면은 `metrics + artifacts + report`를 병합 조회하며, 구형(legacy) `report` 단일 페이로드도 하위호환으로 처리합니다.

### 참고: 응답 형태

클라이언트는 아래 두 형태를 모두 허용합니다.

1. 평탄 응답
```json
{ "job_id": "...", "status": "queued" }
```

2. envelope 응답
```json
{ "ok": true, "data": { "job_id": "...", "status": "queued" } }
```

## 5) 폴링/재시도/타임아웃

- Run Job 화면: 상태/로그 폴링(기본 1.3s 간격)
- 폴링 타임아웃: 90초 초과 시 UI에서 timeout 상태로 전환
- API 요청: 엔드포인트별 timeout/retry 정책 적용
  - 일시 장애(408/429/5xx 등) 중심 재시도
  - 실패 시 상세 에러 메시지(status/code/message) 표시

## 6) 최근 UX 개선 포인트 (2026-02)

- **Run Job 오류 가시성 강화**: `Error Details` 카드에서 API 오류와 실패 메시지를 분리 노출
- **실행 상태/진행률 강화**: 상태 배너 + progress bar 추가 (queued/running/success/fail/canceled 흐름 가시화)
- **Results 아티팩트 가독성 개선**: 타입 분류(metrics/report/model/checkpoint/data/other), 파일명/경로 분리 표기
- **Dashboard 상태 가독성 개선**: Recent Jobs의 상태를 배지 색상으로 표현

## 7) 빌드 / 점검

```bash
cd ~/spline-lstm/ui
npm run build         # production
npm run build:stage   # staging
npm run build:dev     # development
npm run check:pa      # 성능/접근성 보조 체크
```

- 산출물: `ui/dist/`

## 8) 범위

본 구현은 **비파괴적 GUI 고도화(Phase 5 통합 반영)** 범위입니다.
- 기존 파이프라인 코드 변경 없이 UI/API 계약 커버리지 확장(`cancel`, `metrics`, `artifacts`)
- Run Job에서 Phase5 확장 파라미터(`feature_mode`, `target_cols`, `dynamic_covariates`, `export_formats`) 전달
- 실제 운영 전 권장 보강: 인증, 접근제어, E2E 테스트
