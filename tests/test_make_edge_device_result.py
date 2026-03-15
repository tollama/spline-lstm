from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

def test_make_edge_device_result_from_flags(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    out_path = tmp_path / "android_device.json"

    cmd = [
        sys.executable,
        "scripts/make_edge_device_result.py",
        "--output",
        str(out_path),
        "--runtime-stack",
        "tflite",
        "--fallback-chain",
        "tflite,keras",
        "--latency-p50-ms",
        "18.4",
        "--latency-p95-ms",
        "24.7",
        "--memory-peak-mb",
        "212.0",
        "--size-mb",
        "4.2",
        "--attempts",
        "200",
        "--failures",
        "0",
        "--accuracy-rmse",
        "0.94",
        "--accuracy-baseline-rmse",
        "1.0",
        "--accuracy-mae",
        "0.71",
        "--accuracy-wape",
        "8.9",
        "--accuracy-max-abs-diff",
        "1.42",
        "--accuracy-n-samples",
        "64",
        "--per-horizon-rmse",
        "0.81,0.93,1.05",
    ]
    proc = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["runtime_stack"] == "tflite"
    assert payload["fallback_chain"] == ["tflite", "keras"]
    assert payload["latency_ms"]["p95"] == 24.7
    assert payload["memory_peak_mb"] == 212.0
    assert payload["accuracy"]["rmse"] == 0.94
    assert payload["accuracy"]["baseline_rmse"] == 1.0
    assert payload["accuracy"]["rmse_degradation_pct"] == pytest.approx(-6.0)
    assert payload["accuracy"]["per_horizon_rmse"] == [0.81, 0.93, 1.05]


def test_make_edge_device_result_seeds_from_existing_report(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    report_path = tmp_path / "desktop_reference.json"
    out_path = tmp_path / "seeded_device.json"
    report_path.write_text(
        json.dumps(
            {
                "runtime_stack": "onnx",
                "fallback_chain": ["onnx", "keras"],
                "status": "succeeded",
                "latency_p50_ms": 21.1,
                "latency_p95_ms": 29.8,
                "ram_peak_mb": 236.0,
                "size_mb": 5.1,
                "attempts": 200,
                "failures": 0,
                "accuracy": {
                    "rmse": 0.97,
                    "baseline_rmse": 1.02,
                    "wape": 9.4,
                },
            }
        ),
        encoding="utf-8",
    )

    cmd = [
        sys.executable,
        "scripts/make_edge_device_result.py",
        "--output",
        str(out_path),
        "--from-report-json",
        str(report_path),
        "--memory-peak-mb",
        "240.0",
    ]
    proc = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["runtime_stack"] == "onnx"
    assert payload["fallback_chain"] == ["onnx", "keras"]
    assert payload["latency_p95_ms"] == 29.8
    assert payload["memory_peak_mb"] == 240.0
    assert payload["accuracy"]["rmse"] == 0.97
    assert payload["accuracy"]["baseline_rmse"] == 1.02
    assert payload["accuracy"]["rmse_degradation_pct"] == pytest.approx(-4.9019607843137315)
