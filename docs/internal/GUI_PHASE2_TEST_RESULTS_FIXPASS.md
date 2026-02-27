# GUI_PHASE2_TEST_RESULTS_FIXPASS

## Standard Handoff Format

### 1) 요청/목표
- 프로젝트: `~/spline-lstm`
- 역할: Tester (GUI Phase2 FixPass 재검증)
- 목표: timeout/retry 보강 반영 후 재검증
- 검증 항목:
  1. 오류 노출
  2. retry 동작/횟수
  3. timeout 발생 및 사용자 메시지
  4. 상태머신/빌드 재확인

---

### 2) 수행 범위/방법
- 코드 검토:
  - `ui/src/api/client.ts`
  - `ui/src/pages/RunJobPage.tsx`
- 실행 검증:
  1. `cd ui && npm install && npm run build`
  2. `VITE_USE_MOCK=true npm run dev -- --host 127.0.0.1 --port 4173`
  3. Playwright headless로 Run Job 성공/실패 시나리오 검증
  4. non-mock dev(`:4174`) + 지연 응답 stub 서버(`:18001`)로 timeout/retry 실측

---

### 3) 결과 요약

| 검증 항목 | 결과 | 핵심 근거 |
|---|---|---|
| 1) 오류 노출 | PASS | 실패 시 `Failure Message`/`API Error`에 즉시 반영 (`formatApiError`) |
| 2) retry 동작/횟수 | PASS | timeout 유도 시 `POST /pipelines/...:run` 호출 hit=2(초기 1 + retry 1) 확인 |
| 3) timeout 발생 및 사용자 메시지 | **FAIL (Blocker)** | timeout 시 사용자 메시지가 기대값 `요청 시간 초과 (...)`가 아닌 `네트워크 연결 실패: timeout:12000`로 노출 |
| 4) 상태머신/빌드 재확인 | PASS | mock에서 `success`/`fail` 종단 전이 확인, `npm run build` 성공 |

**종합 판정: FAIL (Blocker 존재)**

---

### 4) 상세 근거

#### [검증 1] 오류 노출
- 실패 시 UI 표시 확인:
  - `RunJobPage.tsx`에서 catch 경로에서 `apiError`, `failureMessage`, `jobStatus=fail` 설정
  - `Failure Message` 카드 및 `API Error` 영역에 표시
- mock fail(`runId`에 `fail` 포함) 실행 시 실패 메시지 노출 확인

#### [검증 2] retry 동작/횟수
- 코드 정책:
  - `postRunJob`: `retries: 1`, `timeoutMs: 12000`
  - `fetchJob`: `retries: 2`, `timeoutMs: 8000`
  - `fetchJobLogs`: `retries: 1`, `timeoutMs: 8000`
- 실측:
  - 지연 stub(20s)로 `postRunJob` timeout 유도
  - 서버 카운트 결과: `hits: 2` (재시도 1회 정상)

#### [검증 3] timeout 발생 및 사용자 메시지
- 기대: timeout 시 `ApiError("요청 시간 초과 (xxxxms)")` 노출
- 실측: `Failure Message = "네트워크 연결 실패: timeout:12000"`
- 해석:
  - 현재 환경(fetch abort reason 전달)에서 timeout 예외가 `DOMException(AbortError)` 분기로 들어가지 않고 일반 에러로 정규화됨
  - 결과적으로 사용자 메시지가 timeout 친화 문구가 아니라 네트워크 실패 문구로 표시됨

#### [검증 4] 상태머신/빌드 재확인
- mock 성공/실패 시나리오:
  - success run: `status = success`, success 로그 존재
  - fail run: `status = fail`, failure message에 mock 실패 문자열 존재
- 빌드:
  - `vite build` 성공 (`dist/assets/index-*.js` 생성)

---

### 5) Blocker
- **B1 (High): timeout 사용자 메시지 불일치**
  - 재현: non-mock + 지연 응답으로 timeout 유도
  - 현재: `네트워크 연결 실패: timeout:12000`
  - 기대: `요청 시간 초과 (12000ms)` 형태
  - 영향: 요구사항 3) “timeout 발생 및 사용자 메시지” 미충족

---

### 6) 권고 수정 (핵심)
- `fetchJson` catch에서 abort 판별을 `error.name === "AbortError"`에만 의존하지 말고,
  - `controller.signal.aborted` 또는
  - abort reason 문자열(`timeout:` prefix)까지 함께 판별
- 판별 시 일관되게 `ApiError("요청 시간 초과 (...)" )`로 매핑하도록 보강 필요

---

### 7) 최종 결론
- retry 보강과 상태머신/빌드는 재검증 **PASS**.
- 다만 timeout 시 사용자-facing 메시지가 요구와 다르게 노출되어 **FAIL (Blocker)**.
- Blocker 해소 후 동일 시나리오 재실행 시 PASS 전환 가능.
