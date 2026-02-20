# GUI_PHASE2_CODER_NOTES

## 목적
GUI Phase2 Tester 결과(`GUI_PHASE2_TEST_RESULTS.md`)의 Conditional Fail 원인(재시도/timeout 제어 부재) 해소.

## 변경 요약 (Fix Pass)

### 1) API timeout 제어 강화
- 파일: `ui/src/api/client.ts`
- `fetchJson`에 `AbortController` 기반 timeout 처리 유지/정비.
- timeout 발생 시 `ApiError("요청 시간 초과 (...ms)")`로 정규화.

### 2) 재시도 정책 구현 (재시도 가능 오류만)
- 파일: `ui/src/api/client.ts`
- `shouldRetry` 기준:
  - 네트워크/timeout 계열(`status` 없음)
  - HTTP transient 상태코드: `408, 425, 429, 500, 502, 503, 504`
- 요청별 정책(`timeoutMs`, `retries`, `retryDelayMs`) 반영.
- 지수형에 가까운 선형 backoff(`retryDelayMs * attempt`) 적용.

### 3) UI retry 상태/횟수 표시
- 파일: `ui/src/pages/RunJobPage.tsx`
- 상태 추가:
  - `retryCount`
  - `isRetrying`
  - `lastRetryReason`
- `fetchJob`/`fetchJobLogs` 요청에서 retry 이벤트를 수집하여
  - Retry Status(재시도 중/대기)
  - Retry Count(누적 횟수)
  - 마지막 재시도 사유
  를 화면에 표시.

### 4) API retry 이벤트 전달 경로 추가
- 파일: `ui/src/api/client.ts`
- 추가 타입:
  - `RetryEvent`
  - `ApiRequestOptions`
- `fetchJob(jobId, options?)`, `fetchJobLogs(jobId, options?)`에서 `onRetry` 콜백 수신 가능하도록 확장.

## 비파괴성
- 기존 API 호출 경로/엔드포인트/상태 매핑 유지.
- 기존 호출부와 호환되는 optional 옵션 확장 방식 사용.

## 빌드 검증
- 실행: `cd ui && npm run build`
- 결과: 성공 (`tsc -b`, `vite build` 통과)

## 참고
- 연동 백엔드 부재 환경에서는 실제 성공 플로우 실증이 제한될 수 있으나,
  timeout/재시도/노출 상태는 프론트 단에서 검증 가능.

---

## 변경 요약 (Fix Pass2 - Timeout 메시지 정규화)

### 1) timeout/abort/network 예외 분기 일관화
- 파일:
  - `ui/src/api/errorNormalization.ts` (신규)
  - `ui/src/api/client.ts`
- 추가된 정규화 규칙:
  - `AbortError` (`DOMException` 또는 `Error.name === "AbortError"`) → timeout으로 처리
  - `timeout:12000`, `timed out` 등 timeout marker 포함 오류 → timeout으로 처리
  - 그 외 비-HTTP 예외 → 네트워크 오류로 처리
- 사용자 노출 메시지 표준화:
  - timeout: `요청 시간 초과 (Nms)`
  - network: `네트워크 연결 실패`

### 2) 기존 불일치 케이스 해결
- 문제 사례:
  - 기대: `요청 시간 초과 (12000ms)`
  - 실제(기존): `네트워크 연결 실패: timeout:12000`
- 조치 후:
  - timeout marker 기반 오류도 timeout 메시지로 강제 정규화되어 기대 문자열로 수렴.

### 3) 단위 테스트 보강
- 파일: `ui/src/api/errorNormalization.test.ts` (신규, Vitest)
- 검증 항목:
  - AbortError timeout 판정
  - timeout marker 판정
  - timeout 메시지 정규화
  - ApiError 보존
  - 일반 오류의 네트워크 메시지 정규화
- 테스트 실행: `cd ui && npm test`

### 4) 테스트 툴링 추가
- 파일: `ui/package.json`
- 변경:
  - script 추가: `test` (`vitest run`)
  - devDependency 추가: `vitest`

### 5) 빌드/검증
- 실행:
  - `cd ui && npm test`
  - `cd ui && npm run build`
- 결과: 모두 성공
