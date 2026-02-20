"""Phase 3 MVP tests: baseline comparison, reproducibility, metadata validation.

요구사항:
1) 동일 config 재실행 편차 검증
2) naive baseline 대비 모델 성능 검증
3) split index / config / commit hash metadata 존재 검증
4) 실패 시 원인 메시지 명확화
"""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from models.lstm import BACKEND


pytestmark = pytest.mark.skipif(
    BACKEND != "tensorflow",
    reason="Phase 3 runner reproducibility test requires TensorFlow backend",
)


def _run_phase3_cli(tmp_path: Path, run_id: str, seed: int = 123) -> dict:
    root = Path(__file__).resolve().parents[1]
    artifacts_dir = tmp_path / "artifacts"
    checkpoints_dir = tmp_path / "checkpoints"

    cmd = [
        sys.executable,
        "-m",
        "src.training.runner",
        "--run-id",
        run_id,
        "--epochs",
        "20",
        "--batch-size",
        "16",
        "--sequence-length",
        "24",
        "--horizon",
        "1",
        "--test-size",
        "0.2",
        "--val-size",
        "0.2",
        "--synthetic",
        "--synthetic-samples",
        "360",
        "--synthetic-noise",
        "0.06",
        "--seed",
        str(seed),
        "--learning-rate",
        "0.003",
        "--verbose",
        "0",
        "--artifacts-dir",
        str(artifacts_dir),
        "--checkpoints-dir",
        str(checkpoints_dir),
    ]

    proc = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True)
    assert proc.returncode == 0, (
        "Phase3 runner execution failed. "
        f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    )

    metrics_path = artifacts_dir / "metrics" / f"{run_id}.json"
    assert metrics_path.exists(), f"metrics file missing: {metrics_path}"
    return json.loads(metrics_path.read_text(encoding="utf-8"))


def _generate_synthetic(n_samples: int = 360, noise: float = 0.06, seed: int = 123) -> np.ndarray:
    rng = np.random.default_rng(seed)
    t = np.linspace(0, 24 * np.pi, n_samples)
    y = np.sin(t) + 0.35 * np.sin(2.5 * t + 0.4) + noise * rng.normal(size=n_samples)
    return y.astype(np.float32)


def _split_series(data: np.ndarray, test_size: float, val_size: float):
    n = len(data)
    train_end = int(n * (1 - test_size))
    trainval = data[:train_end]
    test = data[train_end:]

    val_start = int(len(trainval) * (1 - val_size))
    train = trainval[:val_start]
    val = trainval[val_start:]
    return train, val, test


def _normalize_minmax(train: np.ndarray, val: np.ndarray, test: np.ndarray):
    lo = float(np.min(train))
    hi = float(np.max(train))
    den = hi - lo + 1e-8
    return (train - lo) / den, (val - lo) / den, (test - lo) / den


def _create_sequences(data: np.ndarray, seq_len: int = 24, horizon: int = 1):
    if data.ndim == 1:
        data = data.reshape(-1, 1)
    X, y = [], []
    for i in range(len(data) - seq_len - horizon + 1):
        X.append(data[i : i + seq_len])
        y.append(data[i + seq_len : i + seq_len + horizon])
    X = np.array(X)
    y = np.array(y).reshape(-1, horizon * data.shape[1])
    return X, y


def _rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def test_phase3_reproducibility_and_baseline_vs_model(tmp_path: Path):
    """동일 config 재실행 편차 + naive baseline 대비 성능 검증."""
    run1 = _run_phase3_cli(tmp_path, run_id="phase3-repro-a", seed=123)
    run2 = _run_phase3_cli(tmp_path, run_id="phase3-repro-b", seed=123)

    rmse1 = float(run1["metrics"]["rmse"])
    rmse2 = float(run2["metrics"]["rmse"])

    assert math.isfinite(rmse1) and math.isfinite(rmse2), "RMSE must be finite"

    # Reproducibility tolerance: absolute/relative mixed guard.
    # (환경 차이(TF/cuDNN/OS)로 완전 동일은 강제하지 않음)
    tol = max(0.05, rmse1 * 0.25)
    assert abs(rmse1 - rmse2) <= tol, (
        "Reproducibility drift exceeded tolerance. "
        f"rmse1={rmse1:.6f}, rmse2={rmse2:.6f}, tol={tol:.6f}"
    )

    # Baseline: persistence(last value of input window) on same synthetic split.
    cfg = run1["config"]
    series = _generate_synthetic(n_samples=360, noise=0.06, seed=int(cfg["seed"]))
    train_raw, val_raw, test_raw = _split_series(series, test_size=cfg["test_size"], val_size=cfg["val_size"])
    train_s, val_s, test_s = _normalize_minmax(train_raw, val_raw, test_raw)

    X_test, y_test = _create_sequences(
        test_s,
        seq_len=int(cfg["sequence_length"]),
        horizon=int(cfg["horizon"]),
    )
    y_pred_baseline = X_test[:, -1, 0].reshape(-1, 1)
    baseline_rmse = _rmse(y_test, y_pred_baseline)

    # Fairness contract: payload baseline must be computed on same split/scale/horizon.
    payload_baseline_rmse = float(run1["baselines"]["naive_last"]["rmse"])
    assert abs(payload_baseline_rmse - baseline_rmse) <= 1e-6, (
        "Baseline fairness mismatch. Expected runner baseline to match same synthetic split/scale/horizon. "
        f"payload={payload_baseline_rmse:.6f}, recomputed={baseline_rmse:.6f}"
    )

    assert rmse1 <= payload_baseline_rmse * 1.15, (
        "Model did not beat/track naive baseline within tolerance. "
        f"model_rmse={rmse1:.6f}, baseline_rmse={baseline_rmse:.6f}, "
        "allowed_factor=1.15"
    )


def test_phase3_metadata_presence_split_config_commit(tmp_path: Path):
    """split index / config / commit hash metadata 존재 검증 (실패 원인 메시지 포함)."""
    run = _run_phase3_cli(tmp_path, run_id="phase3-meta", seed=123)

    # config metadata
    assert isinstance(run.get("config"), dict) and run["config"], "Missing config metadata in metrics payload"

    # split index metadata: accept common key variants
    split_key = None
    for k in ("split_index", "split_indices", "split", "data_split"):
        if k in run:
            split_key = k
            break
    assert split_key is not None, (
        "Missing split index metadata. "
        "Expected one of keys: split_index/split_indices/split/data_split"
    )

    # commit hash metadata policy:
    # - git repo: commit_hash must be present and SHA-like
    # - non-git/unavailable: commit_hash may be null, but source must be explicit
    assert "commit_hash" in run, "Missing commit_hash key in metrics payload"
    assert "commit_hash_source" in run, "Missing commit_hash_source key in metrics payload"

    commit = run.get("commit_hash")
    source = str(run.get("commit_hash_source"))

    if commit is None:
        assert source == "unavailable", (
            "When commit_hash is null, commit_hash_source must be 'unavailable'. "
            f"source={source!r}"
        )
    else:
        commit_str = str(commit)
        assert re.fullmatch(r"[0-9a-fA-F]{7,40}", commit_str), f"Invalid commit hash format: {commit_str}"
        assert source == "git", f"Expected commit_hash_source='git' when hash exists, got {source!r}"

    metadata_path = Path(run["metadata_path"])
    assert metadata_path.exists(), f"metadata file missing: {metadata_path}"
    meta = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert meta.get("commit_hash") == commit
    assert meta.get("commit_hash_source") == source
