"""Edge benchmark harness for exported forecasting models."""

from __future__ import annotations

import argparse
import json
import logging
import resource
import time
from pathlib import Path
from typing import Any

import numpy as np

from src.training.edge import (
    compute_accuracy_score,
    compute_edge_score,
    compute_latency_score,
    compute_size_score,
    compute_stability_score,
    load_device_profiles,
    parse_edge_sla,
    run_keras_inference,
    run_onnx_inference,
    run_tflite_inference,
    select_runtime_stack,
    utc_now_iso,
)

logger = logging.getLogger(__name__)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_shape(shape: list[int]) -> list[int]:
    out: list[int] = []
    for dim in shape:
        if dim is None or int(dim) <= 0:
            out.append(1)
        else:
            out.append(int(dim))
    return out


def _dummy_inputs_from_specs(input_specs: list[dict[str, Any]]) -> list[np.ndarray]:
    if not input_specs:
        return [np.zeros((1, 24, 1), dtype=np.float32)]
    out: list[np.ndarray] = []
    for spec in input_specs:
        shape = _normalize_shape(list(spec.get("shape", [1, 24, 1])))
        out.append(np.zeros(shape, dtype=np.float32))
    return out


def _latency_stats(samples_ms: list[float]) -> tuple[float, float]:
    arr = np.asarray(samples_ms, dtype=np.float64)
    return float(np.percentile(arr, 50)), float(np.percentile(arr, 95))


def _runtime_infer(runtime: str, model_path: Path, sample_inputs: list[np.ndarray]) -> np.ndarray:
    if runtime == "tflite":
        return run_tflite_inference(model_path, sample_inputs)
    if runtime == "onnx":
        return run_onnx_inference(model_path, sample_inputs)
    if runtime == "keras":
        return run_keras_inference(model_path, sample_inputs)
    raise ValueError(f"unsupported runtime benchmark: {runtime}")


def _benchmark_runtime(
    *,
    runtime: str,
    model_path: Path,
    sample_inputs: list[np.ndarray],
    warmup: int,
    iterations: int,
) -> dict[str, Any]:
    failures = 0
    samples_ms: list[float] = []

    for _ in range(max(0, warmup)):
        try:
            _runtime_infer(runtime, model_path, sample_inputs)
        except Exception:
            failures += 1

    for _ in range(max(1, iterations)):
        t0 = time.perf_counter()
        try:
            _runtime_infer(runtime, model_path, sample_inputs)
        except Exception:
            failures += 1
            continue
        dt_ms = (time.perf_counter() - t0) * 1000.0
        samples_ms.append(dt_ms)

    if not samples_ms:
        return {
            "status": "failed",
            "failures": failures,
            "attempts": int(iterations),
            "latency_p50_ms": None,
            "latency_p95_ms": None,
        }

    p50, p95 = _latency_stats(samples_ms)
    return {
        "status": "succeeded",
        "failures": failures,
        "attempts": int(iterations),
        "latency_p50_ms": p50,
        "latency_p95_ms": p95,
    }


def _max_rss_mb() -> float:
    # Linux: KB, macOS: bytes. Use a conservative heuristic.
    rss = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if rss > 1024 * 1024 * 64:
        return rss / (1024.0 * 1024.0)
    return rss / 1024.0


def _size_mb(path: Path) -> float:
    return float(path.stat().st_size) / (1024.0 * 1024.0)


