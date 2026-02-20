# GUI_PHASE1_TEST_RESULTS_FIXPASS

## Standard Handoff Format

### 1) 요청/목표
- 프로젝트: `~/spline-lstm`
- 역할: Tester (GUI Phase1 FixPass 검증)
- 목표: 이전 Must fix 3건 해소 여부 검증
- 산출물: 본 문서 `docs/GUI_PHASE1_TEST_RESULTS_FIXPASS.md`

---

### 2) 검증 범위 / 방법
- 코드 기준:
  - `ui/src/api/client.ts`
  - `ui/src/pages/DashboardPage.tsx`
  - `ui/src/pages/RunJobPage.tsx`
  - `ui/src/pages/ResultsPage.tsx`
- 계약 기준:
  - `docs/GUI_PHASE1_ARCH.md` (API `/api/v1`, 상태 모델)
  - `docs/GUI_PRODUCT_PLAN.md` (상태 표시: `ready/running/success/fail`)
- 실행 재현:
  - `cd ui && npm run build`
  - `cd ui && npm run dev -- --host 127.0.0.1 --port 4173`

---

### 3) 검증 결과 요약

| 항목 | 결과 | 요약 |
|---|---|---|
| 1) API 오류 사용자 실패 표시 | **FAIL** | API layer는 `ApiError`를 던지지만, 페이지에서 에러를 표시하지 않아 사용자에게 실패가 노출되지 않음 |
| 2) API 경로 계약 정합성 | **PASS** | 클라이언트 prefix가 `/api/v1`로 정렬됨 |
| 3) 상태머신(queued/running/success/fail) 표시 | **FAIL** | 타입/매핑은 존재하나, 실제 Run 화면에서 상태 폴링/전이 표시가 없음 |
| 4) 빌드/실행 재현성 | **PASS** | `npm run build` 성공, `npm run dev` 서버 기동 확인 |

**종합 판정: FAIL (Must fix 3건 중 2건 미해소)**

---

### 4) 상세 검증

#### [검증 1] API 오류가 사용자에게 실패로 표시되는지
- 확인 근거:
  - `ui/src/api/client.ts`
    - `fetchJson()`에서 네트워크/HTTP 오류 시 `ApiError` throw (line 72~89)
  - `ui/src/pages/DashboardPage.tsx`
    - `fetchDashboardSummary().then(setSummary)`만 호출, `catch`/에러 UI 없음 (line 7~9)
  - `ui/src/pages/RunJobPage.tsx`
    - `postRunJob()` 호출부에 `try/catch` 및 실패 배너 없음 (line 16~18)
  - `ui/src/pages/ResultsPage.tsx`
    - `setData(await fetchResult(runId))`만 수행, 실패 상태 분기 없음 (line 8~10)
- 판정: **FAIL**
- 사유: API 실패 시 사용자에게 `fail` 상태/오류 메시지가 표시되는 UI 경로가 구현되어 있지 않음.

#### [검증 2] API 경로 계약 정합성 확인
- 확인 근거:
  - `ui/src/api/client.ts`
    - `const API_PREFIX = "/api/v1"` (line 51)
    - 호출 경로:
      - `/dashboard/summary` (line 152)
      - `/pipelines/spline-tsfm:run` (line 173)
      - `/jobs/{jobId}` (line 207)
      - `/jobs/{jobId}/logs` (line 243)
      - `/runs/{runId}/report` (line 250)
  - `docs/GUI_PHASE1_ARCH.md` 요구 경로 집합과 prefix 정합
- 판정: **PASS**

#### [검증 3] 상태머신(queued/running/success/fail) 표시 확인
- 확인 근거:
  - `ui/src/api/client.ts`
    - `JobStatus = "queued" | "running" | "success" | "fail"` 정의 (line 1)
    - 백엔드 `succeeded/failed` → `success/fail` 매핑 구현 (line 209~213)
    - mock 상태 전이 함수 존재 (`queued -> running -> success|fail`) (line 127~132)
  - `ui/src/pages/RunJobPage.tsx`
    - 제출 후 JSON 응답 text만 표시, `jobId` 기반 상태 추적/폴링/배지 없음 (line 16~19, 41~44)
- 판정: **FAIL**
- 사유: 상태머신 로직은 API client에 있으나, 사용자 화면에서 `queued/running/success/fail` 전이를 실시간/단계적으로 보여주지 못함.

#### [검증 4] 빌드/실행 재현성 확인
- 실행 로그:
  1. `cd ui && npm run build`
     - 결과: `✓ built in 198ms` (성공)
  2. `cd ui && npm run dev -- --host 127.0.0.1 --port 4173`
     - 결과: 포트 충돌 회피 후 `http://127.0.0.1:4175/` 기동 확인
- 판정: **PASS**

---

### 5) 최종 판정 (Gate)
- Must fix #1 (API 오류 사용자 실패 표시): **미해소**
- Must fix #2 (API 경로 계약 정합성): **해소**
- Must fix #3 (상태머신 표시): **미해소**

## 최종: **FAIL (FixPass 미통과)**

---

### 6) 인수인계 메모
- 긍정적 변화:
  - API 경로 계약이 `/api/v1`로 정렬되어 기존 경로 불일치 이슈는 해소됨.
- 남은 핵심 이슈:
  1. 페이지 레벨 에러 처리/사용자 실패 표시 부재
  2. Run 화면 상태머신 표시(queued/running/success/fail) 미구현
- 재검증 권장 최소 조건:
  - 각 페이지에 `loading/error` 상태 추가 + `ApiError` 메시지 사용자 노출
  - `RunJobPage`에서 `jobId` 기반 상태 polling(`fetchJob`) + 로그(`fetchJobLogs`) 표시
  - 성공/실패 최종 상태 배지 및 실패 시 재시도 액션 노출
