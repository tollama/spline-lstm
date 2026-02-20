# GUI_PHASE2_ARCH — GUI Phase 2 설계 고정 (실API 연동/상태머신/오류처리)

## Standard Handoff Format

### 1) 요청/목표
- 역할: Architect
- 프로젝트: `~/spline-lstm`
- 목표: **GUI Phase 2에서 `/api/v1` 실연동 계약 + 상태머신 + 오류처리 표준 + polling/timeout/retry 정책을 고정**하여 FE/BE/QA 구현-검증 기준선을 통일한다.
- 범위:
  - UI(`ui/`)와 FastAPI(`/api/v1`) 사이의 통신 계약
  - Job 수명주기(queued/running/success/fail) 전이 규칙
  - 표준 에러 코드/메시지 포맷
  - 클라이언트 재시도/타임아웃/폴링 정책
- 비범위:
  - 인증/권한(RBAC)
  - SSE/WebSocket 실시간 스트림 본격 도입(Phase 3 후보)
  - 분산 큐/멀티 워커 아키텍처

---

### 2) Phase 2 결정 요약 (Locked)
1. **API Prefix 고정**: 모든 GUI 호출은 `GET|POST /api/v1/*`만 사용한다.
2. **응답 Envelope 고정**: 성공/실패 모두 공통 envelope(`ok/data/error/request_id/ts`)를 사용한다.
3. **UI 상태머신 고정**: UI 외부 노출 상태는 정확히 `queued | running | success | fail` 4단계로 통일한다.
4. **백엔드 상태 매핑 고정**:
   - `queued -> queued`
   - `running|preprocessing|training|evaluating|inferencing -> running`
   - `succeeded -> success`
   - `failed|canceled -> fail`
5. **장기작업 조회 정책 고정**: 기본 Polling(1.2s 시작, 최대 3s 백오프), 타임아웃/재시도 표준 적용.

---

### 3) `/api/v1` 연동 계약 상세

#### 3.1 공통 응답 Envelope (필수)

성공:
```json
{
  "ok": true,
  "data": {},
  "error": null,
  "request_id": "req_20260218_abc123",
  "ts": "2026-02-18T21:24:00+09:00"
}
```

실패:
```json
{
  "ok": false,
  "data": null,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "lookback must be >= 1",
    "details": { "field": "lookback" },
    "retryable": false
  },
  "request_id": "req_20260218_def456",
  "ts": "2026-02-18T21:24:02+09:00"
}
```

필수 규칙:
- `request_id`는 모든 응답에서 채워진다(추적성).
- HTTP status와 `error.code`는 상호 일관성을 유지한다.
- `error.message`는 사용자 노출 가능한 한국어/영어 혼용 없이, UI 정책에 맞게 단일 언어(기본 한국어)로 제공한다.

#### 3.2 엔드포인트 목록 (Phase 2 고정)
1. `GET /api/v1/health`
2. `GET /api/v1/dashboard/summary`
3. `POST /api/v1/pipelines/spline-tsfm:run`
4. `GET /api/v1/jobs/{job_id}`
5. `GET /api/v1/jobs/{job_id}/logs?offset={n}&limit={m}`
6. `GET /api/v1/runs/{run_id}/metrics`
7. `GET /api/v1/runs/{run_id}/report`
8. `GET /api/v1/runs/{run_id}/artifacts`
9. `POST /api/v1/jobs/{job_id}:cancel`

#### 3.3 요청/응답 스키마 핵심

##### A) 실행 제출
`POST /api/v1/pipelines/spline-tsfm:run`

요청(최소 필드):
```json
{
  "run_id": "gui-20260218-001",
  "mode": "train_eval",
  "input": {
    "dataset_path": "data/raw/synthetic/s1.csv",
    "target_cols": ["target"],
    "lookback": 24,
    "horizon": 1,
    "scaling": "standard"
  },
  "model": {
    "model_type": "lstm",
    "epochs": 20,
    "batch_size": 32
  },
  "runtime": { "seed": 42 }
}
```

성공 응답(`data`):
```json
{
  "job_id": "job_01J...",
  "run_id": "gui-20260218-001",
  "status": "queued",
  "message": "job accepted"
}
```

##### B) Job 상세
`GET /api/v1/jobs/{job_id}`

응답(`data`):
```json
{
  "job_id": "job_01J...",
  "run_id": "gui-20260218-001",
  "status": "running",
  "step": "training",
  "progress": 62,
  "message": "epoch 13/20",
  "error_message": null,
  "started_at": "2026-02-18T21:20:00+09:00",
  "updated_at": "2026-02-18T21:23:10+09:00"
}
```

##### C) Job 로그
`GET /api/v1/jobs/{job_id}/logs`

응답(`data`):
```json
{
  "job_id": "job_01J...",
  "offset": 0,
  "next_offset": 120,
  "lines": [
    {"ts": "2026-02-18T21:21:00+09:00", "level": "INFO", "message": "preprocessing started"},
    {"ts": "2026-02-18T21:22:10+09:00", "level": "WARN", "message": "missing ratio 0.12"}
  ]
}
```

