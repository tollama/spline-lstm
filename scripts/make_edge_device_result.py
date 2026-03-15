#!/usr/bin/env python3
"""Generate a real-device edge benchmark JSON payload.

This helper emits a schema-compatible JSON file for
`scripts/ingest_edge_device_bench.py`. It can either:

- build a payload from explicit CLI flags, or
- seed the payload from an existing edge benchmark report JSON and then apply
  CLI overrides.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return payload


def _parse_csv(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def _parse_float_csv(raw: str | None) -> list[float]:
    return [float(x) for x in _parse_csv(raw)]


def _optional_float(value: float | None) -> float | None:
    return None if value is None else float(value)


def _optional_int(value: int | None) -> int | None:
    return None if value is None else int(value)


def _seed_from_report(path: Path) -> dict[str, Any]:
    report = _read_json(path)
    seeded: dict[str, Any] = {}

    runtime_stack = report.get("runtime_stack")
    if isinstance(runtime_stack, str) and runtime_stack:
        seeded["runtime_stack"] = runtime_stack

    fallback_chain = report.get("fallback_chain")
    if isinstance(fallback_chain, list) and all(isinstance(x, str) and x for x in fallback_chain):
        seeded["fallback_chain"] = fallback_chain

    status = report.get("status")
    if isinstance(status, str) and status:
        seeded["status"] = status

    for src_key, dst_key in (
        ("latency_p50_ms", "latency_p50_ms"),
        ("latency_p95_ms", "latency_p95_ms"),
        ("size_mb", "size_mb"),
        ("ram_peak_mb", "memory_peak_mb"),
        ("attempts", "attempts"),
        ("failures", "failures"),
    ):
        value = report.get(src_key)
        if isinstance(value, (int, float)):
            seeded[dst_key] = value

    accuracy = report.get("accuracy")
    if isinstance(accuracy, dict):
        seeded["accuracy"] = {
            key: value
            for key, value in accuracy.items()
            if isinstance(value, (int, float, list))
        }

    return seeded


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if args.from_report_json:
        payload.update(_seed_from_report(Path(args.from_report_json)))

    if args.runtime_stack:
        payload["runtime_stack"] = args.runtime_stack

    fallback_chain = _parse_csv(args.fallback_chain)
    if fallback_chain:
        payload["fallback_chain"] = fallback_chain

    if args.status:
        payload["status"] = args.status

    latency_p50_ms = _optional_float(args.latency_p50_ms)
    latency_p95_ms = _optional_float(args.latency_p95_ms)
    if latency_p50_ms is not None and latency_p95_ms is not None:
        payload["latency_ms"] = {
            "p50": latency_p50_ms,
            "p95": latency_p95_ms,
        }
        payload.pop("latency_p50_ms", None)
        payload.pop("latency_p95_ms", None)
    else:
        if latency_p50_ms is not None:
            payload["latency_p50_ms"] = latency_p50_ms
        if latency_p95_ms is not None:
            payload["latency_p95_ms"] = latency_p95_ms

    if args.memory_peak_mb is not None:
        payload["memory_peak_mb"] = float(args.memory_peak_mb)
    if args.size_mb is not None:
        payload["size_mb"] = float(args.size_mb)
    if args.attempts is not None:
        payload["attempts"] = int(args.attempts)
    if args.failures is not None:
        payload["failures"] = int(args.failures)

    accuracy = payload.get("accuracy")
    accuracy_obj = dict(accuracy) if isinstance(accuracy, dict) else {}
    if args.accuracy_rmse is not None:
        accuracy_obj["rmse"] = float(args.accuracy_rmse)
    if args.accuracy_baseline_rmse is not None:
        accuracy_obj["baseline_rmse"] = float(args.accuracy_baseline_rmse)
    if args.accuracy_rmse_degradation_pct is not None:
        accuracy_obj["rmse_degradation_pct"] = float(args.accuracy_rmse_degradation_pct)
    if args.accuracy_mae is not None:
        accuracy_obj["mae"] = float(args.accuracy_mae)
    if args.accuracy_wape is not None:
        accuracy_obj["wape"] = float(args.accuracy_wape)
    if args.accuracy_max_abs_diff is not None:
        accuracy_obj["max_abs_diff"] = float(args.accuracy_max_abs_diff)
    if args.accuracy_n_samples is not None:
        accuracy_obj["n_samples"] = int(args.accuracy_n_samples)

    per_horizon_rmse = _parse_float_csv(args.per_horizon_rmse)
    if per_horizon_rmse:
        accuracy_obj["per_horizon_rmse"] = per_horizon_rmse

    model_rmse = accuracy_obj.get("rmse")
    baseline_rmse = accuracy_obj.get("baseline_rmse")
    if (
        "rmse_degradation_pct" not in accuracy_obj
        and isinstance(model_rmse, (int, float))
        and isinstance(baseline_rmse, (int, float))
        and float(baseline_rmse) > 0.0
    ):
        accuracy_obj["rmse_degradation_pct"] = float((float(model_rmse) - float(baseline_rmse)) / float(baseline_rmse) * 100.0)

    if accuracy_obj:
        payload["accuracy"] = accuracy_obj

    return payload


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Generate a schema-compatible device-result JSON payload for edge ingest",
        epilog=(
            "You can seed from an existing artifacts/edge_bench/<run_id>/<profile>.json using "
            "--from-report-json, then override fields such as memory_peak_mb or accuracy.*."
        ),
    )
    p.add_argument("--output", type=str, required=True, help="Output JSON path")
    p.add_argument("--from-report-json", type=str, default=None, help="Optional existing benchmark report to seed from")
    p.add_argument("--runtime-stack", type=str, choices=["tflite", "onnx", "keras"], default=None)
    p.add_argument("--fallback-chain", type=str, default=None, help="Comma-separated fallback chain, e.g. 'onnx,keras'")
    p.add_argument("--status", type=str, default="succeeded")
    p.add_argument("--latency-p50-ms", type=float, default=None)
    p.add_argument("--latency-p95-ms", type=float, default=None)
    p.add_argument("--memory-peak-mb", type=float, default=None)
    p.add_argument("--size-mb", type=float, default=None)
    p.add_argument("--attempts", type=int, default=200)
    p.add_argument("--failures", type=int, default=0)
    p.add_argument("--accuracy-rmse", type=float, default=None)
    p.add_argument("--accuracy-baseline-rmse", type=float, default=None)
    p.add_argument("--accuracy-rmse-degradation-pct", type=float, default=None)
    p.add_argument("--accuracy-mae", type=float, default=None)
    p.add_argument("--accuracy-wape", type=float, default=None)
    p.add_argument("--accuracy-max-abs-diff", type=float, default=None)
    p.add_argument("--accuracy-n-samples", type=int, default=None)
    p.add_argument(
        "--per-horizon-rmse",
        type=str,
        default=None,
        help="Comma-separated per-horizon RMSE list, e.g. '0.81,0.93,1.05'",
    )
    return p


def main() -> None:
    args = build_parser().parse_args()
    payload = build_payload(args)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
