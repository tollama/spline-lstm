"""End-to-end preprocessing pipeline for MVP P0."""

from __future__ import annotations

import json
import pickle
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from .spline import SplinePreprocessor
from .transform import build_scaler, chronological_split
from .validators import DataContract, validate_time_series_schema
from .window import make_windows, make_windows_multivariate
from src.covariates.spec import enforce_covariate_spec, load_covariate_spec
from src.utils.run_id import validate_run_id


@dataclass
class PreprocessingConfig:
    run_id: str
    lookback: int = 24
    horizon: int = 1
    smoothing_window: int = 5
    scaling: str = "standard"
    timestamp_col: str = "timestamp"
    target_col: str = "target"
    covariate_cols: Sequence[str] = ()  # Dynamic/Past covariates
    static_covariate_cols: Sequence[str] = ()
    future_covariate_cols: Sequence[str] = ()
    covariate_spec: Optional[str] = None


def _validate_run_id(run_id: str) -> None:
    validate_run_id(run_id, mode="legacy")


def _normalize_covariate_cols(cols: Sequence[str]) -> List[str]:
    out: List[str] = []
    for c in cols:
        if not isinstance(c, str):
            raise ValueError("covariate column names must be strings")
        name = c.strip()
        if not name:
            continue
        if name not in out:
            out.append(name)
    return out


def _scale_covariates_train_only(covariates: np.ndarray, train_end: int, method: str) -> tuple[np.ndarray, Dict[str, np.ndarray]]:
    if covariates.ndim != 2:
        raise ValueError(f"covariates must be 2D [time, n_covariates], got {covariates.shape}")
    if train_end <= 0 or train_end >= len(covariates):
        raise ValueError("invalid train_end boundary for covariate scaling")

    scaled = np.zeros_like(covariates, dtype=float)
    mins: List[float] = []
    maxs: List[float] = []
    means: List[float] = []
    stds: List[float] = []

    for i in range(covariates.shape[1]):
        sc = build_scaler(method)
        train_col = covariates[:train_end, i]
        sc.fit(train_col)
        scaled[:, i] = sc.transform(covariates[:, i])
        payload = sc.to_dict()
        mins.append(float(payload.get("min", 0.0)))
        maxs.append(float(payload.get("max", 1.0)))
        means.append(float(payload.get("mean", 0.0)))
        stds.append(float(payload.get("std", 1.0)))

    return scaled, {
        "method": method,
        "min": np.asarray(mins, dtype=float),
        "max": np.asarray(maxs, dtype=float),
        "mean": np.asarray(means, dtype=float),
        "std": np.asarray(stds, dtype=float),
    }


