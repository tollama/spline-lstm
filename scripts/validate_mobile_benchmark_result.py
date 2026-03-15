#!/usr/bin/env python3
"""Validate an Android/iOS benchmark result payload before ingest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return payload


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_runtime(payload: dict[str, Any]) -> str | None:
    runtime = payload.get("runtime_stack", payload.get("runtime"))
    if not isinstance(runtime, str) or not runtime.strip():
        return None
    return runtime.strip()


def _extract_latency(payload: dict[str, Any]) -> tuple[float | None, float | None]:
    p50 = _as_float(payload.get("latency_p50_ms"))
    p95 = _as_float(payload.get("latency_p95_ms"))
    if p50 is not None and p95 is not None:
        return p50, p95

    latency = payload.get("latency_ms")
    if isinstance(latency, dict):
        p50 = _as_float(latency.get("p50"))
        p95 = _as_float(latency.get("p95"))
        if p50 is not None and p95 is not None:
            return p50, p95

    samples = payload.get("latency_ms_samples", payload.get("latency_samples_ms"))
    if isinstance(samples, list) and samples:
        numeric = [_as_float(x) for x in samples]
        numeric = [x for x in numeric if x is not None]
        if numeric:
            numeric = sorted(numeric)
            n = len(numeric)
            p50 = numeric[min(n - 1, int(round((n - 1) * 0.50)))]
            p95 = numeric[min(n - 1, int(round((n - 1) * 0.95)))]
            return p50, p95

    return None, None


def _extract_size_mb(payload: dict[str, Any]) -> float | None:
    size_mb = _as_float(payload.get("size_mb", payload.get("model_size_mb")))
    if size_mb is not None:
        return size_mb
    size_bytes = _as_float(payload.get("size_bytes", payload.get("model_size_bytes")))
    if size_bytes is None:
        return None
    return float(size_bytes / (1024.0 * 1024.0))


def _extract_memory_mb(payload: dict[str, Any]) -> float | None:
    memory_mb = _as_float(payload.get("memory_peak_mb", payload.get("ram_peak_mb")))
    if memory_mb is not None:
        return memory_mb
    memory_bytes = _as_float(payload.get("memory_peak_bytes", payload.get("ram_peak_bytes")))
    if memory_bytes is None:
        return None
    return float(memory_bytes / (1024.0 * 1024.0))


def _preferred_runtime(platform: str) -> str:
    return "tflite" if platform == "android" else "onnx"


def validate_mobile_benchmark(
    benchmark_result_path: Path,
    *,
    expected_platform: str | None,
    require_metadata: bool,
    require_accuracy: bool,
    strict_runtime_policy: bool,
) -> dict[str, Any]:
    payload = _load_json(benchmark_result_path)
    errors: list[str] = []
    warnings: list[str] = []

    runtime = _extract_runtime(payload)
    if runtime not in {"tflite", "onnx", "keras"}:
        errors.append("runtime_stack/runtime must be one of: tflite, onnx, keras")

    p50, p95 = _extract_latency(payload)
    if p95 is None:
        errors.append("latency p95 is required")
    elif p50 is not None and p95 < p50:
        errors.append("latency p95 must be >= p50")

    size_mb = _extract_size_mb(payload)
    if size_mb is None or size_mb <= 0:
        errors.append("size_mb or size_bytes must be a positive value")

    memory_mb = _extract_memory_mb(payload)
    if memory_mb is None or memory_mb <= 0:
        errors.append("memory_peak_mb or memory_peak_bytes must be a positive value")

    attempts = _as_int(payload.get("attempts", payload.get("runs")))
    failures = _as_int(payload.get("failures", payload.get("failure_count")))
    if attempts is None or attempts <= 0:
        errors.append("attempts/runs must be a positive integer")
    if failures is None or failures < 0:
        errors.append("failures/failure_count must be a non-negative integer")
    elif attempts is not None and failures > attempts:
        errors.append("failures cannot exceed attempts")

    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        if require_metadata:
            errors.append("metadata block is required for mobile benchmark payloads")
        metadata = {}

    platform = metadata.get("platform")
    if require_metadata or platform is not None:
        if platform not in {"android", "ios"}:
            errors.append("metadata.platform must be 'android' or 'ios'")
        for key in ("device_model", "os_version", "app_version", "build_number", "bundle_id"):
            value = metadata.get(key)
            if require_metadata and (not isinstance(value, str) or not value.strip()):
                errors.append(f"metadata.{key} must be a non-empty string")

    if expected_platform and platform and platform != expected_platform:
        errors.append(f"metadata.platform='{platform}' does not match expected platform '{expected_platform}'")

    if platform in {"android", "ios"} and runtime in {"tflite", "onnx", "keras"}:
        preferred = _preferred_runtime(platform)
        if runtime != preferred:
            message = f"{platform} benchmark uses runtime '{runtime}' instead of preferred '{preferred}'"
            if strict_runtime_policy:
                errors.append(message)
            else:
                warnings.append(message)

    fallback_chain = payload.get("fallback_chain")
    if fallback_chain is not None and (
        not isinstance(fallback_chain, list) or not fallback_chain or not all(isinstance(x, str) and x for x in fallback_chain)
    ):
        errors.append("fallback_chain must be a non-empty string list when present")

    accuracy = payload.get("accuracy")
    if not isinstance(accuracy, dict):
        if require_accuracy:
            errors.append("accuracy block is required")
    else:
        rmse = _as_float(accuracy.get("rmse"))
        baseline_rmse = _as_float(accuracy.get("baseline_rmse"))
        if rmse is None or rmse < 0:
            errors.append("accuracy.rmse must be a non-negative number")
        if baseline_rmse is None or baseline_rmse <= 0:
            errors.append("accuracy.baseline_rmse must be a positive number")
        per_horizon = accuracy.get("per_horizon_rmse")
        if per_horizon is not None and (
            not isinstance(per_horizon, list) or any(_as_float(x) is None or _as_float(x) < 0 for x in per_horizon)
        ):
            errors.append("accuracy.per_horizon_rmse must be a numeric list when present")

    return {
        "benchmark_result_path": str(benchmark_result_path),
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Validate an Android/iOS benchmark result payload before ingest")
    p.add_argument("--benchmark-result", type=str, required=True)
    p.add_argument("--expected-platform", type=str, choices=["android", "ios"], default=None)
    p.add_argument("--no-require-metadata", action="store_true", default=False)
    p.add_argument("--no-require-accuracy", action="store_true", default=False)
    p.add_argument("--strict-runtime-policy", action="store_true", default=False)
    return p


def main() -> None:
    args = build_parser().parse_args()
    report = validate_mobile_benchmark(
        Path(args.benchmark_result),
        expected_platform=args.expected_platform,
        require_metadata=not args.no_require_metadata,
        require_accuracy=not args.no_require_accuracy,
        strict_runtime_policy=bool(args.strict_runtime_policy),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
