# GUI_ARCHITECTURE — Cross-platform GUI 기술 아키텍처 설계 (Spline-TSFM 연동)

- 문서 버전: v1.0
- 작성일: 2026-02-18
- 대상 프로젝트: `~/spline-lstm`
- 작성 역할: Architect
- 형식: **Standard Handoff Format (실무 인수인계용)**

---

## 0. Executive Summary (결정 요약)

### 최종 권장안 (1안)
**Web/PWA (React + Vite + TypeScript) + FastAPI Backend + Runner Adapter 계층**

### 선택 이유 (핵심 3가지)
1. **경량성**: Electron/Tauri/RN 대비 빌드/런타임 부담이 낮고, MVP 속도가 가장 빠름
2. **유지보수성**: 단일 UI 코드베이스 + HTTP API 계약 중심으로 역할 분리 명확
3. **배포성**: 브라우저 즉시 배포(Zero-install) + PWA 설치 옵션으로 확장 가능

### 범위
- 본 문서는 GUI 기술 선택, 백엔드 연동 계약, spline-tsfm 파이프라인 API 초안, 반응형 정보구조를 고정한다.
- 실제 구현 코드는 범위 외(후속 Sprint에서 진행).

---

## 1. 기술 후보 비교 (웹/PWA vs Electron/Tauri vs React Native)

## 1.1 비교 기준
- 성능/경량성 (앱 크기, 메모리, 초기 구동)
- 개발 생산성 (MVP 속도, 팀 역량 적합성)
- 유지보수성 (코드베이스 수, 테스트 난이도)
- 배포/업데이트 (배포 채널, 롤백, 운영 단순성)
- 시스템 접근성 (파일시스템, 장기 작업 상태 추적, 알림)

## 1.2 후보별 평가

| 항목 | Web/PWA | Electron/Tauri | React Native |
|---|---|---|---|
| 경량성 | **상** (브라우저 기반, 설치 없이 시작) | 중~하 (Electron 무거움, Tauri는 개선) | 중 (모바일엔 적합, 데스크톱은 별도 브릿지 필요) |
| 개발 속도 | **상** (웹 스택 표준) | 중 (데스크톱 래핑/권한 처리 추가) | 중~하 (웹과 코드 분리 가능성 큼) |
| 유지보수 | **상** (단일 프론트 코드, API 중심) | 중 (데스크톱 런타임별 이슈) | 하~중 (모바일/웹 병행 시 분산) |
| 배포성 | **상** (URL 배포 + PWA) | 중 (앱 스토어/설치 패키지 관리) | 중 (앱스토어 절차 + 웹 별도) |
| 오프라인 | 중 (캐시 기반 제한적) | 상 (로컬 실행 강점) | 중~상 (모바일 오프라인 가능) |
| 로컬 파일 접근 | 하~중 (브라우저 제약) | **상** (로컬 권한 처리 용이) | 중 (모바일 파일권한 별도 대응) |
| 본 프로젝트 적합성 | **높음** | 중 (2단계 대안으로 적합) | 낮음~중 (우선순위 낮음) |

### 보완 메모
- 로컬 파일/장기 백그라운드 작업 제약이 커지면 **2단계에서 Tauri Shell**을 옵션으로 둔다.
- MVP 목표가 “가볍고 직관적 GUI”이므로 1단계는 Web/PWA가 최적.

---

## 2. 권장 아키텍처 (Target Architecture)

## 2.1 전체 구조

```text
[Client: React PWA]
  ├─ Dataset Upload/Select
  ├─ Pipeline Run Form (preprocess/train/infer)
  ├─ Job Monitor (status/log/metrics)
  └─ Result Viewer (chart/table/report)
          │ HTTPS/JSON
          ▼
[FastAPI BFF/API]
  ├─ /api/v1/pipelines/*
  ├─ /api/v1/jobs/*
  ├─ /api/v1/artifacts/*
  └─ /api/v1/health
          │ internal call
          ▼
[Runner Adapter]
  ├─ src.preprocessing.smoke or pipeline entry
  ├─ src.training.runner
  └─ subprocess queue + state store
          │
          ▼
[Artifacts Store]
  ├─ artifacts/processed
  ├─ artifacts/metrics
  ├─ artifacts/reports
  └─ artifacts/checkpoints
```

## 2.2 핵심 설계 원칙
1. **UI는 상태/입력, 실행은 API가 담당** (비즈니스 로직 UI 배제)
2. **Runner 표준입출력 + 아티팩트 경로를 API 계약으로 승격**
3. **장기 작업(Job) 비동기화**: `submit -> poll/status -> result` 패턴 고정
4. **실패 가시성 확보**: stderr/로그/실패코드/재시도 가능 구조

