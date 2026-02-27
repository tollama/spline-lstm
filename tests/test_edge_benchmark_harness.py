from __future__ import annotations

import argparse
import json
from pathlib import Path

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