##### D) 결과 조회
- `GET /api/v1/runs/{run_id}/metrics`
- `GET /api/v1/runs/{run_id}/report`
- `GET /api/v1/runs/{run_id}/artifacts`

결과 조회는 **성공 상태(success)에서만 완전한 데이터를 보장**한다.
`queued/running`에서 조회 시 `409 RUN_NOT_READY` 또는 부분 데이터 반환 중 하나로 고정해야 하며, **Phase 2 기본은 `409 RUN_NOT_READY`**로 통일한다.

---

### 4) 상태 전이 규칙 (queued/running/success/fail)

#### 4.1 상태 정의
- `queued`: 요청 수락, 실행 대기
- `running`: 작업 수행 중(세부 단계 포함)
- `success`: 정상 완료(최종 산출물 생성)
- `fail`: 실패/취소/치명적 오류로 비정상 종료

#### 4.2 상태 전이 다이어그램 (UI 기준)
```text
queued -> running -> success
queued -> running -> fail
queued -> fail            (큐 적재 후 즉시 검증 실패 포함)
running -> fail           (런타임 예외/타임아웃/취소 포함)
```

금지 전이:
- `success -> *`
- `fail -> *`
- `queued -> success` (중간 단계 생략 금지)

#### 4.3 백엔드 상태 → UI 상태 매핑 규칙
- 백엔드 `queued` => UI `queued`
- 백엔드 `running|preprocessing|training|evaluating|inferencing` => UI `running`
- 백엔드 `succeeded` => UI `success`
- 백엔드 `failed|canceled` => UI `fail`

#### 4.4 UI 렌더링 규칙
- `queued/running`: 진행상태, 로그 스트림, 취소 버튼 노출
- `success`: metrics/report/artifacts 노출, 재실행 CTA
- `fail`: 에러 코드+메시지+request_id 표시, 재시도/파라미터 수정 CTA

---

### 5) 오류 코드/메시지 표준

#### 5.1 에러 객체 규약
```json
{
  "code": "RUNNER_TIMEOUT",
  "message": "작업 실행 제한 시간을 초과했습니다.",
  "details": {"job_id": "job_01J...", "timeout_sec": 1800},
  "retryable": true
}
```

필수 필드:
- `code` (machine-readable, UPPER_SNAKE_CASE)
- `message` (user-readable)
- `retryable` (UI 자동재시도 가능 여부)

#### 5.2 표준 코드 테이블 (Phase 2)

| HTTP | code | 의미 | UI 기본 처리 |
|---:|---|---|---|
| 400 | `VALIDATION_ERROR` | 입력값/스키마 오류 | 폼 필드 강조, 자동재시도 금지 |
| 404 | `JOB_NOT_FOUND` | job_id 없음 | 목록 갱신 유도 |
| 404 | `RUN_NOT_FOUND` | run_id 없음 | run_id 확인 안내 |
| 404 | `ARTIFACT_NOT_FOUND` | 결과 파일 없음 | 생성 완료 여부 안내 |
| 409 | `RUN_NOT_READY` | 결과 조회 시점 이름 | polling 유지 |
| 409 | `RUN_ID_MISMATCH` | 산출물 run_id 불일치 | fail 처리 + 관리자 확인 |
| 429 | `RATE_LIMITED` | 과도한 요청 | poll 간격 증가 |
| 500 | `RUNNER_EXEC_ERROR` | 러너 실행 실패 | 제한적 재시도 |
| 504 | `RUNNER_TIMEOUT` | 실행 시간 초과 | 제한적 재시도 + 취소/재실행 |
| 503 | `SERVICE_UNAVAILABLE` | 일시적 서비스 불가 | 백오프 재시도 |

#### 5.3 메시지 가이드
- 사용자 메시지는 **행동 가능한 문장**으로 제공한다.
  - 예: "입력값이 올바르지 않습니다. lookback은 1 이상이어야 합니다."
- 내부 stack trace는 API raw 응답에 노출하지 않는다(`details.debug_id`로 추적).

---

### 6) Polling / Timeout / Retry 정책

#### 6.1 Polling 정책 (Job 상태)
- 시작 간격: `1.2초`
- 안정 구간(10회 이후): `2.0초`
- 부하/429/503 시: `3.0초`까지 증가(backoff)
- 종료 조건:
  - `success|fail` 도달
  - 클라이언트 총 대기시간 timeout 도달
  - 사용자 취소

#### 6.2 Timeout 정책
- `POST /pipelines/...:run` 요청 timeout: `10초`
- `GET /jobs/{id}`/`logs` timeout: `5초`
- `GET /runs/{id}/*` timeout: `8초`
- 단일 Job 관찰 최대시간(UI): 기본 `30분` (설정 가능)
- timeout 발생 시 UI 상태:
  - 즉시 `fail`로 단정하지 않고 `연결 불안정` 배지 + 재시도 경로 제공
  - 연속 timeout 임계치(예: 3회) 초과 시 `fail` 전환 가능