def run_preprocessing_pipeline(
    input_path: str,
    config: PreprocessingConfig,
    artifacts_dir: str = "artifacts",
) -> Dict[str, str]:
    """Run schema -> interpolate/smooth -> scale -> windowing and save artifacts.

    Saved artifacts:
    - artifacts/processed/{run_id}/processed.npz
    - artifacts/models/{run_id}/preprocessor.pkl
    - artifacts/processed/{run_id}/meta.json
    """
    _validate_run_id(config.run_id)

    in_path = Path(input_path)
    if not in_path.exists():
        raise FileNotFoundError(f"input file not found: {input_path}")

    if in_path.suffix.lower() == ".parquet":
        raw = pd.read_parquet(in_path)
    else:
        raw = pd.read_csv(in_path)

    covariate_cols = _normalize_covariate_cols(config.covariate_cols)
    static_cols = _normalize_covariate_cols(config.static_covariate_cols)
    future_cols = _normalize_covariate_cols(config.future_covariate_cols)

    covariate_spec_raw = load_covariate_spec(config.covariate_spec)
    covariate_contract = enforce_covariate_spec(
        declared_dynamic=list(set(covariate_cols) | set(future_cols)),
        declared_static=static_cols,
        available_columns=raw.columns,
        spec_payload=covariate_spec_raw,
        context="preprocessing",
    )
    covariate_cols = covariate_contract["dynamic_covariates"]

    validated = validate_time_series_schema(
        raw,
        contract=DataContract(
            timestamp_col=config.timestamp_col,
            target_col=config.target_col,
            covariate_cols=tuple(set(covariate_cols) | set(static_cols) | set(future_cols)),
        ),
        allow_missing_target=True,
        lookback=config.lookback,
        horizon=config.horizon,
    )

    series = validated[config.target_col].to_numpy(dtype=float)

    pre = SplinePreprocessor()
    series_interp = pre.interpolate_missing(series)
    series_smooth = pre.smooth(series_interp, window=config.smoothing_window)

    # Leakage-safe scaling: fit only on train split, then transform full series.
    train_smooth, _, _, (train_end, _) = chronological_split(series_smooth)
    scaler = build_scaler(config.scaling)
    scaler.fit(train_smooth)
    series_scaled = scaler.transform(series_smooth)

    X, y = make_windows(series_scaled, lookback=config.lookback, horizon=config.horizon)

    covariates_raw = None
    covariates_scaled = None
    covariate_scaler = None
    features_scaled = None
    future_features_scaled = None
    static_features = None
    X_mv, y_mv, X_fut = None, None, None
    feature_names = [config.target_col]
    target_indices = [0]

    if covariate_cols:
        cov_df = validated[covariate_cols].copy()
        cov_df = cov_df.ffill().bfill().fillna(0.0)
        covariates_raw = cov_df.to_numpy(dtype=float)
        if np.isnan(covariates_raw).any() or np.isinf(covariates_raw).any():
            raise ValueError("covariates contain NaN/Inf after imputation")

        covariates_scaled, covariate_scaler = _scale_covariates_train_only(
            covariates_raw,
            train_end=train_end,
            method=config.scaling,
        )
        features_scaled = np.concatenate([series_scaled.reshape(-1, 1), covariates_scaled], axis=1)
        feature_names = [config.target_col, *covariate_cols]

        # Handle Future Covariates if any
        if future_cols:
            f_cov_df = validated[future_cols].copy().ffill().bfill().fillna(0.0)
            f_cov_raw = f_cov_df.to_numpy(dtype=float)
            f_cov_scaled, _ = _scale_covariates_train_only(f_cov_raw, train_end=train_end, method=config.scaling)
            future_features_scaled = f_cov_scaled

        # Handle Static Covariates if any
        if static_cols:
            s_cov_df = validated[static_cols].copy().ffill().bfill().fillna(0.0)
            static_features = s_cov_df.to_numpy(dtype=float)

        X_mv, y_mv, X_fut = make_windows_multivariate(
            features=features_scaled,
            target=series_scaled,
            lookback=config.lookback,
            horizon=config.horizon,
            future_features=future_features_scaled,
        )

    base = Path(artifacts_dir)
    processed_dir = base / "processed" / config.run_id
    model_dir = base / "models" / config.run_id
    processed_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)

    processed_path = processed_dir / "processed.npz"
    preprocessor_path = model_dir / "preprocessor.pkl"
    meta_path = processed_dir / "meta.json"
    split_contract_path = processed_dir / "split_contract.json"

    arrays = {
        "X": X,
        "y": y,
        "timestamps": validated[config.timestamp_col].astype(str).to_numpy(),
        "raw_target": series,
        "interpolated": series_interp,
        "smoothed": series_smooth,
        "scaled": series_scaled,
        "feature_names": np.asarray(feature_names, dtype=str),
        "target_indices": np.asarray(target_indices, dtype=int),
    }
    if covariates_raw is not None and features_scaled is not None and X_mv is not None and y_mv is not None:
        arrays.update(
            {
                "covariates_raw": covariates_raw,
                "covariates_scaled": covariates_scaled,
                "features_scaled": features_scaled,
                "X_mv": X_mv,
                "y_mv": y_mv,
                "X_fut": X_fut if X_fut is not None else np.array([]),
                "static_features": static_features if static_features is not None else np.array([]),
            }
        )

    np.savez_compressed(processed_path, **arrays)

    preprocessor_payload = {
        "schema_version": "phase1.v2",
        "run_id": config.run_id,
        "feature_order": feature_names,
        "feature_names": feature_names,
        "target_indices": target_indices,
        "spline": {
            "degree": pre.degree,
            "smoothing_factor": pre.smoothing_factor,
            "num_knots": pre.num_knots,
        },
        "scaler": scaler.to_dict(),
        "config": asdict(config),
        "multivariate": {
            "enabled": bool(covariate_cols),
            "covariate_cols": list(covariate_cols),
            "static_covariate_cols": list(static_cols),
            "future_covariate_cols": list(future_cols),
            "covariate_scaler": {
                "method": covariate_scaler["method"],
                "mean": covariate_scaler["mean"].tolist(),
                "std": covariate_scaler["std"].tolist(),
                "min": covariate_scaler["min"].tolist(),
                "max": covariate_scaler["max"].tolist(),
            }
            if covariate_scaler is not None
            else None,
        },
        "feature_schema": covariate_contract,
    }
    with open(preprocessor_path, "wb") as f:
        pickle.dump(preprocessor_payload, f)

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "run_id": config.run_id,
                "input_path": str(in_path),
                "n_rows": int(len(validated)),
                "X_shape": list(X.shape),
                "y_shape": list(y.shape),
                "covariate_cols": list(covariate_cols),
                "static_covariate_cols": list(static_cols),
                "future_covariate_cols": list(future_cols),
                "feature_names": feature_names,
                "target_indices": target_indices,
                "X_mv_shape": list(X_mv.shape) if X_mv is not None else None,
                "y_mv_shape": list(y_mv.shape) if y_mv is not None else None,
                "X_fut_shape": list(X_fut.shape) if X_fut is not None else None,
                "static_features_shape": list(static_features.shape) if static_features is not None else None,
                "feature_schema": covariate_contract,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    n_windows = int(len(X))
    test_n = int(n_windows * 0.2)
    trainval_n = n_windows - test_n
    val_n = int(trainval_n * 0.2)
    train_n = trainval_n - val_n

    split_contract = {
        "schema_version": "phase1.split_contract.v1",
        "run_id": config.run_id,
        "processed_npz": str(processed_path),
        "window_keys": {
            "X": "X",
            "y": "y",
            "time_index": "timestamps",
        },
        "canonical_outputs": {
            "X_train": {"source": "X", "slice": [0, train_n]},
            "X_val": {"source": "X", "slice": [train_n, train_n + val_n]},
            "X_test": {"source": "X", "slice": [train_n + val_n, n_windows]},
            "y_train": {"source": "y", "slice": [0, train_n]},
            "y_val": {"source": "y", "slice": [train_n, train_n + val_n]},
            "y_test": {"source": "y", "slice": [train_n + val_n, n_windows]},
            "time_index_train": {"source": "timestamps", "slice": [0, train_n]},
            "time_index_val": {"source": "timestamps", "slice": [train_n, train_n + val_n]},
            "time_index_test": {"source": "timestamps", "slice": [train_n + val_n, n_windows]},
        },
        "split_index": {
            "n_windows": n_windows,
            "train": {"start": 0, "end": train_n},
            "val": {"start": train_n, "end": train_n + val_n},
            "test": {"start": train_n + val_n, "end": n_windows},
            "ratios": {"test_size": 0.2, "val_size": 0.2},
        },
    }
    with open(split_contract_path, "w", encoding="utf-8") as f:
        json.dump(split_contract, f, indent=2, ensure_ascii=False)

    return {
        "processed": str(processed_path),
        "preprocessor": str(preprocessor_path),
        "meta": str(meta_path),
        "split_contract": str(split_contract_path),
    }
