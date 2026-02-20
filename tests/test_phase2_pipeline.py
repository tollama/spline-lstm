"""Phase 2 MVP E2E smoke tests (train/eval/infer + artifact checks)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from training.trainer import Trainer


class DummyTrainableModel:
    """Backend-free model stub for Phase 2 pipeline smoke."""

    def __init__(self):
        self.saved_paths: list[str] = []
        self.loaded_from: str | None = None
        self.fit_calls = []

    def fit_model(self, X, y, **kwargs):
        self.fit_calls.append((X, y, kwargs))
        # minimal history contract
        return {"loss": [0.3], "val_loss": [0.25], "mae": [0.2]}

    def predict(self, X):
        # deterministic inference output with correct shape [batch, 1]
        last_step = X[:, -1, 0]
        return (last_step * 0.95).reshape(-1, 1)

    def save(self, path):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("dummy-model")
        self.saved_paths.append(str(p))

    def load(self, path):
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(path)
        self.loaded_from = str(p)


def _synthetic_series(n: int = 240) -> np.ndarray:
    t = np.linspace(0, 12 * np.pi, n)
    y = np.sin(t) + 0.05 * np.cos(3 * t)
    return y.astype(float)


def test_phase2_e2e_train_eval_infer_and_artifacts(tmp_path: Path):
    """E2E smoke: train -> evaluate(metrics) -> infer -> best/last + run artifacts."""
    model = DummyTrainableModel()
    trainer = Trainer(model=model, sequence_length=24, prediction_horizon=1, save_dir=str(tmp_path / "checkpoints"))

    data = _synthetic_series(240)

    results = trainer.train(
        data,
        epochs=2,
        batch_size=8,
        test_size=0.2,
        val_size=0.2,
        normalize=True,
        verbose=0,
        extra_metric_fns={"max_abs_error": lambda y_true, y_pred: np.max(np.abs(y_true - y_pred))},
    )

    # Train/Eval contracts
    assert "metrics" in results
    assert set(["mae", "mse", "rmse", "mape", "r2", "max_abs_error"]).issubset(results["metrics"].keys())
    assert trainer.y_pred.shape == trainer.y_test.shape
    assert trainer.y_pred.ndim == 2 and trainer.y_pred.shape[1] == 1

    # Inference contract (additional explicit call)
    infer_sample = trainer.X_test[:3]
    infer_out = model.predict(infer_sample)
    assert infer_out.shape == (3, 1)

    # best/last checkpoints
    best_ckpt = Path(trainer.save_checkpoint("best"))
    last_ckpt = Path(trainer.save_checkpoint("last"))
    assert best_ckpt.exists(), "missing best checkpoint"
    assert last_ckpt.exists(), "missing last checkpoint"

    best_metrics = best_ckpt.parent / "best_metrics.json"
    last_metrics = last_ckpt.parent / "last_metrics.json"
    assert best_metrics.exists(), "missing best metrics json"
    assert last_metrics.exists(), "missing last metrics json"

    # run_id-scoped artifacts(metrics/report/model/preprocessor/config)
    run_id = "phase2-smoke"
    out = trainer.save_run_artifacts(
        run_id=run_id,
        base_dir=str(tmp_path / "artifacts"),
        config={"epochs": 2, "sequence_length": 24},
        report="# Phase2 Smoke Report\n\nSynthetic run succeeded.\n",
        preprocessor_blob=b"synthetic-preprocessor",
    )

    for key in ("model", "preprocessor", "metrics", "config", "report"):
        assert Path(out[key]).exists(), f"missing artifact file: {key}"

    # verify metrics/report contents are non-empty and parseable
    metrics = json.loads(Path(out["metrics"]).read_text())
    assert "rmse" in metrics
    assert "Synthetic run succeeded" in Path(out["report"]).read_text()


@pytest.mark.skipif(
    not Path(__file__).resolve().parents[1].joinpath("src", "training", "runner.py").exists(),
    reason="runner.py not implemented yet",
)
def test_phase2_runner_cli_smoke(tmp_path: Path):
    """Runner CLI smoke with synthetic config (short epoch)."""
    root = Path(__file__).resolve().parents[1]
    cmd = [
        sys.executable,
        "-m",
        "src.training.runner",
        "--run-id",
        "phase2-runner-smoke",
        "--epochs",
        "1",
        "--synthetic",
        "--artifacts-dir",
        str(tmp_path / "artifacts"),
        "--checkpoints-dir",
        str(tmp_path / "checkpoints"),
    ]
    proc = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True)
    assert proc.returncode == 0, f"runner smoke failed\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
