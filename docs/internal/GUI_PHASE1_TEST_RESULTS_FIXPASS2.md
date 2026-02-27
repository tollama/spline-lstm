# GUI_PHASE1_TEST_RESULTS_FIXPASS2

## Standard Handoff Format

### 1) 요청/목표
- 프로젝트: `~/spline-lstm`
- 역할: Tester
- 목표: `coder-gui-phase1-fixpass` 반영 이후, GUI Phase1 Must fix 3건 + build/dev 재현성 최종 재검증
- 검증 항목:
  1. API 오류 사용자 노출(은닉 금지)
  2. API 경로 `/api/v1` 정합성
  3. 상태머신(`queued/running/success/fail`) + 로그/실패 분기 UI 표시
  4. build/dev 재현성

---

### 2) 실행 범위/환경
- UI 경로: `ui/`
- 실행 일시: 2026-02-18 (KST)
- 검증 방식:
  - 정적 코드 점검 (`src/api/client.ts`, `src/pages/*`)
  - 명령 실행 (`npm run build`, `npm run dev`)
  - 브라우저 수동 E2E 확인 (mock OFF/ON 각각)

---

### 3) 항목별 결과

| 항목 | 결과 | 근거 |
|---|---|---|
| 1) API 오류 사용자 노출 | **PASS** | mock OFF(`http://127.0.0.1:4173`)에서 Dashboard에 `Dashboard API 오류: 네트워크 연결 실패...`, Run Job에 `API Error: ...` + `Failure Message` 노출 확인 |
| 2) API 경로 `/api/v1` 정합성 | **PASS** | `API_PREFIX = "/api/v1"` 확인, `/api/ui` 사용처 없음(`rg -n "/api/ui|api/ui|/api/v1" src`) |
| 3) 상태머신 + 로그/실패 분기 | **PASS** | mock ON(`VITE_USE_MOCK=true`, `:4174`)에서 Run Job 상태가 `queued -> running -> success` 전이 및 로그 출력 확인, `runId`에 `fail` 포함 시 최종 `fail` + Failure Message + fail 로그 확인 |
| 4) build/dev 재현성 | **PASS** | `npm run build` 성공(vite build 완료), `npm run dev -- --host 127.0.0.1 --port 4173` 및 `VITE_USE_MOCK=true ... --port 4174` 모두 기동 + `curl -I` 200 확인 |

---

### 4) 실행 로그(핵심 증빙)

#### A. 빌드
- 명령: `cd ui && npm run build`
- 결과: **성공**
  - `tsc -b && vite build`
  - `✓ built in 227ms`

#### B. 경로 정합성
- 명령: `cd ui && rg -n "/api/ui|api/ui|/api/v1" src`
- 결과:
  - `src/api/client.ts:51:const API_PREFIX = "/api/v1"`
  - `/api/ui` 매칭 없음

#### C. dev 서버 재현
- 명령1: `npm run dev -- --host 127.0.0.1 --port 4173`
- 명령2: `VITE_USE_MOCK=true npm run dev -- --host 127.0.0.1 --port 4174`
- 확인: `curl -I http://127.0.0.1:4173` / `:4174` 모두 `HTTP/1.1 200 OK`

#### D. UI 동작 확인
- mock OFF(4173):
  - Dashboard: `Dashboard API 오류: 네트워크 연결 실패: Failed to fetch`
  - Run Job submit: `Status=fail`, `API Error: ...`, `Failure Message` 노출
- mock ON(4174):
  - Run Job(정상 runId): `running` 후 `success`, Execution Logs 누적
  - Run Job(`ui-run-fail-20260218`): 최종 `fail`, `MOCK failure: simulated runtime exception` 표시, fail 로그 표시

---

### 5) 최종 판정 (PASS/FAIL + blocker)
- 최종 판정: **PASS**
- Must fix 3건 해소 여부: **전부 해소**
- blocker: **없음**

---

### 6) 리스크/메모
- 상태머신 성공/실패 분기 검증은 mock 시나리오 기준으로 재현됨.
- 실백엔드 연동 시에는 백엔드 응답 스키마(`job_id/run_id/status/error_message`) 계약 유지가 필요.

---

### 7) 산출물
- 본 문서: `docs/GUI_PHASE1_TEST_RESULTS_FIXPASS2.md`
