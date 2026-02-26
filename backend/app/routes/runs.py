from __future__ import annotations

from typing import Any

from backend.app.config import API_PREFIX, ARTIFACTS_DIR
from backend.app.utils import read_json_if_exists
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get(f"{API_PREFIX}/runs/{{run_id}}/metrics")
def run_metrics(run_id: str) -> dict[str, Any]:
    path = ARTIFACTS_DIR / "metrics" / f"{run_id}.json"
    payload = read_json_if_exists(path)
    if payload is None:
        raise HTTPException(status_code=404, detail="run metrics not found")
    return {"ok": True, "data": payload}


@router.get(f"{API_PREFIX}/runs/{{run_id}}/artifacts")
def run_artifacts(run_id: str) -> dict[str, Any]:
    path = ARTIFACTS_DIR / "metrics" / f"{run_id}.json"
    payload = read_json_if_exists(path)
    if payload is None:
        raise HTTPException(status_code=404, detail="run artifacts not found")

    artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
    if "metrics_json" not in artifacts:
        artifacts["metrics_json"] = f"artifacts/metrics/{run_id}.json"
    if "report_md" not in artifacts:
        artifacts["report_md"] = f"artifacts/reports/{run_id}.md"

    return {"ok": True, "data": {"run_id": run_id, "artifacts": artifacts}}


@router.get(f"{API_PREFIX}/runs/{{run_id}}/report")
def run_report(run_id: str) -> JSONResponse:
    report_path = ARTIFACTS_DIR / "reports" / f"{run_id}.md"
    metrics_path = ARTIFACTS_DIR / "metrics" / f"{run_id}.json"

    md = report_path.read_text(encoding="utf-8") if report_path.exists() else None
    metrics_payload = read_json_if_exists(metrics_path)

    if md is None and metrics_payload is None:
        raise HTTPException(status_code=404, detail="run report not found")

    data: dict[str, Any] = {"run_id": run_id}
    if md is not None:
        data["report"] = md
    if metrics_payload and isinstance(metrics_payload.get("metrics"), dict):
        data["metrics"] = metrics_payload["metrics"]

    return JSONResponse(content={"ok": True, "data": data})