def _score_device(
    *,
    metrics_payload: dict[str, Any] | None,
    bench: dict[str, Any],
    model_size_mb: float,
    profile: dict[str, Any],
    sla: dict[str, Any],
) -> dict[str, Any]:
    model_rmse = None
    baseline_rmse = None
    if metrics_payload:
        model_rmse = float(metrics_payload.get("metrics", {}).get("rmse"))
        baseline_rmse = float(metrics_payload.get("baselines", {}).get("naive_last", {}).get("rmse"))

    acc = compute_accuracy_score(
        model_rmse, baseline_rmse, allowed_degradation_pct=float(sla["max_rmse_degradation_pct"])
    )
    lat = compute_latency_score(bench.get("latency_p95_ms"), target_ms=float(profile["latency_p95_target_ms"]))
    siz = compute_size_score(
        model_size_mb,
        target_mb=float(profile["size_target_mb"]),
        hard_limit_mb=float(profile["size_hard_limit_mb"]),
    )
    st = compute_stability_score(int(bench.get("failures", 0)), int(bench.get("attempts", 0)))

    edge_score = compute_edge_score(
        accuracy_score=acc,
        latency_score=lat,
        size_score=siz,
        stability_score=st,
        sla=sla,
    )
    return {
        "accuracy_score": acc,
        "latency_score": lat,
        "size_score": siz,
        "stability_score": st,
        "edge_score": edge_score,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    artifacts_dir = Path(args.artifacts_dir)
    run_id = args.run_id
    manifest_path = artifacts_dir / "exports" / run_id / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"export manifest not found: {manifest_path}")

    manifest = _load_json(manifest_path)
    metrics_path = artifacts_dir / "metrics" / f"{run_id}.json"
    metrics_payload = _load_json(metrics_path) if metrics_path.exists() else None

    profiles = load_device_profiles(args.device_benchmark_config)
    selected_devices = args.device or list(profiles.keys())
    edge_sla = parse_edge_sla(args.edge_sla)

    output_root = artifacts_dir / "edge_bench" / run_id
    output_root.mkdir(parents=True, exist_ok=True)

    runtime_compat = manifest.get("runtime_compatibility", {})
    input_specs = manifest.get("input_specs", [])
    sample_inputs = _dummy_inputs_from_specs(input_specs)

    results: list[dict[str, Any]] = []
    for device_name in selected_devices:
        profile = profiles.get(device_name)
        if profile is None:
            raise ValueError(f"unknown device profile: {device_name}")

        runtime_order = list(profile.get("runtime_order", ["tflite", "onnx", "keras"]))
        runtime_stack, fallback_chain = select_runtime_stack(runtime_compat, runtime_order)
        model_ref = runtime_compat.get(runtime_stack, {}).get("path")

        record: dict[str, Any] = {
            "run_id": run_id,
            "device_profile": device_name,
            "runtime_stack": runtime_stack,
            "fallback_chain": fallback_chain,
            "generated_at": utc_now_iso(),
            "sla": edge_sla,
            "profile": profile,
            "parity_error": manifest.get("parity", {}).get(runtime_stack),
        }

        if not model_ref:
            record.update(
                {
                    "status": "skipped",
                    "reason": "no exported runtime available",
                    "latency_p50_ms": None,
                    "latency_p95_ms": None,
                    "ram_peak_mb": _max_rss_mb(),
                    "size_mb": None,
                    "edge_score": 0.0,
                }
            )
        else:
            model_path = Path(model_ref)
            bench = _benchmark_runtime(
                runtime=runtime_stack,
                model_path=model_path,
                sample_inputs=sample_inputs,
                warmup=args.warmup,
                iterations=args.iterations,
            )
            size_mb = _size_mb(model_path) if model_path.exists() else None
            score = _score_device(
                metrics_payload=metrics_payload,
                bench=bench,
                model_size_mb=float(size_mb or 0.0),
                profile=profile,
                sla=edge_sla,
            )
            record.update(
                {
                    "status": bench["status"],
                    "latency_p50_ms": bench.get("latency_p50_ms"),
                    "latency_p95_ms": bench.get("latency_p95_ms"),
                    "ram_peak_mb": _max_rss_mb(),
                    "size_mb": size_mb,
                    "failures": bench.get("failures", 0),
                    "attempts": bench.get("attempts", 0),
                    **score,
                }
            )

        out_path = output_root / f"{device_name}.json"
        out_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        results.append(record)

    ranked = sorted(results, key=lambda x: float(x.get("edge_score", 0.0)), reverse=True)
    leaderboard = {
        "run_id": run_id,
        "generated_at": utc_now_iso(),
        "champion": ranked[0]["device_profile"] if ranked else None,
        "fallback": ranked[1]["device_profile"] if len(ranked) > 1 else None,
        "results": ranked,
    }
    (output_root / "leaderboard.json").write_text(
        json.dumps(leaderboard, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return leaderboard


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Benchmark exported edge models")
    p.add_argument("--run-id", type=str, required=True)
    p.add_argument("--artifacts-dir", type=str, default="artifacts")
    p.add_argument("--device", action="append", default=None, help="Device profile name. Repeatable.")
    p.add_argument("--iterations", type=int, default=200)
    p.add_argument("--warmup", type=int, default=30)
    p.add_argument(
        "--edge-sla",
        type=str,
        choices=["balanced", "accuracy_biased", "latency_biased"],
        default="balanced",
    )
    p.add_argument("--device-benchmark-config", type=str, default=None)
    return p


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    args = build_parser().parse_args()
    out = run(args)
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
