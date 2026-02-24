"""Phase 5 runner contract alignment tests (doc <-> code)."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pytest
from src.training.runner import _compute_metrics, _load_training_arrays, _parse_csv_like, _parse_export_formats


def test_parse_csv_like_contract_list_parsing():
    assert _parse_csv_like(None) == []
    assert _parse_csv_like("") == []
    assert _parse_csv_like("target") == ["target"]
    assert _parse_csv_like("target_a, target_b ,, ") == ["target_a", "target_b"]


def test_parse_export_formats_contract_validation():
    assert _parse_export_formats(None) == ["none"]
    assert _parse_export_formats("") == ["none"]
    assert _parse_export_formats("onnx") == ["onnx"]
    assert _parse_export_formats("onnx,tflite") == ["onnx", "tflite"]
    assert _parse_export_formats("onnx,onnx,tflite") == ["onnx", "tflite"]

    with pytest.raises(ValueError):
        _parse_export_formats("none,onnx")
    with pytest.raises(ValueError):
        _parse_export_formats("coreml")


def test_load_training_arrays_prefers_phase5_xy_keys(tmp_path: Path):
    npz = tmp_path / "processed.npz"
    X = np.random.randn(12, 6, 4).astype(np.float32)
    y = np.random.randn(12, 4).astype(np.float32)
    np.savez_compressed(
        npz, X=X, y=y, feature_names=np.array(["target", "c1", "c2", "c3"]), target_indices=np.array([0])
    )

    args = argparse.Namespace(processed_npz=str(npz), sequence_length=6)
    x_out, y_out = _load_training_arrays(args)

    assert x_out is not None and y_out is not None
    assert x_out.shape == (12, 6, 4)
    assert y_out.shape == (12, 4)


def test_load_training_arrays_supports_legacy_xmv_ymv_keys(tmp_path: Path):
    npz = tmp_path / "processed.npz"
    X_mv = np.random.randn(10, 5, 3).astype(np.float32)
    y_mv = np.random.randn(10, 2).astype(np.float32)
    np.savez_compressed(
        npz, X_mv=X_mv, y_mv=y_mv, feature_names=np.array(["target", "c1", "c2"]), target_indices=np.array([0])
    )

    args = argparse.Namespace(processed_npz=str(npz), sequence_length=5)
    x_out, y_out = _load_training_arrays(args)

    assert x_out is not None and y_out is not None
    assert x_out.shape == (10, 5, 3)
    assert y_out.shape == (10, 2)


def test_compute_metrics_includes_mase_for_consistency():
    y_true = np.array([[1.0], [2.0], [3.0], [4.0]], dtype=np.float32)
    y_pred = np.array([[1.2], [1.8], [2.7], [4.1]], dtype=np.float32)
    metrics = _compute_metrics(y_true, y_pred)

    assert "mase" in metrics
    assert np.isfinite(metrics["mase"])
