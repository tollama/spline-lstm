from __future__ import annotations

import os
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from preprocessing.pipeline import PreprocessingConfig, run_preprocessing_pipeline
from preprocessing.validators import validate_time_series_schema
from preprocessing.window import make_windows


def _base_df(n: int = 40) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=n, freq="h"),
            "target": np.linspace(1.0, 2.0, n),
        }
    )


def test_phase1_missing_required_column_fails():
    df = _base_df().drop(columns=["target"])
    with pytest.raises(ValueError, match="missing required columns"):
        validate_time_series_schema(df)


def test_phase1_non_monotonic_timestamp_fails():
    df = _base_df()
    df.loc[10, "timestamp"] = df.loc[5, "timestamp"]
    with pytest.raises(ValueError, match="unique"):
        validate_time_series_schema(df)


def test_phase1_missing_ratio_limit_fails():
    df = _base_df()
    df.loc[:20, "target"] = np.nan
    with pytest.raises(ValueError, match="missing ratio"):
        validate_time_series_schema(df, allow_missing_target=True)


def test_phase1_window_dtype_and_shape_contract():
    series = np.linspace(0.0, 1.0, 32)
    X, y = make_windows(series, lookback=8, horizon=3)
    assert X.ndim == 3 and y.ndim == 2
    assert X.shape[1:] == (8, 1)
    assert y.shape[1] == 3
    assert X.dtype == np.float32
    assert y.dtype == np.float32


def test_phase1_preprocessor_payload_has_schema_version(tmp_path: Path):
    df = _base_df(60)
    input_path = tmp_path / "input.csv"
    df.to_csv(input_path, index=False)

    cfg = PreprocessingConfig(run_id="phase1-contract-test", lookback=12, horizon=2)
    out = run_preprocessing_pipeline(
        input_path=str(input_path),
        config=cfg,
        artifacts_dir=str(tmp_path / "artifacts"),
    )

    with open(out["preprocessor"], "rb") as f:
        payload = pickle.load(f)

    assert payload["schema_version"] == "phase1.v2"
    assert payload["feature_order"] == ["target"]


def test_phase1_pipeline_emits_split_contract_file(tmp_path: Path):
    df = _base_df(80)
    input_path = tmp_path / "input.csv"
    df.to_csv(input_path, index=False)

    cfg = PreprocessingConfig(run_id="phase1-split-contract", lookback=12, horizon=2)
    out = run_preprocessing_pipeline(
        input_path=str(input_path),
        config=cfg,
        artifacts_dir=str(tmp_path / "artifacts"),
    )

    contract_path = Path(out["split_contract"])
    assert contract_path.exists()

    import json

    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    assert contract["schema_version"] == "phase1.split_contract.v1"
    assert contract["run_id"] == "phase1-split-contract"
    for k in (
        "X_train",
        "X_val",
        "X_test",
        "y_train",
        "y_val",
        "y_test",
        "time_index_train",
        "time_index_val",
        "time_index_test",
    ):
        assert k in contract["canonical_outputs"]
    assert "split_index" in contract
