from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest
from src.training.edge_device_ingest import run


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _build_args(*, run_id: str, artifacts_dir: Path, device_result: list[str], merge_existing: bool = True) -> argparse.Namespace:
    return argparse.Namespace(
        run_id=run_id,
        artifacts_dir=str(artifacts_dir),
        device_result=device_result,
        device_results_dir=None,
        edge_sla="balanced",
        device_benchmark_config=None,
        metrics_json=None,
        merge_existing=merge_existing,
    )


def test_device_ingest_writes_profile_files_and_leaderboard(tmp_path: Path) -> None:
    run_id = "device-ingest-001"
    artifacts = tmp_path / "artifacts"

    _write_json(
        artifacts / "metrics" / f"{run_id}.json",
        {
            "metrics": {"rmse": 0.96},
            "baselines": {"naive_last": {"rmse": 1.00}},
        },
    )

    android_source = tmp_path / "android.json"
    ios_source = tmp_path / "ios.json"
    _write_json(
        android_source,
        {
            "runtime": "tflite",
            "latency_ms_samples": [18.0, 19.0, 20.0, 21.0],
            "memory_peak_mb": 210.0,
            "model_size_bytes": 4 * 1024 * 1024,
            "attempts": 1000,
            "failures": 0,
        },
    )
    _write_json(
        ios_source,
        {
            "runtime_stack": "onnx",
            "latency_ms": {"p50": 25.0, "p95": 32.0},
            "ram_peak_bytes": 220 * 1024 * 1024,
            "size_mb": 5.0,
            "attempts": 1000,
            "failures": 0,
        },
    )

    out = run(
        _build_args(
            run_id=run_id,
            artifacts_dir=artifacts,
            device_result=[
                f"android_high_end={android_source}",
                f"ios_high_end={ios_source}",
            ],
        )
    )

    bench_root = artifacts / "edge_bench" / run_id
    assert (bench_root / "android_high_end.json").exists()
    assert (bench_root / "ios_high_end.json").exists()
    assert (bench_root / "leaderboard.json").exists()

    assert out["run_id"] == run_id
    assert len(out["results"]) == 2
    assert out["results"][0]["device_profile"] == "android_high_end"
    assert out["results"][0]["latency_p95_ms"] == pytest.approx(20.85, rel=1e-3)
    assert out["results"][0]["size_mb"] == pytest.approx(4.0, rel=1e-6)


def test_device_ingest_merges_existing_records_by_default(tmp_path: Path) -> None:
    run_id = "device-ingest-merge-001"
    artifacts = tmp_path / "artifacts"
    existing_record = {
        "run_id": run_id,
        "device_profile": "desktop_reference",
        "runtime_stack": "tflite",
        "status": "succeeded",
        "latency_p50_ms": 12.0,
        "latency_p95_ms": 15.0,
        "ram_peak_mb": 150.0,
        "size_mb": 3.0,
        "attempts": 1000,
        "failures": 0,
        "edge_score": 88.0,
    }
    _write_json(artifacts / "edge_bench" / run_id / "desktop_reference.json", existing_record)

    source = tmp_path / "android.json"
    _write_json(
        source,
        {
            "runtime": "tflite",
            "latency_ms": {"p50": 22.0, "p95": 30.0},
            "memory_peak_mb": 200.0,
            "size_mb": 4.0,
            "attempts": 1000,
            "failures": 0,
        },
    )

    out = run(
        _build_args(
            run_id=run_id,
            artifacts_dir=artifacts,
            device_result=[f"android_high_end={source}"],
            merge_existing=True,
        )
    )

    assert len(out["results"]) == 2
    profiles = {item["device_profile"] for item in out["results"]}
    assert profiles == {"desktop_reference", "android_high_end"}


def test_device_ingest_requires_latency_p95(tmp_path: Path) -> None:
    run_id = "device-ingest-invalid-001"
    artifacts = tmp_path / "artifacts"
    source = tmp_path / "broken.json"
    _write_json(
        source,
        {
            "runtime": "tflite",
            "size_mb": 3.0,
            "attempts": 1000,
            "failures": 0,
        },
    )

    args = _build_args(
        run_id=run_id,
        artifacts_dir=artifacts,
        device_result=[f"android_high_end={source}"],
    )
    with pytest.raises(ValueError, match="latency_p95_ms is required"):
        run(args)
