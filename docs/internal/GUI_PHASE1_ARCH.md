# GUI_PHASE1_ARCH — 경량 크로스플랫폼 GUI Phase 1 아키텍처 고정

## Standard Handoff Format

### 1) 요청/목표
- 역할: Architect
- 프로젝트: `~/spline-lstm`
- 목표: **Phase 1에서 GUI 아키텍처/화면 구조/API mock 계약/완료기준(DoD)을 고정**하여 FE·BE·QA가 병렬 착수 가능한 상태를 만든다.
- 제약:
  - 경량 우선(모바일 브라우저 포함)
  - 단일 코드베이스 기반(UI: `ui/`)
  - 실행 파이프라인은 비동기 Job 모델(제출 → 상태조회 → 결과확인)

---

### 2) Phase 1 아키텍처 결정 요약
1. **UI 기술 기준선**: React + TypeScript + Vite (기존 `ui/` 구조 유지)
2. **화면 범위**: Dashboard / Run Job / Results **3개 화면만 Phase 1 확정**
3. **데이터 흐름**: Mock API 기반 선개발 (MSW 또는 JSON Server 계열), 이후 FastAPI 실API로 스위치
4. **상태 전략**: 서버 상태(잡/결과)는 Query 기반 캐시, 화면 로컬 상태(폼/필터)는 컴포넌트 상태
5. **성능 전략**: 차트/로그 컴포넌트 지연 로딩 + 모바일 단순 레이아웃

---

### 3) 화면 3종 정보구조(IA)

#### 3.1 Dashboard 화면
**목적**: 현재 시스템 상태와 최근 실행 현황을 한눈에 확인

- 상단 영역
  - 앱 타이틀/프로젝트 배지
  - 빠른 액션: `새 Job 실행`, `최근 결과 보기`
- 상태 카드 영역
  - API 상태(healthy/degraded)
  - 실행 중 Job 수
  - 최근 24시간 성공/실패 카운트
- 최근 Job 리스트
  - 컬럼: Job ID, 모드(train/eval/infer), 상태, 시작시각, 소요시간
  - 행 액션: 상세 보기(Results 이동)
- 최근 알림/오류 요약
  - 최근 실패 3건의 에러 요약

**핵심 사용자 액션**
- Job 상세 진입
- Run Job 화면 이동

#### 3.2 Run Job 화면
**목적**: 파이프라인 실행 파라미터 입력 및 실행 제출

- 입력 섹션 A: 데이터셋
  - dataset_path (텍스트/선택)
  - target_cols (기본 `target`)
  - optional covariates
- 입력 섹션 B: 실행 모드
  - mode: `train_eval` | `infer` | `preprocess_only`
  - lookback / horizon / scaling
- 입력 섹션 C: 모델/런타임(최소)
  - epochs, batch_size, seed
- 제출 섹션
  - `Run` 버튼
  - 요청 payload preview (접기/펼치기)
  - 제출 후 job_id 토스트 + Dashboard/Results 이동 CTA

**검증 규칙(클라이언트)**
- 필수값 누락 시 제출 차단
- 숫자 파라미터 최소/최대 범위 검증
- mode별 필드 조건부 노출

#### 3.3 Results 화면
**목적**: 단일 run 결과 확인 및 실패 원인 파악

- 헤더
  - run_id / job_id / status / 실행 시각
- 지표 카드
  - MAE, MSE, RMSE, robust MAPE, MASE, R2 (없으면 `N/A`)
- 차트 영역
  - 실제값 vs 예측값 시계열 라인
  - 줌(Phase 1 기본: x축 범위 선택 1종)
- 로그 영역
  - stdout/stderr 합성 로그 (최신순/시간순 토글)
  - ERROR 레벨 하이라이트
- 아티팩트 링크 영역
  - report.md / metrics.json / checkpoint 경로(읽기 전용)

**상태별 렌더링**
- queued/running: 스켈레톤 + progress/step
- succeeded: 지표/차트/아티팩트 표시
- failed: 에러요약 + 재실행 버튼(동일 파라미터 복제)

