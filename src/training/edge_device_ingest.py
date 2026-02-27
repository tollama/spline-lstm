"""Ingest real-device benchmark outputs into edge benchmark artifacts."""

from __future__ import annotations

import argparse
import json
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
    utc_now_iso,
)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_device_result_entry(raw: str) -> tuple[str, Path]:
    if "=" not in raw:
        raise ValueError(f"invalid --device-result value '{raw}', expected '<device_profile>=<json_path>'")
    device_profile, path = raw.split("=", 1)
    profile = device_profile.strip()
    if not profile:
        raise ValueError(f"invalid --device-result value '{raw}', device_profile must not be empty")
    result_path = Path(path.strip())
    if not result_path.exists():
        raise FileNotFoundError(f"device result not found: {result_path}")
    return profile, result_path


def _extract_latency(raw: dict[str, Any]) -> tuple[float | None, float | None]:
    p50 = _safe_float(raw.get("latency_p50_ms"))
    p95 = _safe_float(raw.get("latency_p95_ms"))
    if p50 is not None and p95 is not None:
        return p50, p95

    latency_obj = raw.get("latency_ms")
    if isinstance(latency_obj, dict):
        p50 = _safe_float(latency_obj.get("p50"))
        p95 = _safe_float(latency_obj.get("p95"))
        if p50 is not None and p95 is not None:
            return p50, p95

    samples = raw.get("latency_ms_samples", raw.get("latency_samples_ms"))
    if isinstance(samples, list):
        arr = np.asarray(samples, dtype=np.float64).reshape(-1)
        if arr.size > 0:
            return float(np.percentile(arr, 50)), float(np.percentile(arr, 95))

    return None, None


def _extract_size_mb(raw: dict[str, Any]) -> float | None:
    size_mb = _safe_float(raw.get("size_mb", raw.get("model_size_mb")))
    if size_mb is not None:
        return size_mb

    size_bytes = _safe_float(raw.get("size_bytes", raw.get("model_size_bytes")))
    if size_bytes is None:
        return None
    return float(size_bytes / (1024.0 * 1024.0))


def _extract_ram_peak_mb(raw: dict[str, Any]) -> float | None:
    ram_peak_mb = _safe_float(raw.get("ram_peak_mb", raw.get("memory_peak_mb")))
    if ram_peak_mb is not None:
        return ram_peak_mb

    ram_peak_bytes = _safe_float(raw.get("ram_peak_bytes", raw.get("memory_peak_bytes")))
    if ram_peak_bytes is None:
        return None
    return float(ram_peak_bytes / (1024.0 * 1024.0))


def _extract_attempts_failures(raw: dict[str, Any]) -> tuple[int, int]:
    samples = raw.get("latency_ms_samples", raw.get("latency_samples_ms"))
    inferred_attempts = len(samples) if isinstance(samples, list) else 0
    attempts = _safe_int(raw.get("attempts", raw.get("runs")))
    failures = _safe_int(raw.get("failures", raw.get("failure_count")))
    return max(0, attempts if attempts is not None else inferred_attempts), max(0, failures or 0)


def _extract_runtime(raw: dict[str, Any]) -> str:
    runtime_stack = raw.get("runtime_stack", raw.get("runtime"))
    if not isinstance(runtime_stack, str) or not runtime_stack:
        return "tflite"
    return runtime_stack


def _extract_status(raw: dict[str, Any], attempts: int, failures: int) -> str:
    status = raw.get("status")
    if isinstance(status, str) and status:
        return status
    if attempts <= 0:
        return "failed"
    return "succeeded" if failures <= 0 else "failed"


def _extract_accuracy_metrics(metrics_payload: dict[str, Any] | None) -> tuple[float | None, float | None]:
    if not metrics_payload:
        return None, None
    model_rmse = _safe_float(metrics_payload.get("metrics", {}).get("rmse"))
    baseline_rmse = _safe_float(metrics_payload.get("baselines", {}).get("naive_last", {}).get("rmse"))
    return model_rmse, baseline_rmse


