from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from backend.app.config import API_PREFIX, ARTIFACTS_DIR
from backend.app.models import MobileBenchmarkBatchIngestRequest, MobileBenchmarkIngestRequest
from backend.app.utils import atomic_write_text, corr, idempotency_get, idempotency_put, rate_limit_or_raise
from fastapi import APIRouter, HTTPException, Request

from scripts.validate_mobile_benchmark_result import validate_mobile_benchmark
from src.training.edge_device_ingest import run as run_device_ingest

router = APIRouter()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return payload


def _select_record(leaderboard: dict[str, Any], device_profile: str) -> dict[str, Any] | None:
    rows = leaderboard.get("results")
    if not isinstance(rows, list):
        return None
    for row in rows:
        if isinstance(row, dict) and row.get("device_profile") == device_profile:
            return row
    return None


def _ingest_one(
    *,
    payload: MobileBenchmarkIngestRequest,
    request: Request,
    request_suffix: str | None = None,
) -> dict[str, Any]:
    upload_dir = ARTIFACTS_DIR / "mobile_uploads" / payload.run_id
    suffix = request_suffix or request.state.request_id
    source_path = upload_dir / f"{payload.device_profile}-{suffix}.json"
    atomic_write_text(source_path, json.dumps(payload.benchmark_result, ensure_ascii=False, indent=2))

    validation = validate_mobile_benchmark(
        source_path,
        expected_platform=payload.expected_platform,
        require_metadata=payload.require_metadata,
        require_accuracy=payload.require_accuracy,
        strict_runtime_policy=payload.strict_runtime_policy,
    )
    if not validation["ok"]:
        raise HTTPException(status_code=400, detail={"message": "invalid mobile benchmark payload", **validation})

    ingest_args = argparse.Namespace(
        run_id=payload.run_id,
        artifacts_dir=str(ARTIFACTS_DIR),
        device_result=[f"{payload.device_profile}={source_path}"],
        device_results_dir=None,
        edge_sla="balanced",
        device_benchmark_config=None,
        metrics_json=None,
        merge_existing=True,
    )
    leaderboard = run_device_ingest(ingest_args)
    record = _select_record(leaderboard, payload.device_profile)
    if record is None:
        record_path = ARTIFACTS_DIR / "edge_bench" / payload.run_id / f"{payload.device_profile}.json"
        if record_path.exists():
            record = _load_json(record_path)
        else:
            raise HTTPException(status_code=500, detail="ingested benchmark record missing after ingest")

    return {
        "run_id": payload.run_id,
        "device_profile": payload.device_profile,
        "source_path": str(source_path),
        "validation": validation,
        "record": record,
        "leaderboard": {
            "champion": leaderboard.get("champion"),
            "fallback": leaderboard.get("fallback"),
        },
        "correlation": corr(request, run_id=payload.run_id),
    }


@router.post(f"{API_PREFIX}/mobile/benchmarks:ingest")
def ingest_mobile_benchmark(payload: MobileBenchmarkIngestRequest, request: Request) -> dict[str, Any]:
    rate_limit_or_raise(key=f"mobile:{request.client.host if request.client else 'local'}", limit=120, window_sec=60)
    idem_key = request.headers.get("x-idempotency-key")
    if idem_key:
        cached = idempotency_get(f"mobile:{idem_key}")
        if cached:
            return cached

    response = {"ok": True, "data": _ingest_one(payload=payload, request=request)}
    if idem_key:
        idempotency_put(f"mobile:{idem_key}", response)
    return response


@router.post(f"{API_PREFIX}/mobile/benchmarks:ingest-batch")
def ingest_mobile_benchmark_batch(payload: MobileBenchmarkBatchIngestRequest, request: Request) -> dict[str, Any]:
    rate_limit_or_raise(key=f"mobile-batch:{request.client.host if request.client else 'local'}", limit=30, window_sec=60)
    idem_key = request.headers.get("x-idempotency-key")
    if idem_key:
        cached = idempotency_get(f"mobile-batch:{idem_key}")
        if cached:
            return cached

    uploads = payload.uploads
    if not uploads:
        raise HTTPException(status_code=400, detail="uploads must not be empty")

    items: list[dict[str, Any]] = []
    for idx, item in enumerate(uploads):
        items.append(_ingest_one(payload=item, request=request, request_suffix=f"{request.state.request_id}-{idx}"))

    response = {
        "ok": True,
        "data": {
            "count": len(items),
            "items": items,
            "correlation": corr(request),
        },
    }
    if idem_key:
        idempotency_put(f"mobile-batch:{idem_key}", response)
    return response
