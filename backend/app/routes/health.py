from __future__ import annotations

from typing import Any

from backend.app.config import API_PREFIX, ARTIFACTS_DIR, PHASE6_FLAGS, SECURITY, STORE_PATH
from backend.app.utils import corr, ensure_parent, utc_now_iso
from fastapi import APIRouter, Request

router = APIRouter()


@router.get(f"{API_PREFIX}/health")
def health(request: Request) -> dict[str, Any]:
    store = request.app.state.store
    executor = request.app.state.executor

    writable = False
    try:
        ensure_parent(STORE_PATH)
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
            "ts": utc_now_iso(),
            "executor_mode": executor._mode(),
            "security": {"dev_mode": SECURITY["dev_mode"], "auth_required": SECURITY["auth_required"]},
            "details": {
                "store": store.diagnostics(),
                "artifacts_dir": str(ARTIFACTS_DIR),
                "store_dir_writable": writable,
            },
        },
    }


@router.get(f"{API_PREFIX}/dashboard/summary")
def dashboard_summary(request: Request) -> dict[str, Any]:
    store = request.app.state.store
    from backend.app.routes.jobs import to_job_payload

    jobs = [to_job_payload(job, request=request) for job in store.list_recent(limit=10)]
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
            "correlation": corr(request),
        },
    }


@router.get(f"{API_PREFIX}/pilot/readiness")
def pilot_readiness(request: Request) -> dict[str, Any]:
    store = request.app.state.store

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
            "correlation": corr(request),
        },
    }
