# GUI_PHASE3_TEST_RESULTS

## Standard Handoff Format

### 1) 요청/목표
- 프로젝트: `~/spline-lstm`
- 역할: Tester (GUI Phase 3 테스트)
- 목표: UX/안정성 개선 검증
- 검증 항목:
  1. 중복 요청 방지 동작
  2. 로딩/빈상태/오류복구 UI
  3. 회귀 테스트(Phase1/2 핵심)
  4. 빌드/실행 재현성

---

### 2) 수행 범위/방법
- 코드 점검:
  - `ui/src/pages/RunJobPage.tsx`
  - `ui/src/pages/ResultsPage.tsx`
  - `ui/src/api/client.ts`
- 실행/검증 커맨드:
  1. `cd ui && npm run test`
  2. `cd ui && npm run build`
  3. `cd .. && python3 -m pytest -q tests/test_preprocessing_pipeline.py tests/test_artifacts.py tests/test_phase2_pipeline.py tests/test_fixpass2_verification.py`
  4. 재현성 확인: UI 빌드 2회 해시 비교 (`shasum -a 256`, `diff -u`)
  5. 실행 확인: `npm run dev` (mock/non-mock 각각 포트 분리 실행)

---

### 3) 결과 요약

| 검증 항목 | 결과 | 핵심 근거 |
|---|---|---|
| 1) 중복 요청 방지 동작 | **FAIL** | `Run Scenario` 버튼이 제출 중(`submitting`)에도 비활성화되지 않음. `onSubmit` 재진입 차단 플래그(예: inFlight guard) 부재 |
| 2) 로딩/빈상태/오류복구 UI | **PASS** | Results: `loading/loaded/error` 상태 분리 + 로딩 중 버튼 disable, Run: 실패 메시지/로그 empty 안내/재시도 카운트 노출 |
| 3) 회귀 테스트(Phase1/2 핵심) | **PASS** | Python 회귀팩 14개 통과 + 핵심 3개 테스트 2회 연속 통과 |
| 4) 빌드/실행 재현성 | **PASS** | UI 테스트/빌드 성공, 빌드 산출물 해시 2회 동일, dev 서버(mock/non-mock) 실행 확인 |

**종합 판정: CONDITIONAL FAIL**  
- 이유: UX/안정성 핵심 항목인 **중복 요청 방지** 미충족

---

### 4) 상세 근거

#### [검증 1] 중복 요청 방지 동작 (FAIL)
- `ui/src/pages/RunJobPage.tsx`
  - `<button className="primary" type="submit">Run Scenario</button>`
  - 제출 상태(`uiState === "submitting"`) 기반 `disabled` 처리 없음
  - `onSubmit` 초입에 재진입 방지 조건(예: `if (uiState===...) return`) 없음
- 해석:
  - 빠른 연속 클릭/엔터 입력 시 중복 실행 요청 가능성이 존재
  - 백엔드에서 중복 방어를 하더라도 프런트 UX 관점에서는 Phase3 요구 미흡

#### [검증 2] 로딩/빈상태/오류복구 UI (PASS)
- Results 페이지 (`ui/src/pages/ResultsPage.tsx`)
  - 상태머신: `idle | loading | loaded | error`
  - 로딩 중 버튼 비활성화 + 라벨 `Loading...`
  - 에러 카드(`Results API 오류`)와 재요청 버튼(`Load Results`) 제공
- Run 페이지 (`ui/src/pages/RunJobPage.tsx`)
  - empty 로그 안내: `아직 로그가 없습니다.`
  - 실패 메시지 영역 분리, API 에러/재시도 횟수/마지막 재시도 사유 노출
  - 폴링 timeout 시 사용자 메시지 설정: `폴링 제한 시간(...)을 초과했습니다.`
- non-mock 대시보드 접근 시 네트워크 오류 문구 노출 확인 (`Dashboard API 오류: 네트워크 연결 실패`)

#### [검증 3] 회귀 테스트(Phase1/2 핵심) (PASS)
- 실행 결과:
  - `python3 -m pytest -q tests/test_preprocessing_pipeline.py tests/test_artifacts.py tests/test_phase2_pipeline.py tests/test_fixpass2_verification.py`
  - 결과: `14 passed in 5.13s`
- 추가 안정성 확인(동일 테스트 반복):
  - `python3 -m pytest -q tests/test_phase2_pipeline.py tests/test_fixpass2_verification.py` 2회 실행
  - 결과: 두 번 모두 `3 passed`

#### [검증 4] 빌드/실행 재현성 (PASS)
- UI 단위 테스트:
  - `npm run test` → `1 passed (5 tests)`
- UI 빌드:
  - `npm run build` 성공
- 빌드 산출물 해시 2회 비교:
  - `dist/index.html`
  - `dist/assets/index-9O0je86K.css`
  - `dist/assets/index-D5Jy_J1g.js`
  - `diff` 무변경(동일 해시)
- 실행 재현:
  - `VITE_USE_MOCK=true npm run dev -- --host 127.0.0.1 --port 4173` 실행 성공
  - `npm run dev -- --host 127.0.0.1 --port 4174` 실행 성공

---

### 5) Blocker
- **B1. 중복 요청 방지 미구현 (Must fix)**
  - 영향: 동일 run 요청 중복 발생 가능, 사용자 혼선 및 서버 부하 증가 위험
  - 권고:
    1. `Run Scenario` 버튼을 `submitting/polling` 동안 `disabled`
    2. `onSubmit` 재진입 가드 추가 (`if (uiState === "submitting" || uiState === "polling") return;`)
    3. 필요 시 `runId` 단위 in-flight 맵으로 중복 제출 차단

---

### 6) 최종 결론
- Phase3 테스트 4개 항목 중 3개 PASS, 1개 FAIL.
- 로딩/빈상태/오류복구 UI, 회귀 테스트, 빌드/실행 재현성은 기준 충족.
- 단, **중복 요청 방지 동작이 미충족**이므로 현재 게이트는 **CONDITIONAL FAIL**로 판정한다.
- B1 수정 후 동일 시나리오 재검증을 권장한다.
