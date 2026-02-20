from __future__ import annotations

import contextvars
import copy
import hashlib
import json
import logging
import os
import shlex
import signal
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import fcntl
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

API_PREFIX = "/api/v1"
ROOT_DIR = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = Path(os.getenv("SPLINE_BACKEND_ARTIFACTS_DIR", str(ROOT_DIR / "artifacts"))).resolve()
STORE_PATH = Path(os.getenv("SPLINE_BACKEND_STORE_PATH", str(ROOT_DIR / "backend" / "data" / "jobs_store.json"))).resolve()


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_csv(name: str, default: List[str]) -> List[str]:
    raw = os.getenv(name)
    if not raw:
        return default
    return [x.strip() for x in raw.split(",") if x.strip()]


def _security_config() -> Dict[str, Any]:
    env = os.getenv("SPLINE_ENV", "dev").strip().lower()
    dev_mode = _env_flag("SPLINE_DEV_MODE", default=(env != "prod"))
    api_token = os.getenv("SPLINE_API_TOKEN")
    auth_required = not dev_mode
    if auth_required and not api_token:
        raise RuntimeError("SPLINE_API_TOKEN must be set when SPLINE_DEV_MODE=0")

    cors_origins = _env_csv(
        "SPLINE_CORS_ORIGINS",
        [
            "http://localhost",
            "http://127.0.0.1",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
            "http://localhost:4174",
            "http://127.0.0.1:4174",
        ] if dev_mode else [],
    )
    trusted_hosts = _env_csv("SPLINE_TRUSTED_HOSTS", ["localhost", "127.0.0.1", "testserver"])
    return {
        "env": env,
        "dev_mode": dev_mode,
        "api_token": api_token,
        "auth_required": auth_required,
        "cors_origins": cors_origins,
        "trusted_hosts": trusted_hosts,
    }


SECURITY = _security_config()

PHASE6_FLAGS = {
    "enable_adjusted_execute": _env_flag("SPLINE_PHASE6_ENABLE_ADJUSTED_EXECUTE", True),
    "enable_tollama_adapter": _env_flag("SPLINE_PHASE6_ENABLE_TOLLAMA_ADAPTER", True),
    "enable_mcp": _env_flag("SPLINE_PHASE6_ENABLE_MCP", True),
}

_IDEMPOTENCY_LOCK = threading.Lock()
_IDEMPOTENCY_CACHE: Dict[str, Dict[str, Any]] = {}
_RATE_LOCK = threading.Lock()
_RATE_BUCKETS: Dict[str, List[float]] = {}

_REQUEST_ID: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = _REQUEST_ID.get() or ""
        return True


logger = logging.getLogger("backend.app")
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s %(message)s"))
    _h.addFilter(RequestIdFilter())
    logger.addHandler(_h)
logger.setLevel(logging.INFO)
logger.propagate = False


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _atomic_write_text(path: Path, text: str) -> None:
    _ensure_parent(path)
    tmp = path.with_suffix(path.suffix + f".tmp.{uuid.uuid4().hex[:8]}")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _sanitize_line(raw: str) -> str:
    return raw.rstrip("\r\n")[:2000]


def _rate_limit_or_raise(key: str, limit: int = 30, window_sec: int = 60) -> None:
    now = time.time()
    with _RATE_LOCK:
        bucket = [ts for ts in _RATE_BUCKETS.get(key, []) if now - ts < window_sec]
        if len(bucket) >= limit:
            raise HTTPException(status_code=429, detail="rate limit exceeded")
        bucket.append(now)
        _RATE_BUCKETS[key] = bucket


def _idempotency_get(key: str) -> Optional[Dict[str, Any]]:
    with _IDEMPOTENCY_LOCK:
        return copy.deepcopy(_IDEMPOTENCY_CACHE.get(key))


def _idempotency_put(key: str, value: Dict[str, Any]) -> None:
    with _IDEMPOTENCY_LOCK:
        _IDEMPOTENCY_CACHE[key] = copy.deepcopy(value)


@dataclass
class JobRecord:
    job_id: str
    run_id: str
    model_type: str
    feature_mode: str
    created_at: float
    status: str = "queued"
    message: Optional[str] = None
    step: Optional[str] = "queued"
    progress: Optional[int] = 0
    updated_at: Optional[str] = None
    error_message: Optional[str] = None
    canceled: bool = False
    execution_mode: str = "mock"
    exit_code: Optional[int] = None


