from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from models.lstm import LSTMModel
from preprocessing.pipeline import PreprocessingConfig, run_preprocessing_pipeline
from preprocessing.validators import DataContract, validate_time_series_schema
from preprocessing.window import make_windows_multivariate


def test_validate_schema_with_covariates_accepts_numeric_columns():
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=8, freq="h"),
            "target": np.linspace(0, 1, 8),
            "temp": np.linspace(10, 12, 8),
            "dow": [1, 1, 1, 1, 1, 1, 1, 1],
        }
    )
    out = validate_time_series_schema(
        df,
        contract=DataContract(covariate_cols=("temp", "dow")),
        allow_missing_target=True,
    )
    assert list(out.columns) == ["timestamp", "target", "temp", "dow"]


def test_make_windows_multivariate_shapes():
    features = np.random.randn(30, 3).astype(float)
    target = np.random.randn(30).astype(float)
    X, y = make_windows_multivariate(features, target, lookback=5, horizon=2)
    assert X.shape == (24, 5, 3)
    assert y.shape == (24, 2)


def test_pipeline_saves_multivariate_poc_artifacts(tmp_path: Path):
    n = 80
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=n, freq="h"),
            "target": np.sin(np.linspace(0, 4, n)),
            "temp": np.linspace(12, 18, n),
            "promo": np.where(np.arange(n) % 7 == 0, 1.0, 0.0),
        }
    )
    input_csv = tmp_path / "input.csv"
    df.to_csv(input_csv, index=False)

    out = run_preprocessing_pipeline(
        input_path=str(input_csv),
        config=PreprocessingConfig(run_id="phase5-mv", lookback=8, horizon=2, covariate_cols=("temp", "promo")),
        artifacts_dir=str(tmp_path / "artifacts"),
    )

    npz = np.load(out["processed"])
    assert "X_mv" in npz.files
    assert "y_mv" in npz.files
    assert "features_scaled" in npz.files
    assert npz["X_mv"].shape[2] == 3  # target + 2 covariates


def test_lstm_input_features_contract_for_multivariate_proto():
    model = LSTMModel(sequence_length=4, output_units=1, input_features=3)
    X = np.random.randn(16, 4, 3).astype(np.float32)
    y = np.random.randn(16, 1).astype(np.float32)
    model._validate_xy(X, y)


def test_pipeline_multivariate_artifact_contract_keys(tmp_path: Path):
    n = 64
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=n, freq="h"),
            "target": np.sin(np.linspace(0, 3, n)),
            "temp": np.linspace(10, 20, n),
            "promo": (np.arange(n) % 5 == 0).astype(float),
        }
    )
    input_csv = tmp_path / "input.csv"
    df.to_csv(input_csv, index=False)

    out = run_preprocessing_pipeline(
        input_path=str(input_csv),
        config=PreprocessingConfig(
            run_id="phase5-mv-contract", lookback=8, horizon=2, covariate_cols=("temp", "promo")
        ),
        artifacts_dir=str(tmp_path / "artifacts"),
    )

    npz = np.load(out["processed"])
    assert npz["feature_names"].tolist() == ["target", "temp", "promo"]
    assert npz["target_indices"].tolist() == [0]
    assert "covariates_scaled" in npz.files


def test_validate_schema_rejects_overlapping_contract_columns():
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=8, freq="h"),
            "target": np.linspace(0, 1, 8),
        }
    )
    with pytest.raises(ValueError, match="must be unique"):
        validate_time_series_schema(
            df,
            contract=DataContract(covariate_cols=("target",)),
            allow_missing_target=True,
        )
