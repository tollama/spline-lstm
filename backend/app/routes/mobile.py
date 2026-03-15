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


def _new_receipt(
    *,
    run_id: str,
    device_profile: str,
    source_path: str,
    request_id: str,
    status: str,
    record_path: str | None = None,
    validation: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "receipt_id": f"mobile-receipt-{uuid.uuid4().hex[:16]}",
        "received_at": utc_now_iso(),
        "kind": "mobile_benchmark_ingest",
        "run_id": run_id,
        "device_profile": device_profile,
        "source_path": source_path,
        "status": status,
        "request_id": request_id,
    }
    if record_path:
        receipt["record_path"] = record_path
    if validation:
        receipt["validation"] = validation
    if error:
        receipt["error"] = error
    return receipt


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


def _load_record_from_receipt(receipt: dict[str, Any]) -> dict[str, Any] | None:
    record_path = receipt.get("record_path")
    if isinstance(record_path, str):
        payload = read_json_if_exists(Path(record_path))
        if payload is not None:
            return payload

    run_id = receipt.get("run_id")
    device_profile = receipt.get("device_profile")
    if not isinstance(run_id, str) or not isinstance(device_profile, str):
        return None
    fallback = ARTIFACTS_DIR / "edge_bench" / run_id / f"{device_profile}.json"
    return read_json_if_exists(fallback)


def _iter_mobile_receipts() -> list[dict[str, Any]]:
    root = ARTIFACTS_DIR / "mobile_receipts"
    rows: list[dict[str, Any]] = []
    if not root.exists():
        return rows
    for path in root.glob("*.json"):
        payload = read_json_if_exists(path)
        if isinstance(payload, dict):
            rows.append(payload)
    rows.sort(key=lambda item: str(item.get("received_at", "")), reverse=True)
    return rows