class JobStore:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()
        self._records: Dict[str, JobRecord] = {}
        self.corrupted_file: Optional[str] = None
        self.last_save_error: Optional[str] = None
        self._load()

    @property
    def lock_path(self) -> Path:
        return self.path.with_suffix(self.path.suffix + ".lock")

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception as exc:
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            bad_path = self.path.with_suffix(self.path.suffix + f".corrupt.{ts}")
            try:
                os.replace(self.path, bad_path)
                self.corrupted_file = str(bad_path)
            except Exception:
                self.corrupted_file = str(self.path)
            logger.error("job_store_corrupt_json path=%s error=%s", self.path, exc)
            return
        if not isinstance(raw, dict):
            return
        for item in raw.get("jobs", []):
            try:
                rec = JobRecord(**item)
            except Exception:
                continue
            self._records[rec.job_id] = rec

    def _save(self) -> None:
        _ensure_parent(self.path)
        payload = {"jobs": [asdict(v) for v in self._records.values()]}
        serialized = json.dumps(payload, ensure_ascii=False, indent=2)
        try:
            with open(self.lock_path, "a+", encoding="utf-8") as lockf:
                fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)
                _atomic_write_text(self.path, serialized)
                fcntl.flock(lockf.fileno(), fcntl.LOCK_UN)
            self.last_save_error = None
        except Exception as exc:
            self.last_save_error = str(exc)
            logger.error("job_store_save_failed path=%s error=%s", self.path, exc)
            raise

    def upsert(self, rec: JobRecord) -> None:
        with self.lock:
            rec.updated_at = _utc_now_iso()
            self._records[rec.job_id] = rec
            self._save()

    def get(self, job_id: str) -> Optional[JobRecord]:
        with self.lock:
            rec = self._records.get(job_id)
            return JobRecord(**asdict(rec)) if rec else None

    def list_recent(self, limit: int = 20) -> List[JobRecord]:
        with self.lock:
            values = list(self._records.values())
        values.sort(key=lambda x: x.created_at, reverse=True)
        return [JobRecord(**asdict(v)) for v in values[:limit]]

    def diagnostics(self) -> Dict[str, Any]:
        return {
            "path": str(self.path),
            "lock_path": str(self.lock_path),
            "records": len(self._records),
            "corrupted_file": self.corrupted_file,
            "last_save_error": self.last_save_error,
        }


@dataclass
class JobRuntime:
    process: Optional[subprocess.Popen[str]] = None
    logs: List[Dict[str, Any]] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)
    started_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None

    def append_log(self, level: str, message: str, source: str = "runtime") -> None:
        with self.lock:
            self.logs.append({"ts": _utc_now_iso(), "level": level, "source": source, "message": _sanitize_line(message)})
            if len(self.logs) > 5000:
                self.logs = self.logs[-5000:]

    def read_logs(self, offset: int, limit: int) -> List[Dict[str, Any]]:
        with self.lock:
            return list(self.logs[offset : offset + limit])