---

### 4) 반응형 기준 (모바일/태블릿/노트북)

#### 4.1 브레이크포인트
- **모바일**: `< 768px`
- **태블릿**: `768px ~ 1279px`
- **노트북**: `>= 1280px`

#### 4.2 레이아웃 원칙
1. 모바일: 1열 스택, 핵심 액션 버튼 하단 고정 허용
2. 태블릿: 2열(콘텐츠 2:1 또는 1:1), 표/로그 일부 축약
3. 노트북: 3영역(폼/상태/로그 또는 차트/지표/로그 동시 노출)

#### 4.3 화면별 반응형 규칙
- Dashboard
  - 모바일: 카드 1열, 최근 Job 5건
  - 태블릿: 카드 2열, 최근 Job 8건
  - 노트북: 카드 4열, 최근 Job 10건 + 오류요약 사이드패널
- Run Job
  - 모바일: 섹션 아코디언, 제출 버튼 sticky
  - 태블릿: 입력 2열(기본/고급)
  - 노트북: 입력 2열 + payload preview 고정 패널
- Results
  - 모바일: 지표 카드 1열, 차트 높이 축소(240~280px), 로그 기본 접힘
  - 태블릿: 지표 2~3열, 차트/로그 탭 전환
  - 노트북: 차트 + 로그 분할(상하 또는 좌우), 지표 상단 고정

#### 4.4 성능/경량 가드레일 (Phase 1)
- 초기 인터랙션 가능 시점:
  - 모바일 ≤ 3.0s / 태블릿 ≤ 2.5s / 노트북 ≤ 2.0s
- 런타임 메모리 목표:
  - 모바일 ≤ 250MB / 태블릿 ≤ 350MB / 노트북 ≤ 500MB
- 로그 렌더링:
  - 1회 기본 200줄, 추가는 `Load more`

---

### 5) API Mock 계약 (Phase 1 고정)

#### 5.1 공통 응답 Envelope
```json
{
  "ok": true,
  "data": {},
  "error": null,
  "request_id": "req_mock_001",
  "ts": "2026-02-18T21:18:00+09:00"
}
```

실패 예시:
```json
{
  "ok": false,
  "data": null,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "lookback must be >= 1",
    "details": { "field": "lookback" }
  },
  "request_id": "req_mock_002",
  "ts": "2026-02-18T21:18:03+09:00"
}
```

#### 5.2 Endpoint 목록
1. `GET /api/v1/health`
2. `GET /api/v1/dashboard/summary`
3. `GET /api/v1/jobs?limit=10`
4. `POST /api/v1/pipelines/spline-tsfm:run`
5. `GET /api/v1/jobs/{job_id}`
6. `GET /api/v1/jobs/{job_id}/logs?offset=0&limit=200`
7. `GET /api/v1/runs/{run_id}/metrics`
8. `GET /api/v1/runs/{run_id}/artifacts`
9. `POST /api/v1/jobs/{job_id}:cancel`

#### 5.3 주요 스키마

- Dashboard Summary (`GET /dashboard/summary`)
```json
{
  "ok": true,
  "data": {
    "api_status": "healthy",
    "running_jobs": 1,
    "success_24h": 12,
    "failed_24h": 2,
    "latest_failures": [
      { "job_id": "job_102", "message": "dataset not found", "ts": "2026-02-18T19:01:00+09:00" }
    ]
  }
}
```