## 2.3 프론트 기술 스택 (권장)
- React + TypeScript + Vite
- UI: Tailwind CSS + headless component 라이브러리(예: shadcn/ui 계열)
- 상태관리: TanStack Query(서버 상태) + 로컬 폼 상태(React Hook Form)
- 차트: ECharts 또는 Recharts
- PWA: Workbox 기반 기본 캐시/설치 지원

---

## 3. 백엔드 연동 계약 (FastAPI / Runner API)

## 3.1 API 설계 원칙
- Prefix: `/api/v1`
- 응답 공통 envelope:

```json
{
  "ok": true,
  "data": {},
  "error": null,
  "request_id": "req_...",
  "ts": "2026-02-18T21:15:00+09:00"
}
```

- 실패 시:

```json
{
  "ok": false,
  "data": null,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "...",
    "details": {}
  },
  "request_id": "req_...",
  "ts": "..."
}
```

## 3.2 Endpoint 계약 초안

### A) 헬스체크
- `GET /api/v1/health`
- 목적: API/runner/artifacts 상태 확인

### B) 파이프라인 실행 제출
- `POST /api/v1/pipelines/spline-tsfm:run`
- 설명: preprocess/train/eval/infer 묶음 실행 또는 단계별 실행

요청 예시:
```json
{
  "run_id": "gui-20260218-001",
  "mode": "train_eval",
  "input": {
    "dataset_path": "data/raw/synthetic/s1.csv",
    "target_cols": ["target"],
    "dynamic_covariates": ["temp", "promo"],
    "lookback": 24,
    "horizon": 1,
    "scaling": "standard"
  },
  "model": {
    "model_type": "lstm",
    "hidden_units": [128, 64],
    "dropout": 0.2,
    "learning_rate": 0.001,
    "epochs": 20,
    "batch_size": 32
  },
  "runtime": {
    "seed": 42,
    "export_formats": ["none"]
  }
}
```

응답 예시:
```json
{
  "ok": true,
  "data": {
    "job_id": "job_01J...",
    "run_id": "gui-20260218-001",
    "status": "queued"
  }
}
```

### C) Job 상태 조회
- `GET /api/v1/jobs/{job_id}`
- 반환: `queued | running | succeeded | failed | canceled`

응답 핵심 필드:
```json
{
  "job_id": "job_01J...",
  "run_id": "gui-20260218-001",
  "status": "running",
  "progress": 62,
  "step": "training",
  "started_at": "...",
  "updated_at": "...",
  "artifacts": {
    "metrics_json": null,
    "report_md": null,
    "checkpoint": null
  }
}
```

### D) Job 로그 조회
- `GET /api/v1/jobs/{job_id}/logs?offset=0&limit=200`
- stdout/stderr 합성 로그 스트림(라인 기반)

### E) 실행 결과(메트릭) 조회
- `GET /api/v1/runs/{run_id}/metrics`
- `GET /api/v1/runs/{run_id}/report`
- `GET /api/v1/runs/{run_id}/artifacts`

### F) 실행 취소
- `POST /api/v1/jobs/{job_id}:cancel`

---

## 4. spline-tsfm 파이프라인 호출/상태조회/API 스펙 초안

## 4.1 단계 모델 (state machine)

```text
queued
  -> preprocessing
  -> training
  -> evaluating
  -> inferencing(optional)
  -> succeeded
(실패 시 failed, 사용자 취소 시 canceled)
```

## 4.2 내부 Runner 매핑 (권장)
- preprocessing: `python3 -m src.preprocessing.smoke ...` 또는 표준 pipeline 엔트리
- train/eval/infer: `python3 -m src.training.runner ...`

## 4.3 표준 Job 데이터 모델

```json
{
  "job_id": "job_01J...",
  "run_id": "gui-20260218-001",
  "pipeline": "spline-tsfm",
  "status": "running",
  "step": "training",
  "progress": 62,
  "command": ["python3", "-m", "src.training.runner", "--run-id", "gui-20260218-001"],
  "exit_code": null,
  "error": null,
  "artifacts": {
    "processed_npz": "artifacts/processed/gui-20260218-001/processed.npz",
    "metrics_json": "artifacts/metrics/gui-20260218-001.json",
    "report_md": "artifacts/reports/gui-20260218-001.md",
    "checkpoint": "artifacts/checkpoints/gui-20260218-001/best.keras"
  }
}
```

## 4.4 API 에러 코드 초안
- `VALIDATION_ERROR` (400): 입력 파라미터/스키마 오류
- `RUN_ID_MISMATCH` (409): 전처리/학습 run_id 불일치
- `ARTIFACT_NOT_FOUND` (404): 산출물 미존재
- `JOB_NOT_FOUND` (404)
- `RUNNER_EXEC_ERROR` (500): subprocess 실행 실패
- `RUNNER_TIMEOUT` (504)