class JobExecutor:
    def __init__(self, store: JobStore):
        self.store = store
        self._runtimes: Dict[str, JobRuntime] = {}
        self._lock = threading.Lock()

    def _mode(self) -> str:
        return os.getenv("SPLINE_BACKEND_EXECUTOR_MODE", "auto").strip().lower()

    def _command_template(self) -> List[str]:
        raw = os.getenv("SPLINE_BACKEND_RUNNER_CMD", f"{sys.executable} -m src.training.runner")
        return shlex.split(raw)

    def _timeout_sec(self) -> int:
        try:
            return max(5, int(os.getenv("SPLINE_BACKEND_RUN_TIMEOUT_SEC", "1800")))
        except Exception:
            return 1800

    def should_use_real(self) -> bool:
        mode = self._mode()
        if mode == "mock":
            return False
        if mode == "real":
            return True
        # auto: require explicit opt-in runtime availability check
        return bool(shlex.split(os.getenv("SPLINE_BACKEND_RUNNER_CMD", "")))

    def submit(self, rec: JobRecord) -> None:
        if self.should_use_real():
            rec.execution_mode = "real"
            self.store.upsert(rec)
            self._start_real_job(rec)
            return

        rec.execution_mode = "mock"
        self.store.upsert(rec)

    def _start_real_job(self, rec: JobRecord) -> None:
        runtime = JobRuntime()
        with self._lock:
            self._runtimes[rec.job_id] = runtime

        args = self._command_template() + [
            "--run-id",
            rec.run_id,
            "--artifacts-dir",
            str(ARTIFACTS_DIR),
            "--model-type",
            rec.model_type,
            "--feature-mode",
            rec.feature_mode,
            "--epochs",
            os.getenv("SPLINE_BACKEND_RUNNER_EPOCHS", "1"),
            "--verbose",
            "0",
        ]

        try:
            process = subprocess.Popen(
                args,
                cwd=str(ROOT_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                start_new_session=True,
            )
            runtime.process = process
            runtime.append_log("INFO", f"spawned pid={process.pid} cmd={' '.join(args)}")
            rec.status = "running"
            rec.step = "training"
            rec.progress = 5
            rec.message = "runner started"
            self.store.upsert(rec)

            threading.Thread(target=self._pump_stream, args=(rec.job_id, process.stdout, "stdout"), daemon=True).start()
            threading.Thread(target=self._pump_stream, args=(rec.job_id, process.stderr, "stderr"), daemon=True).start()
            threading.Thread(target=self._wait_and_finalize, args=(rec.job_id, process, self._timeout_sec()), daemon=True).start()
        except Exception as exc:
            runtime.append_log("ERROR", f"executor spawn failed: {exc}")
            rec.status = "failed"
            rec.step = "failed"
            rec.progress = 100
            rec.error_message = f"executor spawn failed: {exc}"
            rec.message = "runner failed to start"
            self.store.upsert(rec)

    def _pump_stream(self, job_id: str, stream: Any, source: str) -> None:
        if stream is None:
            return
        for line in stream:
            runtime = self._runtimes.get(job_id)
            if runtime is None:
                return
            runtime.append_log("INFO" if source == "stdout" else "WARN", line, source=source)

    def _wait_and_finalize(self, job_id: str, process: subprocess.Popen[str], timeout_sec: int) -> None:
        runtime = self._runtimes.get(job_id)
        rec = self.store.get(job_id)
        if rec is None:
            return

        try:
            exit_code = process.wait(timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            self._terminate_process(process)
            exit_code = -signal.SIGKILL
            if runtime:
                runtime.append_log("ERROR", f"timeout exceeded ({timeout_sec}s)")

        rec = self.store.get(job_id)
        if rec is None:
            return

        rec.exit_code = int(exit_code)
        rec.progress = 100

        if rec.canceled:
            rec.status = "canceled"
            rec.step = "canceled"
            rec.message = "cancel accepted"
            rec.error_message = rec.error_message or "사용자 요청으로 작업이 취소되었습니다."
        elif exit_code == 0:
            rec.status = "succeeded"
            rec.step = "finished"
            rec.message = "completed"
            _ensure_mock_run_artifacts(rec)
        else:
            rec.status = "failed"
            rec.step = "failed"
            rec.message = "failed"
            rec.error_message = rec.error_message or f"runner exited with code {exit_code}"
        self.store.upsert(rec)

        if runtime:
            runtime.finished_at = time.time()
            runtime.append_log("INFO", f"process finished exit_code={exit_code}")

    def _terminate_process(self, process: subprocess.Popen[str]) -> None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except Exception:
            try:
                process.terminate()
            except Exception:
                pass
        try:
            process.wait(timeout=3)
        except Exception:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass

    def cancel(self, job_id: str) -> bool:
        runtime = self._runtimes.get(job_id)
        if runtime and runtime.process and runtime.process.poll() is None:
            runtime.append_log("WARN", "cancel requested")
            self._terminate_process(runtime.process)
            return True
        return False

    def logs(self, job_id: str, offset: int, limit: int) -> List[Dict[str, Any]]:
        runtime = self._runtimes.get(job_id)
        if runtime is None:
            return []
        return runtime.read_logs(offset, limit)


store = JobStore(STORE_PATH)
executor = JobExecutor(store)
app = FastAPI(title="spline-lstm backend skeleton", version="0.2.0")

if SECURITY["trusted_hosts"]:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=SECURITY["trusted_hosts"])
if SECURITY["cors_origins"]:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=SECURITY["cors_origins"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-API-Token"],
        max_age=600,
    )


@app.middleware("http")
async def _security_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or f"req-{uuid.uuid4().hex[:12]}"
    token = _REQUEST_ID.set(request_id)
    request.state.request_id = request_id
    try:
        path = request.url.path
        if path.startswith(API_PREFIX) and path != f"{API_PREFIX}/health" and SECURITY["auth_required"]:
            token_header = request.headers.get("x-api-token")
            if token_header != SECURITY["api_token"]:
                return JSONResponse(status_code=401, content={"ok": False, "error": "unauthorized"})

        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["x-request-id"] = request_id
        return response
    finally:
        _REQUEST_ID.reset(token)


def _corr(request: Optional[Request] = None, job_id: Optional[str] = None, run_id: Optional[str] = None) -> Dict[str, str]:
    rid = getattr(getattr(request, "state", None), "request_id", None) or _REQUEST_ID.get() or ""
    out = {"request_id": rid}
    if job_id:
        out["job_id"] = job_id
    if run_id:
        out["run_id"] = run_id
    return out


@app.exception_handler(HTTPException)
async def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if exc.status_code >= 500:
        logger.exception("HTTPException path=%s detail=%s", request.url.path, exc.detail)
        return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": "internal server error"})
    return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": exc.detail})


@app.exception_handler(RequestValidationError)
async def _validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    logger.warning("Validation error path=%s detail=%s", request.url.path, exc.errors())
    return JSONResponse(status_code=422, content={"ok": False, "error": "invalid request"})


@app.exception_handler(Exception)
async def _generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error path=%s", request.url.path)
    return JSONResponse(status_code=500, content={"ok": False, "error": "internal server error"})


class RunRequest(BaseModel):
    run_id: Optional[str] = None
    runId: Optional[str] = None
    model_type: Optional[str] = None
    model: Optional[str] = None
    feature_mode: Optional[str] = "univariate"
    model_config_payload: Optional[Dict[str, Any]] = Field(default=None, alias="model_config")


class InputPatchOperation(BaseModel):
    op: str = Field(pattern="^(replace|add)$")
    path: str
    value: Any
    reason: Optional[str] = None


class ForecastInputRequest(BaseModel):
    run_id: str
    actor: Optional[str] = "anonymous"
    base_inputs: Dict[str, Any]
    patches: List[InputPatchOperation] = Field(default_factory=list)


class AgentToolInvokeRequest(BaseModel):
    tool: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class ForecastExecuteAdjustedRequest(ForecastInputRequest):
    model_type: Optional[str] = "lstm"
    feature_mode: Optional[str] = "multivariate"


class CovariateFieldSpec(BaseModel):
    name: str
    type: str = Field(pattern="^(numeric|categorical|boolean)$")
    required: bool = True
    known_future: bool = False
    source: Optional[str] = None


class CovariateContractValidateRequest(BaseModel):
    covariate_schema: List[CovariateFieldSpec]
    payload: Dict[str, Any]
    strict_order: bool = True


@app.get(f"{API_PREFIX}/health")
def health() -> Dict[str, Any]:
    writable = False
    try:
        _ensure_parent(STORE_PATH)
        probe = STORE_PATH.parent / ".writecheck.tmp"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        writable = True
    except Exception:
        writable = False

    return {
        "ok": True,
        "data": {
            "status": "healthy",
            "service": "backend-skeleton",
            "ts": _utc_now_iso(),
            "executor_mode": executor._mode(),
            "security": {"dev_mode": SECURITY["dev_mode"], "auth_required": SECURITY["auth_required"]},
            "details": {
                "store": store.diagnostics(),
                "artifacts_dir": str(ARTIFACTS_DIR),
                "store_dir_writable": writable,
            },
        },
    }


def _compute_status(rec: JobRecord) -> JobRecord:
    if rec.execution_mode == "real":
        return rec

    if rec.canceled:
        rec.status = "canceled"
        rec.step = "canceled"
        rec.progress = 100
        rec.error_message = rec.error_message or "사용자 요청으로 작업이 취소되었습니다."
        rec.message = "cancel accepted"
        return rec

    elapsed = time.time() - rec.created_at
    if elapsed < 1.0:
        rec.status = "queued"
        rec.step = "queued"
        rec.progress = 0
        rec.message = "job accepted"
    elif elapsed < 3.0:
        rec.status = "running"
        rec.step = "training"
        rec.progress = 55
        rec.message = "training"
    else:
        rec.status = "succeeded"
        rec.step = "finished"
        rec.progress = 100
        rec.message = "completed"
        _ensure_mock_run_artifacts(rec)
    return rec


def _ensure_mock_run_artifacts(rec: JobRecord) -> None:
    metrics_dir = ARTIFACTS_DIR / "metrics"
    reports_dir = ARTIFACTS_DIR / "reports"
    runmeta_dir = ARTIFACTS_DIR / "runs"
    for d in (metrics_dir, reports_dir, runmeta_dir):
        d.mkdir(parents=True, exist_ok=True)

    metrics_path = metrics_dir / f"{rec.run_id}.json"
    if not metrics_path.exists():
        try:
            metrics_json_ref = str(metrics_path.relative_to(ROOT_DIR))
        except ValueError:
            metrics_json_ref = str(metrics_path)
        payload = {
            "run_id": rec.run_id,
            "metrics": {"rmse": 0.123, "mae": 0.088, "mape": 4.2},
            "config": {"model_type": rec.model_type, "feature_mode": rec.feature_mode},
            "artifacts": {
                "metrics_json": metrics_json_ref,
                "report_md": f"artifacts/reports/{rec.run_id}.md",
            },
        }
        _atomic_write_text(metrics_path, json.dumps(payload, ensure_ascii=False, indent=2))

    report_path = reports_dir / f"{rec.run_id}.md"
    if not report_path.exists():
        _atomic_write_text(
            report_path,
            f"# Run Report\n\n- run_id: {rec.run_id}\n- model: {rec.model_type}\n- feature_mode: {rec.feature_mode}\n",
        )

    runmeta_path = runmeta_dir / f"{rec.run_id}.meta.json"
    if not runmeta_path.exists():
        _atomic_write_text(
            runmeta_path,
            json.dumps({"run_id": rec.run_id, "job_id": rec.job_id, "status": rec.status}, ensure_ascii=False, indent=2),
        )


def _to_job_payload(rec: JobRecord, request: Optional[Request] = None) -> Dict[str, Any]:
    cur = _compute_status(rec)
    store.upsert(cur)
    return {
        "job_id": cur.job_id,
        "run_id": cur.run_id,
        "status": cur.status,
        "message": cur.message,
        "error_message": cur.error_message,
        "step": cur.step,
        "progress": cur.progress,
        "updated_at": cur.updated_at,
        "execution_mode": cur.execution_mode,
        "exit_code": cur.exit_code,
        "correlation": _corr(request, job_id=cur.job_id, run_id=cur.run_id),
    }


@app.get(f"{API_PREFIX}/dashboard/summary")
def dashboard_summary(request: Request) -> Dict[str, Any]:
    jobs = [_to_job_payload(job, request=request) for job in store.list_recent(limit=10)]
    recent_jobs = [
        {
            "runId": j["run_id"],
            "status": "success" if j["status"] == "succeeded" else j["status"],
            "startedAt": j.get("updated_at") or "",
            "model": "lstm",
            "requestId": j.get("correlation", {}).get("request_id", ""),
            "jobId": j.get("job_id", ""),
        }
        for j in jobs[:5]
    ]
    last_run = recent_jobs[0]["runId"] if recent_jobs else ""
    return {
        "ok": True,
        "data": {
            "serviceStatus": "healthy",
            "lastRunId": last_run,
            "lastRmse": 0.123,
            "recentJobs": recent_jobs,
            "correlation": _corr(request),
        },
    }


@app.get(f"{API_PREFIX}/jobs")
def list_jobs(request: Request, limit: int = Query(default=10, ge=1, le=100)) -> Dict[str, Any]:
    jobs = [_to_job_payload(job, request=request) for job in store.list_recent(limit=limit)]
    return {"ok": True, "data": {"jobs": jobs, "correlation": _corr(request)}}


@app.post(f"{API_PREFIX}/pipelines/spline-tsfm:run")
def run_pipeline(payload: RunRequest, request: Request) -> Dict[str, Any]:
    run_id = payload.run_id or payload.runId or f"run-{int(time.time())}"
    model_type = payload.model_type or payload.model or (payload.model_config_payload or {}).get("model_type") or "lstm"
    feature_mode = payload.feature_mode or "univariate"
    rec = JobRecord(
        job_id=f"job-{uuid.uuid4().hex[:12]}",
        run_id=run_id,
        model_type=model_type,
        feature_mode=feature_mode,
        created_at=time.time(),
    )
    store.upsert(rec)
    executor.submit(rec)
    return {
        "ok": True,
        "data": {
            "job_id": rec.job_id,
            "run_id": rec.run_id,
            "status": "queued",
            "message": "job accepted",
            "execution_mode": rec.execution_mode,
            "correlation": _corr(request, job_id=rec.job_id, run_id=rec.run_id),
        },
    }


@app.get(f"{API_PREFIX}/jobs/{{job_id}}")
def get_job(job_id: str, request: Request) -> Dict[str, Any]:
    rec = store.get(job_id)
    if not rec:
        raise HTTPException(status_code=404, detail="job not found")
    return {"ok": True, "data": _to_job_payload(rec, request=request)}


@app.post(f"{API_PREFIX}/jobs/{{job_id}}:cancel")
def cancel_job(job_id: str, request: Request) -> Dict[str, Any]:
    rec = store.get(job_id)
    if not rec:
        raise HTTPException(status_code=404, detail="job not found")
    rec.canceled = True
    rec.status = "canceled"
    rec.step = "canceled"
    rec.progress = 100
    rec.error_message = "사용자 요청으로 작업이 취소되었습니다."
    rec.message = "cancel accepted"
    store.upsert(rec)
    executor.cancel(job_id)
    return {"ok": True, "data": _to_job_payload(rec, request=request)}


@app.get(f"{API_PREFIX}/jobs/{{job_id}}/logs")
def get_logs(job_id: str, request: Request, offset: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=1000)) -> Dict[str, Any]:
    rec = store.get(job_id)
    if not rec:
        raise HTTPException(status_code=404, detail="job not found")

    corr = _corr(request, job_id=job_id, run_id=rec.run_id)
    runtime_lines = executor.logs(job_id, offset, limit)
    if runtime_lines:
        enriched = [{**line, **corr} for line in runtime_lines]
        return {"ok": True, "data": {"job_id": job_id, "lines": enriched, "correlation": corr}}

    cur = _compute_status(rec)
    base = datetime.fromtimestamp(rec.created_at, tz=timezone.utc)
    lines = [
        {"ts": base.isoformat(), "level": "INFO", "source": "mock", "message": "job accepted", **corr},
        {"ts": (base.replace(microsecond=0)).isoformat(), "level": "INFO", "source": "mock", "message": "preprocessing", **corr},
        {"ts": _utc_now_iso(), "level": "INFO", "source": "mock", "message": f"status={cur.status}", **corr},
    ]
    sliced = lines[offset : offset + limit]
    return {"ok": True, "data": {"job_id": job_id, "lines": sliced, "correlation": corr}}