- Run Submit (`POST /pipelines/spline-tsfm:run`)
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
    "epochs": 20,
    "batch_size": 32
  },
  "runtime": {
    "seed": 42
  }
}
```

응답:
```json
{
  "ok": true,
  "data": {
    "job_id": "job_mock_001",
    "run_id": "gui-20260218-001",
    "status": "queued"
  }
}
```

- Job Detail (`GET /jobs/{job_id}`)
```json
{
  "ok": true,
  "data": {
    "job_id": "job_mock_001",
    "run_id": "gui-20260218-001",
    "status": "running",
    "step": "training",
    "progress": 62,
    "started_at": "2026-02-18T21:10:00+09:00",
    "updated_at": "2026-02-18T21:13:00+09:00"
  }
}
```

- Metrics (`GET /runs/{run_id}/metrics`)
```json
{
  "ok": true,
  "data": {
    "mae": 0.123,
    "rmse": 0.221,
    "mape": 4.21,
    "points": [
      { "ts": "2026-02-18T00:00:00+09:00", "actual": 10.2, "pred": 10.0 }
    ]
  }
}
```

- Logs (`GET /jobs/{job_id}/logs`)
```json
{
  "ok": true,
  "data": {
    "offset": 0,
    "next_offset": 120,
    "lines": [
      { "ts": "2026-02-18T21:11:00+09:00", "level": "INFO", "message": "preprocessing started" },
      { "ts": "2026-02-18T21:12:10+09:00", "level": "WARN", "message": "missing ratio 0.12" }
    ]
  }
}
```

#### 5.4 Mock 동작 규칙
- 기본 지연시간: `300~900ms` 랜덤
- Job 상태 전이: `queued -> running -> succeeded|failed`
- 실패 시나리오 2종 강제 포함:
  1) validation 실패 (`400`)
  2) runtime 실패 (`500`, `RUNTIME_ERROR`)

---

### 6) Phase 1 DoD (Definition of Done)
아래 항목 **모두 충족 시 Phase 1 완료**:

1. **화면 구조 고정**
   - Dashboard / Run Job / Results 3화면 IA 문서화 완료
   - 각 화면 핵심 액션/상태 렌더링 규칙 명시
2. **반응형 기준 고정**
   - 모바일/태블릿/노트북 브레이크포인트 및 레이아웃 규칙 합의
   - 화면별 축약/확장 규칙 정의 완료
3. **API Mock 계약 고정**
   - 엔드포인트 9종, 요청/응답 스키마, 에러코드 초안 확정
   - 성공/실패 Mock 시나리오 포함
4. **개발 착수 가능성 확보**
   - FE가 mock 기반으로 독립 개발 가능
   - BE가 실제 FastAPI 계약으로 매핑 가능한 수준의 필드 정의 완료
5. **검증 가능성 확보**
   - QA가 화면/상태/에러 플로우 테스트 케이스 작성 가능한 기준 제공

---

### 7) 구현 핸드오프 체크리스트
- [ ] `ui/` 라우팅: `/dashboard`, `/run`, `/results/:runId`
- [ ] `mocks/handlers`에 API 9종 구현
- [ ] 공통 타입(`Job`, `RunMetrics`, `ApiEnvelope`) 분리
- [ ] 반응형 레이아웃 스냅샷 테스트(모바일/태블릿/노트북)
- [ ] 실패 상태 UI(Validation/Runtime Error) 시나리오 테스트

---

### 8) 리스크 및 후속결정
- 리스크: 실제 Runner 응답 필드와 mock 불일치 가능성
  - 대응: BE 착수 시 계약검토 미팅 1회(30분)로 필드 동기화
- 리스크: 모바일 로그/차트 렌더 성능 저하
  - 대응: 로그 pagination + 차트 포인트 샘플링 기본 적용
- 후속 결정 필요:
  1. 상태조회 방식 최종 선택 (Polling 유지 vs SSE/WebSocket)
  2. 차트 라이브러리 확정 (Recharts vs ECharts)

---

### 9) 인수인계 메모
- 본 문서는 **GUI Phase 1 아키텍처 기준선**이다.
- 다음 단계 권장 순서:
  1. FE: mock 기반 3화면 골격 구현
  2. BE: `/api/v1` 실API 스켈레톤 구현
  3. QA: DoD 기반 테스트 체크리스트 작성
- 변경관리 원칙:
  - Phase 1 중 IA/브레이크포인트/API 필드 변경은 PR 문서 승인 후 반영
