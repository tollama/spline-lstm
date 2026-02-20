# GUI_PHASE4_TEST_RESULTS

## 1) 요청/목표
- 프로젝트: `~/spline-lstm`
- 역할: Tester (GUI Phase4 릴리즈 하드닝 검증)
- 목표: GUI 릴리즈 하드닝 관점에서 실행 프로파일, 오류/로그 표준, 기본 성능/접근성, 회귀(Phase1~3 핵심) 확인
- 검증 항목:
  1. 환경 프로파일별 실행 검증(dev/mock/non-mock 최소)
  2. 오류 메시지/로그 표준 확인
  3. 기본 성능/접근성 체크
  4. 회귀(Phase1~3 핵심) 확인

---

## 2) 수행 방법
- 코드/설정 점검
  - `ui/src/api/client.ts` (mock 토글/오류 포맷/재시도)
  - `ui/src/api/errorNormalization.ts` (timeout/network 메시지 정규화)
  - `ui/src/pages/RunJobPage.tsx`, `DashboardPage.tsx`, `ResultsPage.tsx`
  - `ui/.env.development`, `.env.production` (프로파일 기본값 확인)
- 실행/검증 커맨드
  - `cd ui && npm run test`
  - `cd ui && npm run build`
  - `python3 -m pytest -q tests/test_preprocessing_pipeline.py tests/test_data_contract.py tests/test_models.py tests/test_artifacts.py tests/test_phase2_pipeline.py tests/test_phase3_repro_baseline.py`
  - `python3 -m pytest -q tests/test_phase2_pipeline.py tests/test_phase3_repro_baseline.py tests/test_phase4_run_id_guard.py`
- 프로파일 실행 확인
  - dev(mock): `VITE_USE_MOCK=true npm run dev -- --host 127.0.0.1 --port 4173`
  - dev(non-mock): `VITE_USE_MOCK=false npm run dev -- --host 127.0.0.1 --port 4174`
  - prod preview: `npm run preview -- --host 127.0.0.1 --port 4175`
  - 각 프로파일 HTTP 200 및 브라우저 동작 확인
- 브라우저 수동 확인(OpenClaw)
  - mock 모드 Run Job 실패 시나리오(`runId`에 `fail`)로 failure/log 표시 확인
  - non-mock 모드에서 Dashboard/Results 오류 카드/재시도 문구 확인

---

## 3) 결과 요약

| 검증 항목 | 결과 | 핵심 근거 |
|---|---|---|
| 1) 환경 프로파일별 실행 검증 | **PASS** | dev(mock) `:4173`, dev(non-mock) `:4174`, preview `:4175` 모두 HTTP 200. mock에서는 `API: ... (dev mock enabled)` 및 MOCK 데이터 표시, non-mock에서는 실제 API 실패 시 오류 카드 표시 |
| 2) 오류 메시지/로그 표준 | **PASS** | 오류 정규화 테스트 5건 통과. non-mock 오류 메시지 `네트워크 연결 실패` 일관 노출. mock fail 실행 시 `MOCK failure: simulated runtime exception` + 단계형 로그(queued/running/fail) 표시 |
| 3) 기본 성능/접근성 체크 | **PASS** | `npm run build` 성공(총 0.865s, JS 159.16kB gzip 51.15kB). 로컬 응답 TTFB 대체로 1ms 내외. Toast viewport `role=status`, `aria-live=polite` 확인 |
| 4) 회귀(Phase1~3 핵심) | **PASS** | Phase1~3 핵심 회귀팩 `23 passed, 2 skipped` + Phase2/3/4 관련 `6 passed` |

**종합 판정: PASS**

---

## 4) 상세 근거

### [1] 환경 프로파일별 실행 검증 (PASS)
- 실행 확인:
  - `http://127.0.0.1:4173` (dev/mock) → 200
  - `http://127.0.0.1:4174` (dev/non-mock) → 200
  - `http://127.0.0.1:4175` (preview/prod) → 200
- 브라우저 확인:
  - mock(4173): Dashboard에 `MOCK: healthy` 표시, Run 탭에 `(dev mock enabled)` 표시
  - non-mock(4174): Dashboard `Dashboard API 오류: 네트워크 연결 실패`, Results `Results API 오류: 네트워크 연결 실패`

### [2] 오류 메시지/로그 표준 확인 (PASS)
- 자동 테스트:
  - `ui/src/api/errorNormalization.test.ts` → `5 passed`
- 메시지 표준:
  - timeout: `요청 시간 초과 (Nms)`
  - network: `네트워크 연결 실패`
- 수동 시나리오(mock fail):
  - Run ID: `ui-fail-20260218-2145`
  - 상태: `fail`, UI State: `실패`
  - Failure Message: `MOCK failure: simulated runtime exception`
  - Execution Logs: `queued → running(preprocessing/training) → fail` 순서 확인

### [3] 기본 성능/접근성 체크 (PASS)
- 빌드 성능/산출물
  - `vite build` 완료: `built in 225ms`
  - 전체 빌드 wall time: `0.865s`
  - 산출물: `dist/assets/index-uCf32fmL.js 159.16kB (gzip 51.15kB)`
- 로컬 응답(샘플 3회)
  - dev/mock 4173: total 약 `0.00068~0.00089s`
  - dev/non-mock 4174: total 약 `0.00079~0.00090s`
  - preview 4175: warm 이후 total 약 `0.00063~0.00088s`
- 접근성 기본 체크
  - Toast 컨테이너 `role="status"`, `aria-live="polite"` 확인
  - 탭/버튼/입력 요소가 의미 있는 텍스트 라벨과 함께 노출됨(키보드 포커스 가능한 기본 컨트롤)

### [4] 회귀(Phase1~3 핵심) 확인 (PASS)
- 실행 결과 1:
  - `tests/test_preprocessing_pipeline.py`
  - `tests/test_data_contract.py`
  - `tests/test_models.py`
  - `tests/test_artifacts.py`
  - `tests/test_phase2_pipeline.py`
  - `tests/test_phase3_repro_baseline.py`
  - 결과: `23 passed, 2 skipped`
- 실행 결과 2:
  - `tests/test_phase2_pipeline.py tests/test_phase3_repro_baseline.py tests/test_phase4_run_id_guard.py`
  - 결과: `6 passed`

---

## 5) Blocker / 리스크
- **Blocker 없음**
- 관찰 사항(운영 메모):
  - `ui/.env.development` 기본값이 `VITE_USE_MOCK=true` 이므로, non-mock dev 검증 시 `VITE_USE_MOCK=false`를 명시해야 함.

---

## 6) 최종 결론
- 요청된 4개 검증 항목 모두 **PASS**.
- 릴리즈 하드닝 관점에서 프로파일 실행, 오류/로그 표준, 기본 성능/접근성, Phase1~3 핵심 회귀 모두 확인됨.
- GUI Phase4 Tester Gate는 **PASS**로 판정함.
