"""Data contract validators for preprocessing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class DataContract:
    """MVP input contract for univariate + optional covariates."""

    timestamp_col: str = "timestamp"
    target_col: str = "target"
    covariate_cols: Sequence[str] = field(default_factory=tuple)


def _max_consecutive_true(mask: np.ndarray) -> int:
    max_len = cur = 0
    for v in mask.astype(bool):
        if v:
            cur += 1
            if cur > max_len:
                max_len = cur
        else:
            cur = 0
    return int(max_len)


def validate_time_series_schema(
    df: pd.DataFrame,
    contract: Optional[DataContract] = None,
    allow_missing_target: bool = True,
    *,
    missing_ratio_max: float = 0.30,
    max_gap: int = 24,
    lookback: Optional[int] = None,
    horizon: Optional[int] = None,
) -> pd.DataFrame:
    """Validate and normalize raw time series dataframe.

    Contract:
    - required columns: timestamp, target
    - timestamp must be datetime-like, strictly increasing, unique
    - target must be numeric, finite for non-missing values, non-constant
    - missing ratio / max consecutive missing gap bounded
    - optional minimum length check: n_rows >= lookback + horizon + 1

    Returns a normalized (validated + reindexed) dataframe.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")

    c = contract or DataContract()

    required_cols = [c.timestamp_col, c.target_col, *list(c.covariate_cols)]
    if len(required_cols) != len(set(required_cols)):
        raise ValueError("contract columns must be unique (timestamp/target/covariates overlap)")

    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")

    out = df[required_cols].copy()
    out[c.timestamp_col] = pd.to_datetime(out[c.timestamp_col], errors="coerce")
    if out[c.timestamp_col].isna().any():
        n_bad = int(out[c.timestamp_col].isna().sum())
        raise ValueError(f"timestamp parse failed for {n_bad} rows")

    # Strictly increasing check in the input order (fail-fast for inversions)
    ts = out[c.timestamp_col]
    if ts.duplicated().any():
        raise ValueError("timestamp must be unique")
    if not ts.is_monotonic_increasing:
        raise ValueError("timestamp must be monotonic increasing")

    out[c.target_col] = pd.to_numeric(out[c.target_col], errors="coerce")
    target = out[c.target_col].to_numpy(dtype=float)

    if np.isinf(target).any():
        raise ValueError("target contains Inf/-Inf")

    target_missing = np.isnan(target)
    if not allow_missing_target and target_missing.any():
        n_bad = int(target_missing.sum())
        raise ValueError(f"target contains {n_bad} missing rows")

    if missing_ratio_max is not None:
        miss_ratio = float(target_missing.mean()) if len(target_missing) else 0.0
        if miss_ratio > float(missing_ratio_max):
            raise ValueError(
                f"target missing ratio {miss_ratio:.4f} exceeds limit {missing_ratio_max:.4f}"
            )

    if max_gap is not None and target_missing.any():
        gap = _max_consecutive_true(target_missing)
        if gap > int(max_gap):
            raise ValueError(f"target max missing gap {gap} exceeds limit {max_gap}")

    valid_target = target[~target_missing]
    if valid_target.size == 0:
        raise ValueError("target has no valid numeric values")
    if np.nanstd(valid_target) == 0.0:
        raise ValueError("target is constant (zero variance)")

    if lookback is not None and horizon is not None:
        min_rows = int(lookback) + int(horizon) + 1
        if len(out) < min_rows:
            raise ValueError(
                f"n_rows={len(out)} is too short; require >= lookback+horizon+1 ({min_rows})"
            )

    for cov_col in c.covariate_cols:
        out[cov_col] = pd.to_numeric(out[cov_col], errors="coerce")
        if out[cov_col].isna().all():
            raise ValueError(f"covariate '{cov_col}' is fully missing/non-numeric")

    return out.reset_index(drop=True)