def _read_json_if_exists(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


_ADJUSTABLE_TOP_LEVEL_FIELDS = {
    "horizon",
    "target_history",
    "known_future_covariates",
    "static_covariates",
}


def _payload_hash(payload: Dict[str, Any]) -> str:
    normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _set_nested_value(target: Dict[str, Any], path: str, value: Any) -> None:
    if not path.startswith("/"):
        raise ValueError("path must start with '/'")
    parts = [p for p in path.strip("/").split("/") if p]
    if not parts:
        raise ValueError("path must not be empty")
    if parts[0] not in _ADJUSTABLE_TOP_LEVEL_FIELDS:
        raise ValueError(f"path root '{parts[0]}' is not adjustable")

    cur: Any = target
    for idx, key in enumerate(parts[:-1]):
        next_key = parts[idx + 1]
        if isinstance(cur, list):
            i = int(key)
            if i < 0 or i >= len(cur):
                raise ValueError("list index out of range")
            cur = cur[i]
        elif isinstance(cur, dict):
            if key not in cur:
                cur[key] = [] if next_key.isdigit() else {}
            cur = cur[key]
        else:
            raise ValueError("invalid patch path")

    leaf = parts[-1]
    if isinstance(cur, list):
        i = int(leaf)
        if i < 0 or i >= len(cur):
            raise ValueError("list index out of range")
        cur[i] = value
    elif isinstance(cur, dict):
        cur[leaf] = value
    else:
        raise ValueError("invalid patch target")


def _validate_forecast_inputs(inputs: Dict[str, Any]) -> None:
    horizon = inputs.get("horizon", 1)
    if not isinstance(horizon, int) or horizon < 1 or horizon > 168:
        raise ValueError("horizon must be an int between 1 and 168")

    history = inputs.get("target_history", [])
    if not isinstance(history, list) or len(history) < 2:
        raise ValueError("target_history must contain at least 2 points")
    if any(not isinstance(x, (int, float)) for x in history):
        raise ValueError("target_history must be numeric list")

    for key in ("known_future_covariates", "static_covariates"):
        raw = inputs.get(key, {})
        if raw is None:
            continue
        if not isinstance(raw, dict):
            raise ValueError(f"{key} must be an object")


def _naive_preview(inputs: Dict[str, Any]) -> List[float]:
    history = inputs.get("target_history", [])
    horizon = inputs.get("horizon", 1)
    last = float(history[-1]) if history else 0.0

    cov = inputs.get("known_future_covariates", {})
    cov_effect = 0.0
    if isinstance(cov, dict):
        vals: List[float] = []
        for v in cov.values():
            if isinstance(v, (int, float)):
                vals.append(float(v))
            elif isinstance(v, list):
                vals.extend(float(x) for x in v if isinstance(x, (int, float)))
        if vals:
            cov_effect = sum(vals) / len(vals) * 0.01

    return [round(last + cov_effect, 6) for _ in range(horizon)]


def _append_adjustment_audit(event: Dict[str, Any]) -> None:
    audit_path = ARTIFACTS_DIR / "audit" / "input_adjustments.jsonl"
    _ensure_parent(audit_path)
    with open(audit_path, "a", encoding="utf-8") as fp:
        fp.write(json.dumps(event, ensure_ascii=False) + "\n")


def _apply_input_patches(base_inputs: Dict[str, Any], patches: List[InputPatchOperation]) -> Dict[str, Any]:
    candidate = copy.deepcopy(base_inputs)
    for patch in patches:
        if patch.path.startswith("/target_history") and not patch.reason:
            raise ValueError("target_history patch requires reason")
        _set_nested_value(candidate, patch.path, patch.value)
    _validate_forecast_inputs(candidate)
    return candidate


def _validate_covariate_contract(
    schema: List[CovariateFieldSpec], payload: Dict[str, Any], strict_order: bool = True
) -> Dict[str, Any]:
    if "covariates" not in payload or not isinstance(payload.get("covariates"), dict):
        raise ValueError("payload.covariates must be an object")
    covariates: Dict[str, Any] = payload["covariates"]

    expected = [item.name for item in schema]
    required = {item.name for item in schema if item.required}

    missing = sorted([name for name in required if name not in covariates])
    extras = sorted([name for name in covariates.keys() if name not in expected])

    order_ok = True
    if strict_order:
        order_ok = list(covariates.keys()) == expected

    type_violations: List[str] = []
    type_map = {item.name: item.type for item in schema}
    for name, value in covariates.items():
        dtype = type_map.get(name)
        if dtype is None:
            continue
        if dtype == "numeric" and not isinstance(value, (int, float)):
            type_violations.append(name)
        if dtype == "boolean" and not isinstance(value, bool):
            type_violations.append(name)
        if dtype == "categorical" and not isinstance(value, str):
            type_violations.append(name)

    return {
        "valid": not missing and not extras and order_ok and not type_violations,
        "missing": missing,
        "extras": extras,
        "order_ok": order_ok,
        "type_violations": sorted(type_violations),
        "schema_hash": _payload_hash({"schema": [item.model_dump() for item in schema]}),
    }


def _store_adjusted_inputs(run_id: str, payload: Dict[str, Any]) -> str:
    target = ARTIFACTS_DIR / "inputs" / f"{run_id}.adjusted.json"
    _atomic_write_text(target, json.dumps(payload, ensure_ascii=False, indent=2))
    try:
        return str(target.relative_to(ROOT_DIR))
    except ValueError:
        return str(target)


def _jsonl_stream(chunks: List[Dict[str, Any]]) -> StreamingResponse:
    def _iter():
        for chunk in chunks:
            yield json.dumps(chunk, ensure_ascii=False) + "\n"

    return StreamingResponse(_iter(), media_type="application/x-ndjson")


@app.post(f"{API_PREFIX}/forecast/validate-inputs")
def validate_forecast_inputs(payload: ForecastInputRequest, request: Request) -> Dict[str, Any]:
    candidate = json.loads(json.dumps(payload.base_inputs, ensure_ascii=False))
    original_hash = _payload_hash(candidate)
    try:
        candidate = _apply_input_patches(candidate, payload.patches)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "ok": True,
        "data": {
            "run_id": payload.run_id,
            "valid": True,
            "input_hash_before": original_hash,
            "input_hash_after": _payload_hash(candidate),
            "correlation": _corr(request, run_id=payload.run_id),
        },
    }


