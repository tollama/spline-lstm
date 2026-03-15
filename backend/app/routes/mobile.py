from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from backend.app.config import API_PREFIX, ARTIFACTS_DIR
from backend.app.models import MobileBenchmarkIngestRequest
from backend.app.utils import atomic_write_text, corr
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


@router.post(f"{API_PREFIX}/mobile/benchmarks:ingest")
def ingest_mobile_benchmark(payload: MobileBenchmarkIngestRequest, request: Request) -> dict[str, Any]:
    upload_dir = ARTIFACTS_DIR / "mobile_uploads" / payload.run_id
    source_path = upload_dir / f"{payload.device_profile}-{request.state.request_id}.json"
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
        "ok": True,
        "data": {
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
        },
    }
