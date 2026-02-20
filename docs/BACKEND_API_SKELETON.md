# BACKEND_API_SKELETON

GUI real-mode 연동을 위한 `/api/v1` 백엔드 스켈레톤 가이드입니다.

## 1) 실행

```bash
cd ~/spline-lstm
python3 -m pip install -r requirements.txt
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

- 기본 URL: `http://127.0.0.1:8000`
- API Prefix: `/api/v1`

## 2) 제공 엔드포인트

- `GET /api/v1/health`
- `GET /api/v1/dashboard/summary`
- `GET /api/v1/jobs?limit=10`
- `POST /api/v1/pipelines/spline-tsfm:run`
- `GET /api/v1/jobs/{job_id}`
- `GET /api/v1/jobs/{job_id}/logs?offset=0&limit=200`
- `POST /api/v1/jobs/{job_id}:cancel`
- `GET /api/v1/runs/{run_id}/metrics`
- `GET /api/v1/runs/{run_id}/artifacts`
- `GET /api/v1/runs/{run_id}/report`

## 3) Executor 모드 (real vs mock)

환경변수로 실행경로를 제어합니다.

| `SPLINE_BACKEND_EXECUTOR_MODE` | 동작 |
|---|---|
| `mock` | 시간기반 시뮬레이션(`queued->running->succeeded`) + mock artifact 생성 |
| `real` | 실제 subprocess 실행 (`SPLINE_BACKEND_RUNNER_CMD`) |
| `auto` | `SPLINE_BACKEND_RUNNER_CMD`가 명시된 경우 real, 아니면 mock |

관련 환경변수:

- `SPLINE_BACKEND_RUNNER_CMD` (기본: `python -m src.training.runner`)
- `SPLINE_BACKEND_RUN_TIMEOUT_SEC` (기본: 1800)
- `SPLINE_BACKEND_RUNNER_EPOCHS` (기본: 1)
- `SPLINE_BACKEND_ARTIFACTS_DIR` (기본: `artifacts/`)
- `SPLINE_BACKEND_STORE_PATH` (기본: `backend/data/jobs_store.json`)

## 4) 저장소/아티팩트

- job 저장: `backend/data/jobs_store.json` (override 가능)
- run 결과 아티팩트:
  - `artifacts/metrics/{run_id}.json`
  - `artifacts/reports/{run_id}.md`
  - `artifacts/runs/{run_id}.meta.json`

## 5) Structured logs/status

`GET /jobs/{job_id}/logs`는 아래 구조를 반환합니다.

```json
{
  "ts": "2026-01-01T00:00:00+00:00",
  "level": "INFO",
  "source": "stdout|stderr|runtime|mock",
  "message": "..."
}
```

real 모드에서는 subprocess stdout/stderr를 캡처해 구조화된 로그로 노출합니다.

## 6) 운영 caveats

- real 모드는 host 런타임(파이썬/의존성/TensorFlow backend)에 의존합니다.
- 장기 실행 취소는 SIGTERM 후 grace period 뒤 SIGKILL로 종료합니다.
- 현재 상태 저장은 JSON 파일 기반이며, 멀티 프로세스/멀티 인스턴스 동시성 보장은 제한적입니다.
- mock은 개발/CI fallback 경로이며 운영 성공 지표로 간주하면 안 됩니다.