#### 6.3 Retry 정책
- 자동재시도 대상: 네트워크 오류, `429`, `503`, `504`, `RUNNER_TIMEOUT(retryable=true)`
- 자동재시도 금지: `400 VALIDATION_ERROR`, `404*`, `RUN_ID_MISMATCH`
- 기본 재시도 횟수:
  - 조회성 GET: 최대 3회
  - 실행성 POST(run): 최대 1회(멱등키 또는 동일 run_id 조건)
- 지수 백오프 + 지터:
  - 1회차: 800ms
  - 2회차: 1600ms
  - 3회차: 3200ms (+/- 20% jitter)

#### 6.4 멱등성 규칙
- `POST /pipelines/...:run`은 `run_id` 기준 중복 제출 제어 필요.
- 같은 `run_id`의 중복 요청은:
  - 기존 job 반환(권장) 또는
  - `409 DUPLICATE_RUN_ID`로 명시 실패

---

### 7) 프론트 구현 계약 (ui/src/api/client.ts 기준 정렬)

#### 7.1 타입 정렬
- UI 내부 `JobStatus = queued|running|success|fail` 유지
- API 응답 원문 status는 adapter에서 매핑 후 컴포넌트로 전달

#### 7.2 함수 계약 (고정)
- `fetchDashboardSummary(): Promise<DashboardSummary>`
- `postRunJob(payload): Promise<{jobId, runId, status, message?}>`
- `fetchJob(jobId): Promise<{jobId, runId, status, message?, errorMessage?}>`
- `fetchJobLogs(jobId): Promise<{jobId, logs|string[]|lines[]}>`
- `fetchResult(runId): Promise<ResultPayload>`

#### 7.3 Envelope 파서 규칙
- `fetchJson`은 envelope를 해석해 `ok=false`면 `ApiError`로 통일 throw
- `ApiError` 확장 필드: `status`, `code`, `requestId`, `retryable`, `body`

---

### 8) Phase 2 DoD (Definition of Done)
아래 항목을 모두 충족하면 Phase 2 완료:

1. **실API 계약 고정**
   - `/api/v1` 엔드포인트 9종 요청/응답 스키마 문서화 완료
   - 공통 envelope + 에러 객체 규격 적용

2. **상태머신 고정**
   - queued/running/success/fail 전이 규칙 구현 및 금지 전이 테스트 완료
   - 백엔드 상태값 매핑 로직 단일 함수로 고정

3. **오류 표준 고정**
   - 표준 코드 테이블(HTTP/code/retryable) 반영
   - UI가 코드 기반 분기 처리(필드 오류/재시도/치명오류) 가능

4. **Polling/Timeout/Retry 고정**
   - 기본 폴링 간격/백오프/종료조건 반영
   - timeout/재시도 정책이 페이지 단위로 일관 적용

5. **QA 검증 가능성 확보**
   - 성공/실패/네트워크 불안정/429/timeout 시나리오 테스트 케이스 작성 가능
   - request_id 기반 추적이 로그에서 확인 가능

6. **회귀 방지**
   - API client 단위 테스트 + 상태 전이 테스트 + 에러 매핑 테스트 최소 1세트 통과

---

### 9) 인수인계 체크리스트
- [ ] `docs/GUI_PHASE2_ARCH.md` 승인
- [ ] FE `ui/src/api/client.ts` envelope 파싱/에러 매핑 반영
- [ ] FE `RunJobPage` 상태머신 전이 가드 반영
- [ ] BE `/api/v1` 응답 형식(envelope/error) 통일
- [ ] BE `RUN_NOT_READY`, `RUNNER_TIMEOUT`, `RATE_LIMITED` 코드 표준 반영
- [ ] QA 시나리오(정상/검증오류/러너실패/타임아웃/429) 작성

---

### 10) 리스크/오픈포인트
- 리스크: 현재 일부 API가 envelope 없이 원문 JSON 반환 가능성
  - 대응: Phase 2에서 API 게이트웨이 레이어로 envelope 강제
- 리스크: `report`/`metrics` 스키마 드리프트
  - 대응: JSON Schema 버전 필드(`schema_version`) 추가 권장
- 오픈포인트:
  1. Phase 3에서 SSE/WebSocket 전환 여부
  2. `canceled`를 UI 독립 상태로 승격할지 여부(현재는 fail로 매핑)

---

### 11) Standard Handoff 요약
#### Summary
- GUI Phase 2 기준선으로 실API 계약, 4단계 상태머신, 오류 코드 표준, polling/timeout/retry 정책을 고정했다.

#### Decisions Locked
- `/api/v1` + envelope + `queued/running/success/fail` UI 상태 통일
- 백엔드 상세 상태를 UI 4단계로 매핑
- 재시도 가능 오류와 금지 오류를 코드 기반으로 분리

#### Deliverables
- [x] `docs/GUI_PHASE2_ARCH.md` 작성 완료
- [x] API/상태/오류/운영정책/DoD 문서화 완료

#### Immediate Next Actions
1. FE: `client.ts` envelope/에러 파서 리팩터링
2. BE: 에러 코드 표준 테이블 반영
3. QA: 계약 기반 테스트 매트릭스 작성