def build_mobile_benchmark_summary(
    *,
    run_id: str | None = None,
    device_profile: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    receipts = [
        receipt
        for receipt in _iter_mobile_receipts()
        if (run_id is None or receipt.get("run_id") == run_id)
        and (device_profile is None or receipt.get("device_profile") == device_profile)
    ]

    status_counts: dict[str, int] = {}
    runtime_counts: dict[str, int] = {}
    platform_counts: dict[str, int] = {}
    profile_counts: dict[str, int] = {}
    unique_runs: set[str] = set()
    recent_uploads: list[dict[str, Any]] = []

    latency_values: list[float] = []
    memory_values: list[float] = []
    size_values: list[float] = []
    rmse_values: list[float] = []
    baseline_rmse_values: list[float] = []

    for receipt in receipts:
        status = str(receipt.get("status", "unknown"))
        status_counts[status] = status_counts.get(status, 0) + 1

        receipt_run_id = receipt.get("run_id")
        if isinstance(receipt_run_id, str):
            unique_runs.add(receipt_run_id)

        profile = receipt.get("device_profile")
        if isinstance(profile, str):
            profile_counts[profile] = profile_counts.get(profile, 0) + 1

        record = _load_record_from_receipt(receipt)
        metadata = record.get("metadata", {}) if isinstance(record, dict) else {}
        runtime_stack = record.get("runtime_stack") if isinstance(record, dict) else None
        platform = metadata.get("platform") if isinstance(metadata, dict) else None
        accuracy = record.get("accuracy", {}) if isinstance(record, dict) else {}
        latency = record.get("latency_ms", {}) if isinstance(record, dict) else {}

        if isinstance(runtime_stack, str):
            runtime_counts[runtime_stack] = runtime_counts.get(runtime_stack, 0) + 1
        if isinstance(platform, str):
            platform_counts[platform] = platform_counts.get(platform, 0) + 1

        if isinstance(latency, dict):
            p95 = latency.get("p95")
            if isinstance(p95, (int, float)):
                latency_values.append(float(p95))
        if isinstance(record, dict):
            memory_peak = record.get("memory_peak_mb")
            if isinstance(memory_peak, (int, float)):
                memory_values.append(float(memory_peak))
            size_mb = record.get("size_mb")
            if isinstance(size_mb, (int, float)):
                size_values.append(float(size_mb))
        if isinstance(accuracy, dict):
            rmse = accuracy.get("rmse")
            if isinstance(rmse, (int, float)):
                rmse_values.append(float(rmse))
            baseline_rmse = accuracy.get("baseline_rmse")
            if isinstance(baseline_rmse, (int, float)):
                baseline_rmse_values.append(float(baseline_rmse))

        if len(recent_uploads) < limit:
            recent_uploads.append(
                {
                    "receipt_id": receipt.get("receipt_id"),
                    "received_at": receipt.get("received_at"),
                    "run_id": receipt.get("run_id"),
                    "device_profile": receipt.get("device_profile"),
                    "status": status,
                    "platform": platform,
                    "runtime_stack": runtime_stack,
                    "latency_p95_ms": latency.get("p95") if isinstance(latency, dict) else None,
                    "rmse": accuracy.get("rmse") if isinstance(accuracy, dict) else None,
                }
            )

    success_count = sum(count for key, count in status_counts.items() if key == "succeeded")
    total = len(receipts)
    success_rate = (success_count / total) if total else None

    def _mean(values: list[float]) -> float | None:
        if not values:
            return None
        return round(sum(values) / len(values), 4)

    return {
        "total_receipts": total,
        "successful_receipts": success_count,
        "failed_receipts": total - success_count,
        "success_rate": round(success_rate, 4) if success_rate is not None else None,
        "unique_runs": len(unique_runs),
        "latest_received_at": receipts[0].get("received_at") if receipts else None,
        "status_counts": status_counts,
        "platform_counts": platform_counts,
        "runtime_stack_counts": runtime_counts,
        "device_profile_counts": profile_counts,
        "averages": {
            "latency_p95_ms": _mean(latency_values),
            "memory_peak_mb": _mean(memory_values),
            "size_mb": _mean(size_values),
            "rmse": _mean(rmse_values),
            "baseline_rmse": _mean(baseline_rmse_values),
        },
        "recent_uploads": recent_uploads,
    }


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
        receipt = _new_receipt(
            run_id=payload.run_id,
            device_profile=payload.device_profile,
            source_path=str(source_path),
            request_id=request.state.request_id,
            status="validation_failed",
            validation=validation,
            error={"message": "invalid mobile benchmark payload"},
        )
        receipt_path = _persist_receipt(receipt)
        raise HTTPException(
            status_code=400,
            detail={
                "message": "invalid mobile benchmark payload",
                **validation,
                "receipt": {
                    "receipt_id": receipt["receipt_id"],
                    "receipt_path": str(receipt_path),
                },
            },
        )

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
    receipt = _new_receipt(
        run_id=payload.run_id,
        device_profile=payload.device_profile,
        source_path=item["source_path"],
        request_id=request.state.request_id,
        status="succeeded",
        record_path=str(ARTIFACTS_DIR / "edge_bench" / payload.run_id / f"{payload.device_profile}.json"),
        validation=item["validation"],
    )
    receipt_path = _persist_receipt(receipt)
    item["receipt"] = {"receipt_id": receipt["receipt_id"], "receipt_path": str(receipt_path)}
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
        receipt = _new_receipt(
            run_id=item.run_id,
            device_profile=item.device_profile,
            source_path=ingested["source_path"],
            request_id=request.state.request_id,
            status="succeeded",
            record_path=str(ARTIFACTS_DIR / "edge_bench" / item.run_id / f"{item.device_profile}.json"),
            validation=ingested["validation"],
        )
        receipt_path = _persist_receipt(receipt)
        ingested["receipt"] = {"receipt_id": receipt["receipt_id"], "receipt_path": str(receipt_path)}
        receipts.append({"receipt_id": receipt["receipt_id"], "receipt_path": str(receipt_path)})
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
    rows = []
    for payload in _iter_mobile_receipts():
        if run_id and payload.get("run_id") != run_id:
            continue
        if device_profile and payload.get("device_profile") != device_profile:
            continue
        rows.append(payload)
        if len(rows) >= limit:
            break
    return {"ok": True, "data": {"items": rows, "count": len(rows), "correlation": corr(request, run_id=run_id)}}


@router.get(f"{API_PREFIX}/mobile/benchmarks/summary")
def mobile_benchmark_summary(
    request: Request,
    run_id: str | None = Query(default=None),
    device_profile: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=100),
) -> dict[str, Any]:
    return {
        "ok": True,
        "data": {
            **build_mobile_benchmark_summary(run_id=run_id, device_profile=device_profile, limit=limit),
            "correlation": corr(request, run_id=run_id),
        },
    }
