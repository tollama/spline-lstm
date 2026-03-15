from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path
from typing import Any

from backend.app.config import API_PREFIX, ARTIFACTS_DIR, SECURITY
from backend.app.models import MobileBenchmarkBatchIngestRequest, MobileBenchmarkIngestRequest
from backend.app.utils import (
    atomic_write_text,
    corr,
    idempotency_get,
    idempotency_put,
    rate_limit_or_raise,
    read_json_if_exists,
    utc_now_iso,
    verify_hmac_sha256,
)
from fastapi import APIRouter, HTTPException, Query, Request

from scripts.validate_mobile_benchmark_result import validate_mobile_benchmark
from src.training.edge_device_ingest import run as run_device_ingest

router = APIRouter()


def _receipt_path(receipt_id: str) -> Path:
    return ARTIFACTS_DIR / "mobile_receipts" / f"{receipt_id}.json"


def _persist_receipt(payload: dict[str, Any]) -> Path:
    receipt_id = str(payload["receipt_id"])
    path = _receipt_path(receipt_id)
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))
    return path


async def _require_mobile_signature(request: Request) -> None:
    if not SECURITY.get("mobile_upload_signing_required"):
        return

    timestamp = request.headers.get("x-mobile-timestamp")
    signature = request.headers.get("x-mobile-signature")
    if not timestamp or not signature:
        raise HTTPException(status_code=401, detail="mobile upload signature required")

    try:
        timestamp_int = int(timestamp)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="invalid mobile upload timestamp") from exc

    now = int(time.time())
    skew = int(SECURITY.get("mobile_upload_timestamp_skew_sec", 300))
    if abs(now - timestamp_int) > skew:
        raise HTTPException(status_code=401, detail="mobile upload timestamp expired")

    body = (await request.body()).decode("utf-8")
    message = f"{timestamp}\n{body}"
    secret = str(SECURITY["mobile_upload_signing_secret"])
    if not verify_hmac_sha256(secret, message, signature):
        raise HTTPException(status_code=401, detail="invalid mobile upload signature")


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
async def ingest_mobile_benchmark(payload: MobileBenchmarkIngestRequest, request: Request) -> dict[str, Any]:
    await _require_mobile_signature(request)
    rate_limit_or_raise(key=f"mobile:{request.client.host if request.client else 'local'}", limit=120, window_sec=60)
    idem_key = request.headers.get("x-idempotency-key")
    if idem_key:
        cached = idempotency_get(f"mobile:{idem_key}")
        if cached:
            return cached

    item = _ingest_one(payload=payload, request=request)
    receipt_id = f"mobile-receipt-{uuid.uuid4().hex[:16]}"
    receipt = {
        "receipt_id": receipt_id,
        "received_at": utc_now_iso(),
        "kind": "mobile_benchmark_ingest",
        "run_id": payload.run_id,
        "device_profile": payload.device_profile,
        "source_path": item["source_path"],
        "status": "succeeded",
        "request_id": request.state.request_id,
        "record_path": str(ARTIFACTS_DIR / "edge_bench" / payload.run_id / f"{payload.device_profile}.json"),
    }
    receipt_path = _persist_receipt(receipt)
    item["receipt"] = {"receipt_id": receipt_id, "receipt_path": str(receipt_path)}
    response = {"ok": True, "data": item}
    if idem_key:
        idempotency_put(f"mobile:{idem_key}", response)
    return response


@router.post(f"{API_PREFIX}/mobile/benchmarks:ingest-batch")
async def ingest_mobile_benchmark_batch(payload: MobileBenchmarkBatchIngestRequest, request: Request) -> dict[str, Any]:
    await _require_mobile_signature(request)
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
    receipts: list[dict[str, Any]] = []
    for idx, item in enumerate(uploads):
        ingested = _ingest_one(payload=item, request=request, request_suffix=f"{request.state.request_id}-{idx}")
        receipt_id = f"mobile-receipt-{uuid.uuid4().hex[:16]}"
        receipt = {
            "receipt_id": receipt_id,
            "received_at": utc_now_iso(),
            "kind": "mobile_benchmark_ingest",
            "run_id": item.run_id,
            "device_profile": item.device_profile,
            "source_path": ingested["source_path"],
            "status": "succeeded",
            "request_id": request.state.request_id,
            "record_path": str(ARTIFACTS_DIR / "edge_bench" / item.run_id / f"{item.device_profile}.json"),
        }
        receipt_path = _persist_receipt(receipt)
        ingested["receipt"] = {"receipt_id": receipt_id, "receipt_path": str(receipt_path)}
        receipts.append({"receipt_id": receipt_id, "receipt_path": str(receipt_path)})
        items.append(ingested)

    response = {
        "ok": True,
        "data": {
            "count": len(items),
            "items": items,
            "receipts": receipts,
            "correlation": corr(request),
        },
    }
    if idem_key:
        idempotency_put(f"mobile-batch:{idem_key}", response)
    return response


@router.get(f"{API_PREFIX}/mobile/benchmarks/receipts/{{receipt_id}}")
def get_mobile_benchmark_receipt(receipt_id: str, request: Request) -> dict[str, Any]:
    path = _receipt_path(receipt_id)
    payload = read_json_if_exists(path)
    if payload is None:
        raise HTTPException(status_code=404, detail="mobile receipt not found")
    return {"ok": True, "data": {**payload, "correlation": corr(request, run_id=payload.get("run_id"))}}


@router.get(f"{API_PREFIX}/mobile/benchmarks/receipts")
def list_mobile_benchmark_receipts(
    request: Request,
    run_id: str | None = Query(default=None),
    device_profile: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
) -> dict[str, Any]:
    root = ARTIFACTS_DIR / "mobile_receipts"
    rows: list[dict[str, Any]] = []
    if root.exists():
        for path in sorted(root.glob("*.json"), reverse=True):
            payload = read_json_if_exists(path)
            if not isinstance(payload, dict):
                continue
            if run_id and payload.get("run_id") != run_id:
                continue
            if device_profile and payload.get("device_profile") != device_profile:
                continue
            rows.append(payload)
            if len(rows) >= limit:
                break
    return {"ok": True, "data": {"items": rows, "count": len(rows), "correlation": corr(request, run_id=run_id)}}
