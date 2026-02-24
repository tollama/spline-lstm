"""Phase 5 extension PoC tests (new path smoke + regression-safe contracts)."""

from __future__ import annotations

import argparse
import json
import pickle
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from src.models.lstm import BACKEND
from src.training.runner import _load_series, _validate_run_id_consistency


def _make_processed_bundle(base: Path, run_id: str) -> tuple[Path, Path]:
    pdir = base / "processed" / run_id
    mdir = base / "models" / run_id
    pdir.mkdir(parents=True, exist_ok=True)
    mdir.mkdir(parents=True, exist_ok=True)

    processed = pdir / "processed.npz"
    np.savez_compressed(
        processed,
        scaled=np.arange(48, dtype=np.float32),
        feature_names=np.asarray(["target"], dtype=str),
        target_indices=np.asarray([0], dtype=int),
    )

    meta = pdir / "meta.json"
    meta.write_text(json.dumps({"run_id": run_id}), encoding="utf-8")

    split_contract = pdir / "split_contract.json"
    split_contract.write_text(json.dumps({"schema_version": "phase1.split_contract.v1"}), encoding="utf-8")

    preprocessor = mdir / "preprocessor.pkl"
    with open(preprocessor, "wb") as f:
        pickle.dump({"run_id": run_id, "scaler": {"type": "standard"}}, f)

    return processed, preprocessor


def test_phase5_extension_infers_preprocessor_from_processed_layout(tmp_path: Path):
    artifacts = tmp_path / "artifacts"
    processed, preprocessor = _make_processed_bundle(artifacts, run_id="phase5-ext")

    args = argparse.Namespace(processed_npz=str(processed), preprocessor_pkl=None)
    out = _validate_run_id_consistency("phase5-ext", args)

    assert out == preprocessor


def test_phase5_extension_load_series_accepts_raw_target_only_npz(tmp_path: Path):
    npz_path = tmp_path / "processed.npz"
    raw_target = np.linspace(0.0, 1.0, 17, dtype=np.float64)
    np.savez_compressed(
        npz_path,
        raw_target=raw_target,
        feature_names=np.asarray(["target"], dtype=str),
        target_indices=np.asarray([0], dtype=int),
    )

    args = argparse.Namespace(
        processed_npz=str(npz_path),
        input_npy=None,
        synthetic_samples=32,
        synthetic_noise=0.0,
        seed=42,
    )

    out = _load_series(args)
    assert out.dtype == np.float32
    np.testing.assert_allclose(out, raw_target.astype(np.float32))


@pytest.mark.skipif(BACKEND != "tensorflow", reason="runner smoke requires tensorflow backend")
def test_phase5_extension_smoke_processed_only_path(tmp_path: Path):
    """Smoke the extension path: preprocess -> runner(processed only, inferred preprocessor)."""
    root = Path(__file__).resolve().parents[1]
    artifacts = tmp_path / "artifacts"
    run_id = "phase5-ext-smoke"

    prep_cmd = [
        sys.executable,
        "-m",
        "src.preprocessing.smoke",
        "--run-id",
        run_id,
        "--artifacts-dir",
        str(artifacts),
    ]
    prep = subprocess.run(prep_cmd, cwd=str(root), capture_output=True, text=True)
    assert prep.returncode == 0, f"preprocess smoke failed\nSTDOUT:\n{prep.stdout}\nSTDERR:\n{prep.stderr}"

    runner_cmd = [
        sys.executable,
        "-m",
        "src.training.runner",
        "--run-id",
        run_id,
        "--processed-npz",
        str(artifacts / "processed" / run_id / "processed.npz"),
        "--epochs",
        "1",
        "--artifacts-dir",
        str(artifacts),
    ]
    runner = subprocess.run(runner_cmd, cwd=str(root), capture_output=True, text=True)
    assert runner.returncode == 0, f"runner extension smoke failed\nSTDOUT:\n{runner.stdout}\nSTDERR:\n{runner.stderr}"

    metrics_path = artifacts / "metrics" / f"{run_id}.json"
    report_path = artifacts / "reports" / f"{run_id}.md"
    best_path = artifacts / "checkpoints" / run_id / "best.keras"

    assert metrics_path.exists()
    assert report_path.exists()
    assert best_path.exists()

    payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert payload["run_id"] == run_id
    assert payload["preprocessor"] == str(artifacts / "models" / run_id / "preprocessor.pkl")
    for k in ("mae", "rmse", "mape", "r2"):
        assert k in payload["metrics"]