## 4.5 보안/운영 최소 기준
- dataset_path allowlist(프로젝트 루트 하위만 허용)
- shell injection 방지: command list 실행 고정
- request_id/job_id 로 추적성 확보
- 로그 보존 기간/최대 크기 제한

---

## 5. 반응형 UI 정보구조 (모바일/태블릿/데스크톱)

## 5.1 공통 IA (Information Architecture)

1. **Dashboard**
   - 최근 실행, 실패 알림, 핵심 지표 카드
2. **Run Builder**
   - 데이터 선택 → 파라미터 입력 → 실행 제출
3. **Jobs**
   - 큐/실행중/완료/실패 목록 + 필터
4. **Run Detail**
   - 상태 타임라인, 로그, 메트릭 차트, 아티팩트 다운로드
5. **Settings**
   - 기본 경로, seed, 기본 모델 파라미터

## 5.2 레이아웃 기준

### 모바일 (<768px)
- Bottom tab 4개: Dashboard / Run / Jobs / Settings
- Run Detail: 탭 분리(상태 | 로그 | 지표 | 산출물)
- 차트는 1열, 표는 카드형 요약

### 태블릿 (768~1199px)
- 좌측 compact nav + 우측 콘텐츠
- Jobs 목록 + 상세 2-pane(상하 또는 좌우 전환)
- 로그/지표 분할 보기 허용

### 데스크톱 (>=1200px)
- 좌측 사이드바 + 메인 2~3컬럼
- Jobs list / Timeline+Logs / Metrics&Artifacts 동시 표시
- 고급 필터(기간, 상태, model_type, run_id)

## 5.3 UX 핵심 규칙
- 실행 버튼은 필수 필드 유효성 통과 시만 활성화
- 장기 작업은 “백그라운드 진행” 안내 + 종료 알림
- 실패 시 “원인/해결 힌트/재시도”를 한 화면 제공

---

## 6. 비기능 요구사항 (NFR) 초안

- p95 API 응답시간 (조회성): 300ms 이하 목표
- Job 상태 갱신: 2~5초 폴링(또는 SSE/WebSocket은 2단계)
- 동시 실행: MVP 2~4개 Job 제한
- 감사 가능성: run_id/job_id/request_id 3중 추적
- 접근제어: MVP는 로컬/내부망 전제, 추후 Auth 계층 확장

---

## 7. 구현 단계 제안 (2 Sprint)

### Sprint 1 (MVP)
- FastAPI 골격 + `/health`, `/pipelines/...:run`, `/jobs/{id}`, `/jobs/{id}/logs`
- Runner Adapter(subprocess + 상태 저장)
- React PWA: Run Builder + Jobs + Run Detail 기본
- 메트릭/리포트 렌더링 최소 기능

### Sprint 2 (안정화)
- 실패 복구(재시도/취소/타임아웃)
- 아티팩트 브라우저/다운로드 개선
- 고급 필터/검색, UX polishing
- (옵션) Tauri shell PoC for local-heavy users

---

## 8. 리스크 및 대응

1. **브라우저 기반 파일 접근 한계**
   - 대응: 서버 측 경로 선택 + 업로드 API + 경로 allowlist
2. **장시간 학습 Job 중단/유실**
   - 대응: 상태 저장(파일/SQLite), 재시작 복구 로직
3. **런너 파라미터 드리프트**
   - 대응: API schema versioning + config snapshot 저장
4. **로그 과다/디스크 증가**
   - 대응: 롤링/보존 정책, 최대 파일 크기 제한

---

## 9. Handoff Checklist (인수인계 체크리스트)

- [ ] `backend/app/main.py` FastAPI 엔트리 생성
- [ ] `backend/app/schemas.py` 요청/응답 Pydantic 스키마 정의
- [ ] `backend/app/jobs.py` Job 상태 저장소(초기: SQLite 또는 JSONL)
- [ ] `backend/app/runner_adapter.py` runner command mapping 구현
- [ ] `frontend/` React PWA 부트스트랩
- [ ] Run Builder ↔ `/pipelines/spline-tsfm:run` 연동
- [ ] Jobs/Run Detail ↔ `/jobs/*`, `/runs/*` 연동
- [ ] 오류 코드/메시지 표준화 테스트
- [ ] run_id mismatch 시나리오 회귀 테스트

---

## 10. 최종 결론

본 프로젝트의 현재 목표(가볍고 직관적인 GUI, 빠른 실험/검증, 유지보수 용이성)를 고려하면,
**1단계 아키텍처는 Web/PWA + FastAPI + Runner Adapter가 최적**이다.

Desktop-native 기능(심화 로컬 접근, 오프라인 우선)이 강하게 필요해지는 시점에만
**2단계로 Tauri 래핑**을 검토하는 전략이 비용/효과 측면에서 가장 합리적이다.
