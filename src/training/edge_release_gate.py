"""Release gate for OTA promotion based on edge benchmark SLA."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from src.training.edge import utc_now_iso

logger = logging.getLogger(__name__)


def _load_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"expected JSON object at {path}")
    return raw


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_csv_list(raw: str) -> list[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


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


def _find_profile_record(results: list[dict[str, Any]], profile: str) -> dict[str, Any] | None:
    for item in results:
        if item.get("device_profile") == profile:
            return item
    return None


def _accuracy_degradation_pct(metrics: dict[str, Any] | None) -> float | None:
    if not metrics:
        return None
    model_rmse = _safe_float(metrics.get("metrics", {}).get("rmse"))
    baseline_rmse = _safe_float(metrics.get("baselines", {}).get("naive_last", {}).get("rmse"))
    if model_rmse is None or baseline_rmse is None or baseline_rmse <= 0:
        return None
    return float((model_rmse - baseline_rmse) / baseline_rmse * 100.0)


def _evaluate_profile(
    *,
    profile_name: str,
    record: dict[str, Any] | None,
    degradation_pct: float | None,
    args: argparse.Namespace,
) -> dict[str, Any]:
    blockers: list[str] = []
    notes: list[str] = []
    profile_meta = record.get("profile", {}) if isinstance(record, dict) else {}

    if record is None:
        return {
            "device_profile": profile_name,
            "passed": False,
            "blockers": [f"missing benchmark result for required profile '{profile_name}'"],
            "notes": [],
        }

    status = str(record.get("status", "unknown"))
    if status != "succeeded":
        blockers.append(f"benchmark status must be 'succeeded', got '{status}'")

    latency = _safe_float(record.get("latency_p95_ms"))
    latency_limit = _safe_float(args.max_latency_p95_ms)
    if latency_limit is None:
        latency_limit = _safe_float(profile_meta.get("latency_p95_target_ms")) or 50.0
    if latency is None:
        blockers.append("missing latency_p95_ms")
    elif latency > latency_limit:
        blockers.append(f"latency_p95_ms={latency:.3f} exceeds limit {latency_limit:.3f}")

    size_mb = _safe_float(record.get("size_mb"))
    if size_mb is None:
        blockers.append("missing size_mb")
    else:
        if size_mb > args.size_hard_limit_mb:
            blockers.append(f"size_mb={size_mb:.3f} exceeds hard limit {args.size_hard_limit_mb:.3f}")
        elif size_mb > args.size_limit_mb:
            if args.allow_extended_size:
                notes.append(
                    f"size_mb={size_mb:.3f} exceeded default limit {args.size_limit_mb:.3f} but allowed as extended release"
                )
            else:
                blockers.append(f"size_mb={size_mb:.3f} exceeds default limit {args.size_limit_mb:.3f}")

    if not args.skip_memory_check:
        ram_peak_mb = _safe_float(record.get("ram_peak_mb"))
        memory_budget = _safe_float(args.memory_budget_mb)
        if memory_budget is None:
            memory_budget = _safe_float(profile_meta.get("memory_budget_mb")) or 256.0
        if ram_peak_mb is None:
            blockers.append("missing ram_peak_mb")
        elif ram_peak_mb > memory_budget:
            blockers.append(f"ram_peak_mb={ram_peak_mb:.3f} exceeds budget {memory_budget:.3f}")
    else:
        memory_budget = None

    attempts = _safe_int(record.get("attempts")) or 0
    failures = _safe_int(record.get("failures")) or 0
    if attempts < args.min_stability_attempts:
        blockers.append(f"attempts={attempts} below required {args.min_stability_attempts}")
    if failures > args.max_failures:
        blockers.append(f"failures={failures} exceeds allowed {args.max_failures}")

    if degradation_pct is None:
        blockers.append("missing RMSE baseline comparison for accuracy gate")
    elif degradation_pct > args.max_accuracy_degradation_pct:
        blockers.append(
            f"rmse_degradation_pct={degradation_pct:.3f} exceeds limit {args.max_accuracy_degradation_pct:.3f}"
        )

    edge_score = _safe_float(record.get("edge_score"))
    if args.min_edge_score is not None:
        if edge_score is None:
            blockers.append("missing edge_score")
        elif edge_score < args.min_edge_score:
            blockers.append(f"edge_score={edge_score:.3f} below required {args.min_edge_score:.3f}")

    return {
        "device_profile": profile_name,
        "passed": len(blockers) == 0,
        "blockers": blockers,
        "notes": notes,
        "metrics": {
            "runtime_stack": record.get("runtime_stack"),
            "latency_p95_ms": latency,
            "size_mb": size_mb,
            "ram_peak_mb": _safe_float(record.get("ram_peak_mb")),
            "attempts": attempts,
            "failures": failures,
            "edge_score": edge_score,
            "rmse_degradation_pct": degradation_pct,
        },
        "limits": {
            "max_latency_p95_ms": latency_limit,
            "size_limit_mb": args.size_limit_mb,
            "size_hard_limit_mb": args.size_hard_limit_mb,
            "max_accuracy_degradation_pct": args.max_accuracy_degradation_pct,
            "min_stability_attempts": args.min_stability_attempts,
            "max_failures": args.max_failures,
            "min_edge_score": args.min_edge_score,
            "memory_budget_mb": memory_budget,
            "allow_extended_size": args.allow_extended_size,
            "memory_check_enabled": not args.skip_memory_check,
        },
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    artifacts_dir = Path(args.artifacts_dir)
    run_id = args.run_id
    required_profiles = _parse_csv_list(args.required_profiles)
    if not required_profiles:
        raise ValueError("required_profiles must not be empty")

    leaderboard_path = artifacts_dir / "edge_bench" / run_id / "leaderboard.json"
    if not leaderboard_path.exists():
        raise FileNotFoundError(f"leaderboard not found: {leaderboard_path}")
    leaderboard = _load_json(leaderboard_path)
    results = leaderboard.get("results")
    if not isinstance(results, list):
        raise ValueError("leaderboard.results must be a list")
    result_rows = [row for row in results if isinstance(row, dict)]

    metrics_path = artifacts_dir / "metrics" / f"{run_id}.json"
    metrics_payload = _load_json(metrics_path) if metrics_path.exists() else None
    degradation_pct = _accuracy_degradation_pct(metrics_payload)

    checks: list[dict[str, Any]] = []
    for profile in required_profiles:
        record = _find_profile_record(result_rows, profile)
        checks.append(_evaluate_profile(profile_name=profile, record=record, degradation_pct=degradation_pct, args=args))

    blockers = [f"{item['device_profile']}: {msg}" for item in checks for msg in item["blockers"]]
    promotion_allowed = len(blockers) == 0

    gate_report = {
        "run_id": run_id,
        "generated_at": utc_now_iso(),
        "required_profiles": required_profiles,
        "promotion_allowed": promotion_allowed,
        "blockers": blockers,
        "checks": checks,
        "inputs": {
            "leaderboard_path": str(leaderboard_path),
            "metrics_path": str(metrics_path) if metrics_path.exists() else None,
        },
    }

    report_path = (
        Path(args.output_path)
        if args.output_path
        else (artifacts_dir / "edge_bench" / run_id / "release_gate.json")
    )
    _write_json(report_path, gate_report)

    ota_manifest_path = artifacts_dir / "exports" / run_id / "ota_manifest.json"
    if ota_manifest_path.exists():
        ota_manifest = _load_json(ota_manifest_path)
        ota_manifest["promotion_allowed"] = promotion_allowed
        ota_manifest["promotion_checked_at"] = gate_report["generated_at"]
        ota_manifest["promotion_blockers"] = blockers
        ota_manifest["promotion_required_profiles"] = required_profiles
        ota_manifest["promotion_gate_report"] = str(report_path)
        _write_json(ota_manifest_path, ota_manifest)
        gate_report["ota_manifest_path"] = str(ota_manifest_path)

    return gate_report


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Apply edge SLA gate before OTA promotion")
    p.add_argument("--run-id", type=str, required=True)
    p.add_argument("--artifacts-dir", type=str, default="artifacts")
    p.add_argument(
        "--required-profiles",
        type=str,
        default="android_high_end,ios_high_end",
        help="Comma-separated device profiles required to pass SLA",
    )
    p.add_argument("--max-accuracy-degradation-pct", type=float, default=2.0)
    p.add_argument("--max-latency-p95-ms", type=float, default=None)
    p.add_argument("--size-limit-mb", type=float, default=8.0)
    p.add_argument("--size-hard-limit-mb", type=float, default=15.0)
    p.add_argument("--allow-extended-size", action="store_true", default=False)
    p.add_argument("--memory-budget-mb", type=float, default=None)
    p.add_argument("--skip-memory-check", action="store_true", default=False)
    p.add_argument("--min-stability-attempts", type=int, default=1000)
    p.add_argument("--max-failures", type=int, default=0)
    p.add_argument("--min-edge-score", type=float, default=None)
    p.add_argument("--output-path", type=str, default=None)
    return p


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    args = build_parser().parse_args()
    report = run(args)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["promotion_allowed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
