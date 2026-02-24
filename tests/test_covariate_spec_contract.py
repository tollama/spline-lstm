from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from src.covariates.spec import enforce_covariate_spec, validate_covariate_spec_payload
from src.preprocessing.pipeline import PreprocessingConfig, run_preprocessing_pipeline


def _write_csv(path: Path) -> None:
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=80, freq="h"),
            "target": np.linspace(0, 1, 80),
            "temp": np.random.randn(80),
            "promo": np.random.randint(0, 2, size=80),
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def test_validate_covariate_spec_payload_accepts_valid_schema():
    payload = {
        "schema_version": "covariate_spec.v1",
        "dynamic_covariates": [{"name": "temp", "type": "numeric", "required": True}],
        "static_covariates": [{"name": "store_id", "type": "categorical", "required": False}],
    }
    out = validate_covariate_spec_payload(payload)
    assert out["schema_version"] == "covariate_spec.v1"
    assert out["dynamic_covariates"][0]["name"] == "temp"


def test_validate_covariate_spec_payload_rejects_invalid_field_types():
    payload = {
        "dynamic_covariates": [{"name": "temp", "type": "float", "required": "yes"}],
    }
    with pytest.raises(ValueError, match=r"dynamic_covariates\[0\]\.type"):
        validate_covariate_spec_payload(payload)


def test_validate_covariate_spec_payload_rejects_invalid_schema_version_and_imputation_policy():
    bad_version = {
        "schema_version": "covariate_spec.v2",
        "dynamic_covariates": [{"name": "temp", "type": "numeric", "required": True}],
    }
    with pytest.raises(ValueError, match="schema_version"):
        validate_covariate_spec_payload(bad_version)

    bad_policy = {
        "schema_version": "covariate_spec.v1",
        "dynamic_covariates": [{"name": "temp", "type": "numeric", "required": True}],
        "imputation_policy": {"dynamic_covariates": "median"},
    }
    with pytest.raises(ValueError, match="imputation_policy.dynamic_covariates"):
        validate_covariate_spec_payload(bad_policy)


def test_enforce_covariate_spec_optional_mode_remains_backward_compatible():
    out = enforce_covariate_spec(
        declared_dynamic=["temp"],
        declared_static=[],
        available_columns=["timestamp", "target", "temp"],
        spec_payload={},
        context="runner",
    )
    assert out["enabled"] is False
    assert out["dynamic_covariates"] == ["temp"]
    assert out["schema_version"] is None


def test_preprocessing_fails_fast_when_required_covariate_missing(tmp_path: Path):
    csv_path = tmp_path / "input.csv"
    _write_csv(csv_path)

    spec_path = tmp_path / "cov_spec.json"
    spec_path.write_text(
        json.dumps(
            {
                "dynamic_covariates": [
                    {"name": "temp", "type": "numeric", "required": True},
                    {"name": "event", "type": "numeric", "required": True},
                ]
            }
        ),
        encoding="utf-8",
    )

    cfg = PreprocessingConfig(
        run_id="covspec-missing",
        lookback=8,
        horizon=2,
        covariate_cols=("temp",),
        covariate_spec=str(spec_path),
    )

    with pytest.raises(ValueError, match="required covariates missing"):
        run_preprocessing_pipeline(str(csv_path), config=cfg, artifacts_dir=str(tmp_path / "artifacts"))


def test_preprocessing_artifact_contains_feature_schema_snapshot(tmp_path: Path):
    csv_path = tmp_path / "input.csv"
    _write_csv(csv_path)

    spec_path = tmp_path / "cov_spec.json"
    spec_path.write_text(
        json.dumps(
            {
                "schema_version": "covariate_spec.v1",
                "dynamic_covariates": [{"name": "temp", "type": "numeric", "required": True}],
            }
        ),
        encoding="utf-8",
    )

    cfg = PreprocessingConfig(
        run_id="covspec-ok",
        lookback=8,
        horizon=2,
        covariate_cols=("temp",),
        covariate_spec=str(spec_path),
    )
    out = run_preprocessing_pipeline(str(csv_path), config=cfg, artifacts_dir=str(tmp_path / "artifacts"))

    with open(out["preprocessor"], "rb") as f:
        payload = pickle.load(f)
    assert "feature_schema" in payload
    assert payload["feature_schema"]["enabled"] is True
    assert payload["feature_schema"]["dynamic_covariates"] == ["temp"]


def test_enforce_covariate_spec_rejects_missing_dataset_columns():
    spec = {
        "dynamic_covariates": [{"name": "temp", "type": "numeric", "required": True}],
    }
    with pytest.raises(ValueError, match="missing in dataset columns"):
        enforce_covariate_spec(
            declared_dynamic=["temp"],
            declared_static=[],
            available_columns=["target", "promo"],
            spec_payload=spec,
            context="runner",
        )