def _score_record(
    *,
    model_rmse: float | None,
    baseline_rmse: float | None,
    latency_p95_ms: float | None,
    size_mb: float | None,
    failures: int,
    attempts: int,
    profile: dict[str, Any],
    edge_sla: dict[str, Any],
) -> dict[str, float]:
    accuracy_score = compute_accuracy_score(
        model_rmse=model_rmse,
        baseline_rmse=baseline_rmse,
        allowed_degradation_pct=float(edge_sla["max_rmse_degradation_pct"]),
    )
    latency_score = compute_latency_score(
        latency_p95_ms=latency_p95_ms,
        target_ms=float(profile["latency_p95_target_ms"]),
    )
    size_score = compute_size_score(
        size_mb=size_mb,
        target_mb=float(profile["size_target_mb"]),
        hard_limit_mb=float(profile["size_hard_limit_mb"]),
    )
    stability_score = compute_stability_score(failures=failures, attempts=attempts)
    edge_score = compute_edge_score(
        accuracy_score=accuracy_score,
        latency_score=latency_score,
        size_score=size_score,
        stability_score=stability_score,
        sla=edge_sla,
    )
    return {
        "accuracy_score": accuracy_score,
        "latency_score": latency_score,
        "size_score": size_score,
        "stability_score": stability_score,
        "edge_score": edge_score,
    }


