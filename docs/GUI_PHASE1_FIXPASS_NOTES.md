# GUI Phase 1 FixPass Notes

## Standard Handoff Format

### 1) 요청/목표
- 프로젝트: `~/spline-lstm`
- 역할: Coder (GUI Phase1 Must-fix Fix Pass)
- 목표: `docs/GUI_PHASE1_REVIEW.md`의 Must fix 3건 해소
  1. API 실패 은닉(mock fallback) 제거 + 명확한 에러 노출
  2. API 계약 경로 `/api/v1/*`로 정합화
  3. 실행 상태/로그/실패 분기(queued/running/success/fail) 추가

---

### 2) 변경 파일
- `ui/src/api/client.ts`
- `ui/src/pages/RunJobPage.tsx`
- `ui/src/pages/DashboardPage.tsx`
- `ui/src/pages/ResultsPage.tsx`
- `ui/src/styles.css`
- `ui/src/vite-env.d.ts`

---

### 3) Must fix별 처리 내용

#### Must #1) API 실패가 mock으로 은닉되는 문제
- 기존: `safeFetch` 실패 시 `null` 반환 후 자동 mock 성공 응답 폴백
- 변경:
  - `ApiError` 도입, 실패 시 예외 발생/전파
  - `fetchJson`에서 네트워크/HTTP 실패를 명시적 에러로 처리
  - 페이지별 에러 표시 추가
    - Dashboard: `Dashboard API 오류: ...`
    - Results: `Results API 오류: ...`
    - Run Job: `API Error: ...`, 실패 메시지 영역
- mock fallback 정책:
  - `import.meta.env.DEV && import.meta.env.VITE_USE_MOCK === "true"`일 때만 허용
  - 즉, 개발 모드 + 명시 플래그가 없으면 mock 미사용

#### Must #2) API 계약 경로 정합화
- 기존 경로: `/api/ui/*`
- 변경 경로(아키텍처 기준 `/api/v1`):
  - `GET /api/v1/dashboard/summary`
  - `POST /api/v1/pipelines/spline-tsfm:run`
  - `GET /api/v1/jobs/{job_id}`
  - `GET /api/v1/jobs/{job_id}/logs?offset=0&limit=200`
  - `GET /api/v1/runs/{run_id}/report`
- `client.ts`에서 `API_PREFIX = "/api/v1"` 단일화

#### Must #3) 실행 상태 추적/로그/실패 분기 추가
- `RunJobPage`에 상태 모델 도입:
  - `queued | running | success | fail`
- 동작:
  - 실행 요청 후 `jobId` 저장
  - `jobs/{job_id}`, `jobs/{job_id}/logs` 주기 poll
  - 터미널 상태(`success`/`fail`) 도달 시 polling 중단
- UI 추가:
  - `Execution Status` 카드 (jobId/runId/status badge)
  - `Failure Message` 카드
  - `Execution Logs` 카드
  - API 에러 표시
- mock 모드에서도 queued→running→success/fail 전이와 로그 생성 지원(개발 검증용)

---

### 4) 검증 결과 (실행/빌드)

#### 명령
- `cd ui && npm run build`

#### 결과
- 1차: `ImportMeta.env` 타입 오류 발생
  - 조치: `ui/src/vite-env.d.ts` 추가 (`/// <reference types="vite/client" />`)
- 2차: 빌드 성공
  - `tsc -b && vite build` 통과
  - 산출물 생성 확인: `ui/dist/*`

---

### 5) 리스크/주의사항
- 백엔드 실제 응답 스키마(`job_id`, `status`, `error_message` 등)가 문서와 다르면 런타임 에러가 노출됨
  - 이번 FixPass의 의도는 "은닉"이 아니라 "명시적 실패"이므로 fail-fast 동작이 정상
- mock 사용 시 반드시 개발 모드에서 `VITE_USE_MOCK=true` 명시 필요

---

### 6) 한 줄 요약
- GUI Phase1 Must-fix 3건(에러 은닉 제거, `/api/v1` 정렬, 상태/로그/실패 분기)을 코드 레벨에서 반영했고, UI 빌드 검증(`npm run build`) 성공함.
