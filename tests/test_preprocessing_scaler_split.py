"""Leakage-safety tests for preprocessing pipeline scaling."""

from __future__ import annotations

import os
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from preprocessing.pipeline import PreprocessingConfig, run_preprocessing_pipeline


def test_pipeline_fits_scaler_on_train_split_only(tmp_path: Path):
    """Scaler stats must come from train split only (no val/test leakage)."""
    n = 20
    # Place a large outlier in the final region (test split for default 0.7/0.15 split).
    target = np.array(list(range(1, n)) + [1000], dtype=float)
    target[5] = np.nan
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=n, freq="h"),
            "target": target,
        }
    )
    input_path = tmp_path / "input.csv"
    df.to_csv(input_path, index=False)

    cfg = PreprocessingConfig(
        run_id="leakage-safe-prep",
        lookback=3,
        horizon=1,
        smoothing_window=1,
        scaling="standard",
    )

    out = run_preprocessing_pipeline(
        input_path=str(input_path),
        config=cfg,
        artifacts_dir=str(tmp_path / "artifacts"),
    )

    with open(out["preprocessor"], "rb") as f:
        payload = pickle.load(f)

    scaler = payload["scaler"]
    train_end = int(n * 0.7)

    processed = np.load(out["processed"])
    smoothed = processed["smoothed"]
    train = smoothed[:train_end]

    assert scaler["type"] == "standard"
    assert np.isclose(scaler["mean"], np.mean(train), atol=1e-9)
    assert np.isclose(scaler["std"], np.std(train), atol=1e-9)