def _build_device_record(
    *,
    run_id: str,
    device_profile: str,
    raw_payload: dict[str, Any],
    profile: dict[str, Any],
    edge_sla: dict[str, Any],
    source_path: Path,
    metrics_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    latency_p50_ms, latency_p95_ms = _extract_latency(raw_payload)
    if latency_p95_ms is None:
        raise ValueError(f"latency_p95_ms is required for profile '{device_profile}' (source: {source_path})")

    size_mb = _extract_size_mb(raw_payload)
    ram_peak_mb = _extract_ram_peak_mb(raw_payload)
    attempts, failures = _extract_attempts_failures(raw_payload)
    runtime_stack = _extract_runtime(raw_payload)
    status = _extract_status(raw_payload, attempts=attempts, failures=failures)

    model_rmse, baseline_rmse = _extract_accuracy_metrics(metrics_payload)
    score = _score_record(
        model_rmse=model_rmse,
        baseline_rmse=baseline_rmse,
        latency_p95_ms=latency_p95_ms,
        size_mb=size_mb,
        failures=failures,
        attempts=attempts,
        profile=profile,
        edge_sla=edge_sla,
    )

    fallback_chain = raw_payload.get("fallback_chain")
    if not isinstance(fallback_chain, list) or not fallback_chain:
        fallback_chain = [runtime_stack] if runtime_stack == "keras" else [runtime_stack, "keras"]

    return {
        "run_id": run_id,
        "device_profile": device_profile,
        "runtime_stack": runtime_stack,
        "fallback_chain": fallback_chain,
        "generated_at": utc_now_iso(),
        "status": status,
        "latency_p50_ms": latency_p50_ms,
        "latency_p95_ms": latency_p95_ms,
        "ram_peak_mb": ram_peak_mb,
        "size_mb": size_mb,
        "attempts": attempts,
        "failures": failures,
        "parity_error": raw_payload.get("parity_error"),
        "sla": edge_sla,
        "profile": profile,
        "source": {
            "kind": "device_ingest",
            "path": str(source_path),
        },
        **score,
    }


def _collect_device_sources(args: argparse.Namespace) -> list[tuple[str, Path]]:
    rows: list[tuple[str, Path]] = []
    for raw in args.device_result:
        rows.append(_parse_device_result_entry(raw))

    if args.device_results_dir:
        root = Path(args.device_results_dir)
        if not root.exists():
            raise FileNotFoundError(f"device_results_dir not found: {root}")
        for path in sorted(root.glob("*.json")):
            payload = _load_json(path)
            profile = payload.get("device_profile")
            if isinstance(profile, str) and profile:
                rows.append((profile, path))

    deduped: dict[str, Path] = {}
    for profile, path in rows:
        deduped[profile] = path
    return [(profile, path) for profile, path in deduped.items()]


def _load_existing_device_records(bench_dir: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    if not bench_dir.exists():
        return records
    for path in sorted(bench_dir.glob("*.json")):
        if path.name in {"leaderboard.json", "release_gate.json"}:
            continue
        payload = _load_json(path)
        profile = payload.get("device_profile")
        if isinstance(profile, str) and profile:
            records[profile] = payload
    return records


def run(args: argparse.Namespace) -> dict[str, Any]:
    artifacts_dir = Path(args.artifacts_dir)
    run_id = args.run_id
    bench_dir = artifacts_dir / "edge_bench" / run_id
    bench_dir.mkdir(parents=True, exist_ok=True)

    device_profiles = load_device_profiles(args.device_benchmark_config)
    edge_sla = parse_edge_sla(args.edge_sla)
    metrics_path = Path(args.metrics_json) if args.metrics_json else artifacts_dir / "metrics" / f"{run_id}.json"
    metrics_payload = _load_json(metrics_path) if metrics_path.exists() else None

    sources = _collect_device_sources(args)
    if not sources:
        raise ValueError("no device results provided; use --device-result or --device-results-dir")

    records_by_profile: dict[str, dict[str, Any]] = {}
    if args.merge_existing:
        records_by_profile.update(_load_existing_device_records(bench_dir))

    ingested_profiles: list[str] = []
    for profile_name, source_path in sources:
        profile_cfg = device_profiles.get(profile_name)
        if profile_cfg is None:
            raise ValueError(f"unknown device profile '{profile_name}' from {source_path}")
        raw_payload = _load_json(source_path)
        record = _build_device_record(
            run_id=run_id,
            device_profile=profile_name,
            raw_payload=raw_payload,
            profile=profile_cfg,
            edge_sla=edge_sla,
            source_path=source_path,
            metrics_payload=metrics_payload,
        )
        records_by_profile[profile_name] = record
        _write_json(bench_dir / f"{profile_name}.json", record)
        ingested_profiles.append(profile_name)

    ranked = sorted(records_by_profile.values(), key=lambda x: float(x.get("edge_score", 0.0)), reverse=True)
    leaderboard = {
        "run_id": run_id,
        "generated_at": utc_now_iso(),
        "champion": ranked[0]["device_profile"] if ranked else None,
        "fallback": ranked[1]["device_profile"] if len(ranked) > 1 else None,
        "results": ranked,
        "sources": {
            "ingested_profiles": ingested_profiles,
            "metrics_path": str(metrics_path) if metrics_path.exists() else None,
        },
    }
    _write_json(bench_dir / "leaderboard.json", leaderboard)
    return leaderboard


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Ingest real-device benchmark results into edge benchmark artifacts")
    p.add_argument("--run-id", type=str, required=True)
    p.add_argument("--artifacts-dir", type=str, default="artifacts")
    p.add_argument(
        "--device-result",
        action="append",
        default=[],
        help="Repeatable '<device_profile>=<json_path>' entry",
    )
    p.add_argument(
        "--device-results-dir",
        type=str,
        default=None,
        help="Optional directory of *.json files each containing 'device_profile'",
    )
    p.add_argument(
        "--edge-sla",
        type=str,
        choices=["balanced", "accuracy_biased", "latency_biased"],
        default="balanced",
    )
    p.add_argument("--device-benchmark-config", type=str, default=None)
    p.add_argument("--metrics-json", type=str, default=None)
    p.add_argument("--merge-existing", action="store_true", default=True)
    p.add_argument("--no-merge-existing", action="store_false", dest="merge_existing")
    return p


def main() -> None:
    args = build_parser().parse_args()
    out = run(args)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