@app.post(f"{API_PREFIX}/forecast/preview")
def preview_forecast(payload: ForecastInputRequest, request: Request) -> Dict[str, Any]:
    candidate = json.loads(json.dumps(payload.base_inputs, ensure_ascii=False))
    before_hash = _payload_hash(candidate)
    try:
        candidate = _apply_input_patches(candidate, payload.patches)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    preview = _naive_preview(candidate)
    after_hash = _payload_hash(candidate)
    _append_adjustment_audit(
        {
            "ts": _utc_now_iso(),
            "run_id": payload.run_id,
            "actor": payload.actor,
            "patches": [p.model_dump() for p in payload.patches],
            "input_hash_before": before_hash,
            "input_hash_after": after_hash,
        }
    )
    return {
        "ok": True,
        "data": {
            "run_id": payload.run_id,
            "preview": preview,
            "input_hash_before": before_hash,
            "input_hash_after": after_hash,
            "correlation": _corr(request, run_id=payload.run_id),
        },
    }


@app.post(f"{API_PREFIX}/forecast/execute-adjusted")
def execute_adjusted_forecast(payload: ForecastExecuteAdjustedRequest, request: Request) -> Dict[str, Any]:
    if not PHASE6_FLAGS["enable_adjusted_execute"]:
        raise HTTPException(status_code=503, detail="adjusted execution disabled")

    base = json.loads(json.dumps(payload.base_inputs, ensure_ascii=False))
    before_hash = _payload_hash(base)
    try:
        adjusted = _apply_input_patches(base, payload.patches)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    after_hash = _payload_hash(adjusted)
    run_id = payload.run_id
    stored_ref = _store_adjusted_inputs(run_id, adjusted)

    rec = JobRecord(
        job_id=f"job-{uuid.uuid4().hex[:12]}",
        run_id=run_id,
        model_type=payload.model_type or "lstm",
        feature_mode=payload.feature_mode or "multivariate",
        created_at=time.time(),
    )
    store.upsert(rec)
    executor.submit(rec)

    _append_adjustment_audit(
        {
            "ts": _utc_now_iso(),
            "run_id": run_id,
            "job_id": rec.job_id,
            "actor": payload.actor,
            "patches": [p.model_dump() for p in payload.patches],
            "input_hash_before": before_hash,
            "input_hash_after": after_hash,
            "input_ref": stored_ref,
            "action": "execute_adjusted",
        }
    )

    return {
        "ok": True,
        "data": {
            "run_id": run_id,
            "job_id": rec.job_id,
            "status": "queued",
            "input_hash_before": before_hash,
            "input_hash_after": after_hash,
            "adjusted_input_ref": stored_ref,
            "correlation": _corr(request, run_id=run_id, job_id=rec.job_id),
        },
    }


