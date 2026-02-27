from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.training.edge_release_gate import run


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _build_gate_args(
    *,
    run_id: str,
    artifacts: Path,
    required_profiles: str = "desktop_reference",
    min_stability_attempts: int = 1000,
    max_accuracy_degradation_pct: float = 2.0,
    skip_memory_check: bool = False,
) -> argparse.Namespace:
    return argparse.Namespace(
        run_id=run_id,
        artifacts_dir=str(artifacts),
        required_profiles=required_profiles,
        max_accuracy_degradation_pct=max_accuracy_degradation_pct,
        max_latency_p95_ms=None,
        size_limit_mb=8.0,
        size_hard_limit_mb=15.0,
        allow_extended_size=False,
        memory_budget_mb=None,
        skip_memory_check=skip_memory_check,
        min_stability_attempts=min_stability_attempts,
        max_failures=0,
        min_edge_score=None,
        output_path=None,
        device_result=[],
        device_results_dir=None,
        ingest_edge_sla="balanced",
        device_benchmark_config=None,
        metrics_json=None,
        no_ingest_merge_existing=False,
    )


def test_edge_release_gate_passes_and_updates_ota_manifest(tmp_path: Path) -> None:
    run_id = "gate-pass-001"
    artifacts = tmp_path / "artifacts"

    _write_json(
        artifacts / "edge_bench" / run_id / "leaderboard.json",
        {
            "run_id": run_id,
            "results": [
                {
                    "device_profile": "desktop_reference",
                    "status": "succeeded",
                    "runtime_stack": "tflite",
                    "latency_p95_ms": 12.0,
                    "size_mb": 3.2,
                    "ram_peak_mb": 200.0,
                    "attempts": 1000,
                    "failures": 0,
                    "edge_score": 95.0,
                    "profile": {
                        "latency_p95_target_ms": 50.0,
                        "memory_budget_mb": 1024.0,
                    },
                }
            ],
        },
    )
    _write_json(
        artifacts / "metrics" / f"{run_id}.json",
        {
            "metrics": {"rmse": 0.98},
            "baselines": {"naive_last": {"rmse": 1.00}},
        },
    )
    ota_manifest_path = artifacts / "exports" / run_id / "ota_manifest.json"
    _write_json(
        ota_manifest_path,
        {
            "model_id": "spline-edge",
            "semantic_version": "1.0.0",
            "target_runtime": "tflite",
        },
    )

    out = run(_build_gate_args(run_id=run_id, artifacts=artifacts))
    assert out["promotion_allowed"] is True

    ota = json.loads(ota_manifest_path.read_text(encoding="utf-8"))
    assert ota["promotion_allowed"] is True
    assert ota["promotion_blockers"] == []


def test_edge_release_gate_blocks_on_accuracy_degradation(tmp_path: Path) -> None:
    run_id = "gate-fail-acc-001"
    artifacts = tmp_path / "artifacts"

    _write_json(
        artifacts / "edge_bench" / run_id / "leaderboard.json",
        {
            "run_id": run_id,
            "results": [
                {
                    "device_profile": "desktop_reference",
                    "status": "succeeded",
                    "runtime_stack": "tflite",
                    "latency_p95_ms": 15.0,
                    "size_mb": 4.0,
                    "ram_peak_mb": 180.0,
                    "attempts": 50,
                    "failures": 0,
                    "edge_score": 90.0,
                    "profile": {
                        "latency_p95_target_ms": 50.0,
                        "memory_budget_mb": 1024.0,
                    },
                }
            ],
        },
    )
    _write_json(
        artifacts / "metrics" / f"{run_id}.json",
        {
            "metrics": {"rmse": 1.08},
            "baselines": {"naive_last": {"rmse": 1.00}},
        },
    )
    _write_json(
        artifacts / "exports" / run_id / "ota_manifest.json",
        {
            "model_id": "spline-edge",
            "semantic_version": "1.0.0",
            "target_runtime": "tflite",
        },
    )

    args = _build_gate_args(
        run_id=run_id,
        artifacts=artifacts,
        min_stability_attempts=20,
        max_accuracy_degradation_pct=2.0,
    )
    out = run(args)
    assert out["promotion_allowed"] is False
    assert any("rmse_degradation_pct" in item for item in out["blockers"])


def test_edge_release_gate_inline_ingests_device_results(tmp_path: Path) -> None:
    run_id = "gate-inline-ingest-001"
    artifacts = tmp_path / "artifacts"

    _write_json(
        artifacts / "metrics" / f"{run_id}.json",
        {
            "metrics": {"rmse": 0.98},
            "baselines": {"naive_last": {"rmse": 1.00}},
        },
    )
    _write_json(
        artifacts / "exports" / run_id / "ota_manifest.json",
        {
            "model_id": "spline-edge",
            "semantic_version": "1.0.0",
            "target_runtime": "tflite",
        },
    )

    android_source = tmp_path / "android_device.json"
    _write_json(
        android_source,
        {
            "runtime": "tflite",
            "latency_ms": {"p50": 18.0, "p95": 25.0},
            "memory_peak_mb": 220.0,
            "size_mb": 4.2,
            "attempts": 1000,
            "failures": 0,
        },
    )

    args = _build_gate_args(
        run_id=run_id,
        artifacts=artifacts,
        required_profiles="android_high_end",
        skip_memory_check=True,
    )
    args.device_result = [f"android_high_end={android_source}"]
    out = run(args)

    assert out["promotion_allowed"] is True
    assert (artifacts / "edge_bench" / run_id / "android_high_end.json").exists()
    assert (artifacts / "edge_bench" / run_id / "leaderboard.json").exists()
