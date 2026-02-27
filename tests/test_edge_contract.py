from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import src.training.edge as edge
from src.training.edge import (
    build_runtime_compatibility,
    compute_accuracy_score,
    compute_edge_score,
    compute_latency_score,
    compute_size_score,
    compute_stability_score,
    load_device_profiles,
    parity_within_thresholds,
    parse_edge_sla,
    select_runtime_stack,
)


def test_parse_edge_sla_known_presets() -> None:
    balanced = parse_edge_sla("balanced")
    assert balanced["accuracy_weight"] == pytest.approx(0.45)
    assert balanced["latency_weight"] == pytest.approx(0.30)
    assert balanced["size_weight"] == pytest.approx(0.15)
    assert balanced["stability_weight"] == pytest.approx(0.10)

    with pytest.raises(ValueError):
        parse_edge_sla("unknown")


def test_runtime_selection_prefers_supported_order() -> None:
    runtime_compat = {
        "tflite": {"supported": False},
        "onnx": {"supported": True},
        "keras": {"supported": True},
    }
    runtime, fallback = select_runtime_stack(runtime_compat, preferred_order=["tflite", "onnx", "keras"])
    assert runtime == "onnx"
    assert fallback == ["onnx", "keras"]


def test_build_runtime_compatibility_matrix() -> None:
    matrix = build_runtime_compatibility(
        {
            "tflite": {"status": "succeeded", "path": "a.tflite"},
            "onnx": {"status": "failed", "error": "missing tf2onnx"},
        },
        keras_path="best.keras",
    )
    assert matrix["tflite"]["supported"] is True
    assert matrix["onnx"]["supported"] is False
    assert matrix["keras"]["supported"] is True
    assert matrix["keras"]["path"] == "best.keras"


def test_edge_score_components_and_weighted_total() -> None:
    sla = parse_edge_sla("balanced")
    acc = compute_accuracy_score(
        model_rmse=0.95, baseline_rmse=1.0, allowed_degradation_pct=sla["max_rmse_degradation_pct"]
    )
    lat = compute_latency_score(latency_p95_ms=45.0, target_ms=50.0)
    siz = compute_size_score(size_mb=6.0, target_mb=8.0, hard_limit_mb=15.0)
    st = compute_stability_score(failures=0, attempts=1000)
    score = compute_edge_score(
        accuracy_score=acc,
        latency_score=lat,
        size_score=siz,
        stability_score=st,
        sla=sla,
    )
    assert score > 90.0


def test_load_device_profiles_merges_user_profiles(tmp_path: Path) -> None:
    cfg = tmp_path / "devices.json"
    cfg.write_text(
        json.dumps(
            {
                "profiles": {
                    "android_high_end": {"latency_p95_target_ms": 40},
                    "custom_device": {"runtime_order": ["onnx", "keras"], "latency_p95_target_ms": 60},
                }
            }
        ),
        encoding="utf-8",
    )
    profiles = load_device_profiles(str(cfg))
    assert profiles["android_high_end"]["latency_p95_target_ms"] == 40
    assert profiles["custom_device"]["runtime_order"] == ["onnx", "keras"]


def test_parity_threshold_evaluator() -> None:
    ok = {"max_abs_diff": 0.04, "rmse": 0.02}
    bad = {"max_abs_diff": 0.8, "rmse": 0.3}
    err = {"error": "runtime failure"}
    assert parity_within_thresholds(ok, max_abs_diff=0.1, rmse=0.1) is True
    assert parity_within_thresholds(bad, max_abs_diff=0.1, rmse=0.1) is False
    assert parity_within_thresholds(err, max_abs_diff=0.1, rmse=0.1) is False


def test_export_tflite_model_subprocess_failure_returns_failed(monkeypatch, tmp_path: Path) -> None:
    class _DummyModel:
        def save(self, path: Path, include_optimizer: bool = False) -> None:
            Path(path).write_text("dummy", encoding="utf-8")

    def _fake_run(*_args, **_kwargs):
        return SimpleNamespace(returncode=-6, stdout="", stderr="LLVM ERROR: Failed to infer result type(s).")

    monkeypatch.setattr(edge.subprocess, "run", _fake_run)
    out = edge.export_tflite_model(_DummyModel(), tmp_path / "model.tflite", quantization="fp16")
    assert out["status"] == "failed"
    assert "LLVM ERROR" in out["error"]