@app.post(f"{API_PREFIX}/covariates/validate")
def validate_covariate_contract(payload: CovariateContractValidateRequest, request: Request) -> Dict[str, Any]:
    try:
        result = _validate_covariate_contract(payload.covariate_schema, payload.payload, strict_order=payload.strict_order)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "data": {**result, "correlation": _corr(request)}}


@app.get(f"{API_PREFIX}/agent/tools")
def list_agent_tools(request: Request) -> Dict[str, Any]:
    tools = [
        {"name": "run_preprocessing", "description": "Trigger preprocessing pipeline run."},
        {"name": "run_training", "description": "Trigger training run."},
        {"name": "run_inference", "description": "Trigger inference run."},
        {"name": "get_run_status", "description": "Read current run/job status."},
    ]
    return {"ok": True, "data": {"tools": tools, "correlation": _corr(request)}}


@app.post(f"{API_PREFIX}/agent/tools:invoke")
def invoke_agent_tool(payload: AgentToolInvokeRequest, request: Request) -> Dict[str, Any]:
    _rate_limit_or_raise(key=f"agent:{request.client.host if request.client else 'local'}", limit=60, window_sec=60)
    idem_key = request.headers.get("x-idempotency-key")
    if idem_key:
        cached = _idempotency_get(f"agent:{idem_key}")
        if cached:
            return cached

    supported = {"run_preprocessing", "run_training", "run_inference", "get_run_status"}
    if payload.tool not in supported:
        raise HTTPException(status_code=400, detail="unsupported tool")

    response = {
        "ok": True,
        "data": {
            "tool": payload.tool,
            "accepted": True,
            "result": {
                "message": "tool accepted",
                "arguments": payload.arguments,
            },
            "correlation": _corr(request),
        },
    }

    if idem_key:
        _idempotency_put(f"agent:{idem_key}", response)
    return response


