#!/usr/bin/env python3
"""Phase 4 health check gate for run-scoped artifacts."""

from __future__ import annotations

import argparse
import json
import math
import pickle
import re
from pathlib import Path
from typing import Any


class HealthCheckError(RuntimeError):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


def _validate_run_id(run_id: str) -> None:
    if not isinstance(run_id, str) or not run_id.strip() or re.search(r"[\\/]", run_id):
        raise HealthCheckError(12, "invalid run_id (empty or contains path separator)")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as e:  # pragma: no cover
        raise HealthCheckError(30, f"json parse failed: {path}: {e}")
    if not isinstance(payload, dict):
        raise HealthCheckError(30, f"json object required: {path}")
    return payload


def _read_preprocessor_run_id(path: Path) -> str | None:
    try:
        with open(path, "rb") as f:
            payload = pickle.load(f)
    except Exception as e:
        raise HealthCheckError(30, f"preprocessor read failed: {path}: {e}")
    if not isinstance(payload, dict):
        raise HealthCheckError(30, f"preprocessor payload must be dict: {path}")
    rid = payload.get("run_id")
    if rid is None:
        raise HealthCheckError(30, "preprocessor payload missing run_id")
    if not isinstance(rid, str) or not rid.strip():
        raise HealthCheckError(30, "preprocessor payload run_id must be non-empty string")
    return rid


def run_health_check(run_id: str, artifacts_dir: str = "artifacts") -> dict[str, Any]:
    _validate_run_id(run_id)

    base = Path(artifacts_dir)
    if not base.exists() or not base.is_dir():
        raise HealthCheckError(30, f"artifacts dir missing: {base}")

    # writable probe
    probe = base / ".phase4_write_probe"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except Exception as e:
        raise HealthCheckError(30, f"artifacts dir not writable: {base}: {e}")

    processed = base / "processed" / run_id / "processed.npz"
    meta = base / "processed" / run_id / "meta.json"
    preprocessor = base / "models" / run_id / "preprocessor.pkl"
    best = base / "checkpoints" / run_id / "best.keras"
    last = base / "checkpoints" / run_id / "last.keras"
    metrics = base / "metrics" / f"{run_id}.json"
    report = base / "reports" / f"{run_id}.md"
    metadata = base / "metadata" / f"{run_id}.json"

    required = [processed, meta, preprocessor, best, last, metrics, report, metadata]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise HealthCheckError(30, f"required artifacts missing: {missing}")

    meta_obj = _read_json(meta)
    metrics_obj = _read_json(metrics)
    _read_json(metadata)

    for k in ("run_id", "metrics", "checkpoints"):
        if k not in metrics_obj:
            raise HealthCheckError(30, f"metrics missing key: {k}")

    metrics_run_id = metrics_obj.get("run_id")
    if metrics_run_id != run_id:
        raise HealthCheckError(27, f"run_id mismatch: metrics {metrics_run_id} != {run_id}")

    meta_run_id = meta_obj.get("run_id")
    if isinstance(meta_run_id, str) and meta_run_id != run_id:
        raise HealthCheckError(27, f"run_id mismatch: meta {meta_run_id} != {run_id}")

    preprocessor_run_id = _read_preprocessor_run_id(preprocessor)
    if preprocessor_run_id != run_id:
        raise HealthCheckError(27, f"run_id mismatch: preprocessor {preprocessor_run_id} != {run_id}")

    ckpt_best = str(metrics_obj.get("checkpoints", {}).get("best", ""))
    ckpt_last = str(metrics_obj.get("checkpoints", {}).get("last", ""))
    if run_id not in ckpt_best or run_id not in ckpt_last:
        raise HealthCheckError(27, "metrics checkpoints path does not include run_id")

    rmse = metrics_obj.get("metrics", {}).get("rmse")
    if rmse is None or not isinstance(rmse, (int, float)) or not math.isfinite(float(rmse)):
        raise HealthCheckError(30, "metrics.rmse must be a finite number")

    return {
        "status": "PASS",
        "code": 0,
        "run_id": run_id,
        "artifacts_dir": str(base),
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Phase 4 health check")
    p.add_argument("--run-id", required=True)
    p.add_argument("--artifacts-dir", default="artifacts")
    args = p.parse_args()

    try:
        out = run_health_check(run_id=args.run_id, artifacts_dir=args.artifacts_dir)
        print(json.dumps(out, ensure_ascii=False))
        raise SystemExit(0)
    except HealthCheckError as e:
        print(f"[HEALTH][FAIL][{e.code}] {e}")
        raise SystemExit(e.code)


if __name__ == "__main__":
    main()
