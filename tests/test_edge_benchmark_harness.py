from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

import src.training.edge_benchmark as harness
from src.training.edge_benchmark import run


def test_edge_benchmark_writes_device_reports_and_leaderboard(tmp_path: Path) -> None:
    run_id = "edge-bench-001"
    artifacts = tmp_path / "artifacts"
    exports_dir = artifacts / "exports" / run_id
    exports_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "run_id": run_id,
        "runtime_compatibility": {
            "tflite": {"supported": False, "path": None, "reason": "not exported"},
            "onnx": {"supported": False, "path": None, "reason": "not exported"},
            "keras": {"supported": True, "path": None, "reason": None},
        },
        "input_specs": [{"name": "past_input", "shape": [1, 24, 1], "dtype": "float32"}],
    }
    (exports_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    metrics = {
        "run_id": run_id,
        "metrics": {"rmse": 1.0},
        "baselines": {"naive_last": {"rmse": 1.1}},
    }
    metrics_dir = artifacts / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    (metrics_dir / f"{run_id}.json").write_text(json.dumps(metrics), encoding="utf-8")

    args = argparse.Namespace(
        run_id=run_id,
        artifacts_dir=str(artifacts),
        device=None,
        iterations=10,
        warmup=2,
        edge_sla="balanced",
        device_benchmark_config=None,
    )
    out = run(args)
    assert out["run_id"] == run_id

    bench_root = artifacts / "edge_bench" / run_id
    assert (bench_root / "android_high_end.json").exists()
    assert (bench_root / "ios_high_end.json").exists()
    assert (bench_root / "desktop_reference.json").exists()
    assert (bench_root / "leaderboard.json").exists()


def test_edge_benchmark_benchmarks_keras_when_path_available(tmp_path: Path, monkeypatch) -> None:
    run_id = "edge-bench-keras-001"
    artifacts = tmp_path / "artifacts"
    exports_dir = artifacts / "exports" / run_id
    exports_dir.mkdir(parents=True, exist_ok=True)

    keras_path = artifacts / "checkpoints" / run_id / "best.keras"
    keras_path.parent.mkdir(parents=True, exist_ok=True)
    keras_path.write_bytes(b"dummy")

    manifest = {
        "run_id": run_id,
        "runtime_compatibility": {
            "tflite": {"supported": False, "path": None, "reason": "not exported"},
            "onnx": {"supported": False, "path": None, "reason": "not exported"},
            "keras": {"supported": True, "path": str(keras_path), "reason": None},
        },
        "input_specs": [{"name": "past_input", "shape": [1, 24, 1], "dtype": "float32"}],
    }
    (exports_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    metrics = {
        "run_id": run_id,
        "metrics": {"rmse": 1.0},
        "baselines": {"naive_last": {"rmse": 1.1}},
    }
    metrics_dir = artifacts / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    (metrics_dir / f"{run_id}.json").write_text(json.dumps(metrics), encoding="utf-8")

    def _fake_runtime_infer(runtime: str, model_path: Path, sample_inputs: list[np.ndarray]) -> np.ndarray:
        assert runtime == "keras"
        assert model_path == keras_path
        return np.zeros((1, 24, 1), dtype=np.float32)

    monkeypatch.setattr(harness, "_runtime_infer", _fake_runtime_infer)

    args = argparse.Namespace(
        run_id=run_id,
        artifacts_dir=str(artifacts),
        device=["desktop_reference"],
        iterations=3,
        warmup=1,
        edge_sla="balanced",
        device_benchmark_config=None,
    )
    out = run(args)
    assert out["run_id"] == run_id

    report = json.loads((artifacts / "edge_bench" / run_id / "desktop_reference.json").read_text(encoding="utf-8"))
    assert report["runtime_stack"] == "keras"
    assert report["status"] == "succeeded"
    assert report["latency_p95_ms"] is not None
    assert report["size_mb"] is not None