@app.get(f"{API_PREFIX}/mcp/capabilities")
def mcp_capabilities(request: Request) -> Dict[str, Any]:
    if not PHASE6_FLAGS["enable_mcp"]:
        raise HTTPException(status_code=503, detail="mcp disabled")
    return {
        "ok": True,
        "data": {
            "server": "spline-forecast-mcp",
            "version": "phase6.v1",
            "tools": [
                {"name": "run_preprocessing", "input_schema": {"type": "object", "properties": {"run_id": {"type": "string"}}}},
                {"name": "run_training", "input_schema": {"type": "object", "properties": {"run_id": {"type": "string"}}}},
                {"name": "run_inference", "input_schema": {"type": "object", "properties": {"run_id": {"type": "string"}}}},
                {"name": "get_run_status", "input_schema": {"type": "object", "properties": {"job_id": {"type": "string"}}}},
                {"name": "list_artifacts", "input_schema": {"type": "object", "properties": {"run_id": {"type": "string"}}}},
                {"name": "compare_runs", "input_schema": {"type": "object", "properties": {"base_run_id": {"type": "string"}, "candidate_run_id": {"type": "string"}}}},
            ],
            "correlation": _corr(request),
        },
    }


@app.get(f"{API_PREFIX}/pilot/readiness")
def pilot_readiness(request: Request) -> Dict[str, Any]:
    recent = store.list_recent(limit=20)
    total = len(recent)
    failures = len([x for x in recent if x.status in {"failed", "canceled"}])
    success = len([x for x in recent if x.status in {"succeeded", "success"}])
    rate = (failures / total) if total else 0.0
    stage = "shadow" if total < 5 else ("canary" if rate < 0.2 else "hold")
    return {
        "ok": True,
        "data": {
            "rollout_stage": stage,
            "recent_total": total,
            "recent_success": success,
            "recent_failures": failures,
            "failure_rate": round(rate, 4),
            "kill_switches": PHASE6_FLAGS,
            "correlation": _corr(request),
        },
    }


