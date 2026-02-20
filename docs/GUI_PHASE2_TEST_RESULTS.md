# GUI_PHASE2_TEST_RESULTS

## Standard Handoff Format

### 1) 요청/목표
- 프로젝트: `~/spline-lstm`
- 역할: Tester (GUI Phase 2 테스트)
- 목표: **실연동 기준 검증** 또는 **mock-disabled 환경에서 실패 가시성 검증**
- 산출물: 본 문서 `docs/GUI_PHASE2_TEST_RESULTS.md`

---

### 2) 검증 범위 / 방법
- 코드 기준:
  - `ui/src/api/client.ts`
  - `ui/src/pages/RunJobPage.tsx`
  - `ui/src/pages/DashboardPage.tsx`
  - `ui/src/pages/ResultsPage.tsx`
- 계약 기준:
  - `docs/GUI_ARCHITECTURE.md` (API prefix/경로, 상태머신, 오류/재시도/타임아웃 요구)
- 실행 재현:
  1. `cd ui && npm run build`
  2. `cd ui && npm run dev -- --host 127.0.0.1 --port 4173`
  3. `curl -i http://localhost:8000/api/v1/dashboard/summary`

> 이번 실행 시점에는 `localhost:8000` 백엔드가 미기동 상태여서, 실연동 성공 플로우 대신 **mock-disabled 실패 가시성** 중심으로 판정함.

---

### 3) 검증 결과 요약

| 항목 | 결과 | 요약 |
|---|---|---|
| 1) API 경로/계약 정합성 | **PASS(부분)** | UI가 `/api/v1` prefix 및 핵심 엔드포인트(`/dashboard/summary`, `/pipelines/spline-tsfm:run`, `/jobs/{id}`, `/jobs/{id}/logs`, `/runs/{id}/report`)를 일관되게 사용함 |
| 2) 상태머신(queued/running/success/fail) | **PASS(부분)** | 타입/매핑/폴링 전이는 구현됨. 다만 실백엔드 미기동으로 `success` 실증은 미수행 |
| 3) 오류 노출/재시도/timeout 동작 | **FAIL** | 오류 노출은 동작하나, 명시적 재시도 버튼/전략 및 timeout(AbortController 기반) 제어가 없음 |
| 4) 빌드/실행 재현성 | **PASS** | `npm run build` 성공, `npm run dev` 기동 성공 재현 |

**종합 판정: CONDITIONAL FAIL**  
- 이유: Phase 2 핵심 중 “오류 후 복구(재시도/timeout)” 요구가 미충족이며, 실연동 성공 경로는 백엔드 부재로 미검증.

---

### 4) 상세 검증

#### [검증 1] API 경로/계약 정합성
- 확인 근거 (`ui/src/api/client.ts`):
  - `API_PREFIX = "/api/v1"`
  - 호출 경로:
    - `GET /dashboard/summary`
    - `POST /pipelines/spline-tsfm:run`
    - `GET /jobs/{jobId}`
    - `GET /jobs/{jobId}/logs?offset=0&limit=200`
    - `GET /runs/{runId}/report`
- 상태 매핑:
  - 서버 `succeeded/failed` → UI `success/fail` 매핑 구현됨
- 판정: **PASS(부분)**
- 메모: `docs/GUI_ARCHITECTURE.md`에 있는 `/runs/{run_id}/metrics`, `/runs/{run_id}/artifacts`, `:cancel`은 현재 화면에서 직접 사용하지 않음(Phase 확장 항목으로 보임).

#### [검증 2] 상태머신(queued/running/success/fail)
- 확인 근거 (`ui/src/pages/RunJobPage.tsx`):
  - 제출 직후 `queued` 설정
  - `fetchJob + fetchJobLogs` 병행 조회
  - 1.2초 폴링으로 상태 갱신
  - terminal status(`success`,`fail`)에서 폴링 중단
- 확인 근거 (`ui/src/api/client.ts`):
  - 상태 타입 `JobStatus = queued|running|success|fail`
  - 서버 응답 상태 매핑 구현
- 판정: **PASS(부분)**
- 제한: 실백엔드 미기동으로 `success` 종단 상태는 이번 런에서 실증하지 못함.

#### [검증 3] 오류 노출/재시도/timeout
- 오류 노출:
  - API 실패 시 `formatApiError`를 통해 `apiError`, `failureMessage`에 반영됨
  - Run/Dashboard/Results 페이지에서 에러 텍스트 표시 경로 존재
  - **→ PASS**
- 재시도:
  - 자동 재시도(backoff)/수동 재시도 버튼(명시 액션) 없음
  - 현재는 사용자가 폼 재제출로 우회 가능하지만, 구조화된 retry 정책 부재
  - **→ FAIL**
- timeout:
  - `fetch` 호출에 `AbortController`/요청 timeout 미적용
  - 네트워크 단절 시 브라우저 기본 실패에 의존
  - **→ FAIL**
- 종합 판정: **FAIL**

#### [검증 4] 빌드/실행 재현성
- 실행 로그:
  1. `cd ui && npm run build`
     - 결과: `✓ built in 229ms` (성공)
  2. `cd ui && npm run dev -- --host 127.0.0.1 --port 4173`
     - 결과: `VITE ... ready`, `Local: http://127.0.0.1:4173/`
  3. `curl -i http://localhost:8000/api/v1/dashboard/summary`
     - 결과: `curl: (7) Failed to connect ...` (백엔드 미기동 확인)
- 판정: **PASS** (프론트 기준 재현성 확보)

---

### 5) 최종 판정 (Gate)
- API 경로/계약 정합성: **부분 충족**
- 상태머신 표시/전이: **부분 충족**
- 오류 노출/재시도/timeout: **미충족(핵심 결함)**
- 빌드/실행 재현성: **충족**

## 최종: **CONDITIONAL FAIL**
- 실백엔드 가동 후 성공 플로우 재검증 필요
- 재시도/timeout 요구 미충족 상태로는 Phase 2 완료 판정 곤란

---

### 6) 인수인계 메모
1. **즉시 보완 권장 (Must)**
   - `fetchJson`에 timeout 옵션 추가 (`AbortController` + 공통 timeout)
   - Run 화면에 **명시적 재시도 버튼** 추가(마지막 payload 재전송)
2. **실연동 재검증 체크리스트**
   - 백엔드 기동 후 `queued → running → success` 실제 1회 이상 증빙
   - 실패 케이스 1회(의도적 invalid payload)에서 에러 메시지/로그/상태 일치성 확인
3. **판정 업데이트 조건**
   - 위 2개(Must) 반영 + 실연동 성공/실패 각각 1회 증빙 시 Phase 2 Tester 관점 PASS 전환 가능
