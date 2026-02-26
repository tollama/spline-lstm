from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from backend.app.config import API_PREFIX, ARTIFACTS_DIR, ROOT_DIR
from backend.app.models import RunRequest
from backend.app.store import JobRecord
from backend.app.utils import atomic_write_text, corr, utc_now_iso
from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter()


def compute_status(rec: JobRecord) -> JobRecord:
    if rec.execution_mode == "real":
        return rec

    if rec.canceled:
        rec.status = "canceled"
        rec.step = "canceled"
        rec.progress = 100
        rec.error_message = (
            rec.error_message
            or "\uc0ac\uc6a9\uc790 \uc694\uccad\uc73c\ub85c \uc791\uc5c5\uc774 \ucde8\uc18c\ub418\uc5c8\uc2b5\ub2c8\ub2e4."
        )
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
        ensure_mock_run_artifacts(rec)
    return rec


def ensure_mock_run_artifacts(rec: JobRecord) -> None:
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
        atomic_write_text(metrics_path, json.dumps(payload, ensure_ascii=False, indent=2))

    report_path = reports_dir / f"{rec.run_id}.md"
    if not report_path.exists():
        atomic_write_text(
            report_path,
            f"# Run Report\n\n- run_id: {rec.run_id}\n- model: {rec.model_type}\n- feature_mode: {rec.feature_mode}\n",
        )

    runmeta_path = runmeta_dir / f"{rec.run_id}.meta.json"
    if not runmeta_path.exists():
        atomic_write_text(
            runmeta_path,
            json.dumps(
                {"run_id": rec.run_id, "job_id": rec.job_id, "status": rec.status}, ensure_ascii=False, indent=2
            ),
        )


def to_job_payload(rec: JobRecord, request: Request | None = None) -> dict[str, Any]:
    from backend.app.main import store

    cur = compute_status(rec)
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
        "correlation": corr(request, job_id=cur.job_id, run_id=cur.run_id),
    }


@router.get(f"{API_PREFIX}/jobs")
def list_jobs(request: Request, limit: int = Query(default=10, ge=1, le=100)) -> dict[str, Any]:
    from backend.app.main import store

    jobs = [to_job_payload(job, request=request) for job in store.list_recent(limit=limit)]
    return {"ok": True, "data": {"jobs": jobs, "correlation": corr(request)}}


@router.post(f"{API_PREFIX}/pipelines/spline-tsfm:run")
def run_pipeline(payload: RunRequest, request: Request) -> dict[str, Any]:
    from backend.app.main import executor, store

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
            "correlation": corr(request, job_id=rec.job_id, run_id=rec.run_id),
        },
    }


@router.get(f"{API_PREFIX}/jobs/{{job_id}}")
def get_job(job_id: str, request: Request) -> dict[str, Any]:
    from backend.app.main import store

    rec = store.get(job_id)
    if not rec:
        raise HTTPException(status_code=404, detail="job not found")
    return {"ok": True, "data": to_job_payload(rec, request=request)}


@router.post(f"{API_PREFIX}/jobs/{{job_id}}:cancel")
def cancel_job(job_id: str, request: Request) -> dict[str, Any]:
    from backend.app.main import executor, store

    rec = store.get(job_id)
    if not rec:
        raise HTTPException(status_code=404, detail="job not found")
    rec.canceled = True
    rec.status = "canceled"
    rec.step = "canceled"
    rec.progress = 100
    rec.error_message = (
        "\uc0ac\uc6a9\uc790 \uc694\uccad\uc73c\ub85c \uc791\uc5c5\uc774 \ucde8\uc18c\ub418\uc5c8\uc2b5\ub2c8\ub2e4."
    )
    rec.message = "cancel accepted"
    store.upsert(rec)
    executor.cancel(job_id)
    return {"ok": True, "data": to_job_payload(rec, request=request)}


@router.get(f"{API_PREFIX}/jobs/{{job_id}}/logs")
def get_logs(
    job_id: str, request: Request, offset: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=1000)
) -> dict[str, Any]:
    from backend.app.main import executor, store

    rec = store.get(job_id)
    if not rec:
        raise HTTPException(status_code=404, detail="job not found")

    corr_data = corr(request, job_id=job_id, run_id=rec.run_id)
    runtime_lines = executor.logs(job_id, offset, limit)
    if runtime_lines:
        enriched = [{**line, **corr_data} for line in runtime_lines]
        return {"ok": True, "data": {"job_id": job_id, "lines": enriched, "correlation": corr_data}}

    cur = compute_status(rec)
    base = datetime.fromtimestamp(rec.created_at, tz=timezone.utc)
    lines: list[dict[str, Any]] = [
        {"ts": base.isoformat(), "level": "INFO", "source": "mock", "message": "job accepted", **corr_data},
        {
            "ts": (base.replace(microsecond=0)).isoformat(),
            "level": "INFO",
            "source": "mock",
            "message": "preprocessing",
            **corr_data,
        },
        {"ts": utc_now_iso(), "level": "INFO", "source": "mock", "message": f"status={cur.status}", **corr_data},
    ]
    sliced = lines[offset : offset + limit]
    return {"ok": True, "data": {"job_id": job_id, "lines": sliced, "correlation": corr_data}}