class TollamaGenerateRequest(BaseModel):
    model: str
    prompt: str
    stream: Optional[bool] = False


class TollamaChatRequest(BaseModel):
    model: str
    messages: List[Dict[str, Any]]
    stream: Optional[bool] = False


@app.get("/api/tags")
def tollama_tags() -> Dict[str, Any]:
    return {
        "models": [
            {
                "name": "spline-lstm:latest",
                "model": "spline-lstm",
                "modified_at": _utc_now_iso(),
                "size": 0,
                "digest": "sha256:spline-lstm-phase6",
                "details": {"family": "lstm", "format": "keras"},
            }
        ]
    }


@app.post("/api/generate")
def tollama_generate(payload: TollamaGenerateRequest):
    if not PHASE6_FLAGS["enable_tollama_adapter"]:
        raise HTTPException(status_code=503, detail="tollama adapter disabled")
    _rate_limit_or_raise(key="tollama:generate", limit=120, window_sec=60)
    response_text = (
        "[spline-lstm] Forecast assistant ready. "
        "Use /api/v1/forecast/preview for adjusted covariate what-if simulation. "
        f"Prompt echo: {payload.prompt[:120]}"
    )
    final = {
        "model": payload.model,
        "created_at": _utc_now_iso(),
        "response": response_text,
        "done": True,
    }
    if payload.stream:
        return _jsonl_stream([
            {"model": payload.model, "created_at": _utc_now_iso(), "response": response_text[:48], "done": False},
            final,
        ])
    return final


@app.post("/api/chat")
def tollama_chat(payload: TollamaChatRequest):
    if not PHASE6_FLAGS["enable_tollama_adapter"]:
        raise HTTPException(status_code=503, detail="tollama adapter disabled")
    _rate_limit_or_raise(key="tollama:chat", limit=120, window_sec=60)
    user_messages = [m.get("content", "") for m in payload.messages if m.get("role") == "user"]
    last_user = user_messages[-1] if user_messages else ""
    final = {
        "model": payload.model,
        "created_at": _utc_now_iso(),
        "message": {
            "role": "assistant",
            "content": f"[spline-lstm] received: {last_user[:120]}",
        },
        "done": True,
    }
    if payload.stream:
        return _jsonl_stream([
            {
                "model": payload.model,
                "created_at": _utc_now_iso(),
                "message": {"role": "assistant", "content": "[spline-lstm] thinking..."},
                "done": False,
            },
            final,
        ])
    return final


@app.get(f"{API_PREFIX}/runs/{{run_id}}/metrics")
def run_metrics(run_id: str) -> Dict[str, Any]:
    path = ARTIFACTS_DIR / "metrics" / f"{run_id}.json"
    payload = _read_json_if_exists(path)
    if payload is None:
        raise HTTPException(status_code=404, detail="run metrics not found")
    return {"ok": True, "data": payload}


@app.get(f"{API_PREFIX}/runs/{{run_id}}/artifacts")
def run_artifacts(run_id: str) -> Dict[str, Any]:
    path = ARTIFACTS_DIR / "metrics" / f"{run_id}.json"
    payload = _read_json_if_exists(path)
    if payload is None:
        raise HTTPException(status_code=404, detail="run artifacts not found")

    artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
    if "metrics_json" not in artifacts:
        artifacts["metrics_json"] = f"artifacts/metrics/{run_id}.json"
    if "report_md" not in artifacts:
        artifacts["report_md"] = f"artifacts/reports/{run_id}.md"

    return {"ok": True, "data": {"run_id": run_id, "artifacts": artifacts}}


@app.get(f"{API_PREFIX}/runs/{{run_id}}/report")
def run_report(run_id: str) -> JSONResponse:
    report_path = ARTIFACTS_DIR / "reports" / f"{run_id}.md"
    metrics_path = ARTIFACTS_DIR / "metrics" / f"{run_id}.json"

    md = report_path.read_text(encoding="utf-8") if report_path.exists() else None
    metrics_payload = _read_json_if_exists(metrics_path)

    if md is None and metrics_payload is None:
        raise HTTPException(status_code=404, detail="run report not found")

    data: Dict[str, Any] = {"run_id": run_id}
    if md is not None:
        data["report"] = md
    if metrics_payload and isinstance(metrics_payload.get("metrics"), dict):
        data["metrics"] = metrics_payload["metrics"]

    return JSONResponse(content={"ok": True, "data": data})
