"""Synthetic data generation/validation tests (S1/S2/S3).

Goal
----
Validate that synthetic scenario outputs are realistic and deterministic:
- S1/S2/S3 generation success
- required columns / shape / dtype contract
- missing / outlier / irregular-sampling injection checks (S2/S3)
- seed reproducibility
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from src.training.runner import _generate_synthetic


def _build_synthetic_scenario(
    scenario: str,
    n_samples: int = 240,
    seed: int = 123,
) -> pd.DataFrame:
    """Build scenario dataframe from project synthetic base signal.

    Output contract:
      columns: [timestamp, target, scenario]
      - timestamp: datetime64[ns], monotonic increasing, unique
      - target: float64 (may include NaN by scenario)
      - scenario: one of S1/S2/S3
    """
    scenario = scenario.upper()
    if scenario not in {"S1", "S2", "S3"}:
        raise ValueError(f"unsupported scenario: {scenario}")

    rng = np.random.default_rng(seed)
    base = _generate_synthetic(n_samples=n_samples, noise=0.08, seed=seed).astype(np.float64)

    # S1: regular hourly, no anomaly injection
    if scenario == "S1":
        ts = pd.date_range("2026-01-01", periods=n_samples, freq="h")
        y = base.copy()

    # S2: regular hourly + missing + outlier injection
    elif scenario == "S2":
        ts = pd.date_range("2026-01-01", periods=n_samples, freq="h")
        y = base.copy()

        # deterministic injection via seed
        n_missing = max(3, int(n_samples * 0.06))
        n_outlier = max(3, int(n_samples * 0.03))
        idx = np.arange(n_samples)
        missing_idx = rng.choice(idx, size=n_missing, replace=False)
        remaining = np.setdiff1d(idx, missing_idx)
        outlier_idx = rng.choice(remaining, size=n_outlier, replace=False)

        y[missing_idx] = np.nan
        # outlier amplitude based on robust scale of non-missing points
        sigma = np.nanstd(y)
        y[outlier_idx] += 6.0 * sigma

    # S3: irregular sampling + missing + outlier injection
    else:
        full_ts = pd.date_range("2026-01-01", periods=n_samples, freq="h")

        # drop ~12% timestamps to produce irregular intervals
        keep = np.ones(n_samples, dtype=bool)
        drop_n = max(5, int(n_samples * 0.12))
        drop_idx = rng.choice(np.arange(1, n_samples - 1), size=drop_n, replace=False)
        keep[drop_idx] = False

        ts = full_ts[keep]
        y = base[keep].copy()

        m = len(y)
        n_missing = max(3, int(m * 0.05))
        n_outlier = max(3, int(m * 0.03))

        idx = np.arange(m)
        missing_idx = rng.choice(idx, size=n_missing, replace=False)
        remaining = np.setdiff1d(idx, missing_idx)
        outlier_idx = rng.choice(remaining, size=n_outlier, replace=False)

        y[missing_idx] = np.nan
        sigma = np.nanstd(y)
        y[outlier_idx] += 6.0 * sigma

    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(ts),
            "target": y.astype(np.float64),
            # Keep this column as object dtype across pandas versions.
            "scenario": np.full(len(y), scenario, dtype=object),
        }
    )


@pytest.mark.parametrize("scenario", ["S1", "S2", "S3"])
def test_synthetic_s1_s2_s3_generation_success(scenario: str):
    df = _build_synthetic_scenario(scenario=scenario, n_samples=240, seed=123)

    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0
    assert set(df["scenario"].unique()) == {scenario}


@pytest.mark.parametrize("scenario", ["S1", "S2", "S3"])
def test_synthetic_required_columns_shape_and_types(scenario: str):
    n_samples = 240
    df = _build_synthetic_scenario(scenario=scenario, n_samples=n_samples, seed=42)

    # required column contract
    assert list(df.columns) == ["timestamp", "target", "scenario"]

    # dtype contract
    assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])
    assert pd.api.types.is_float_dtype(df["target"])
    assert pd.api.types.is_object_dtype(df["scenario"]) or pd.api.types.is_string_dtype(df["scenario"])

    # shape / monotonicity / uniqueness contract
    assert len(df) <= n_samples  # S3 may be shorter due to dropped timestamps
    assert df["timestamp"].is_monotonic_increasing
    assert not df["timestamp"].duplicated().any()


def test_s2_injects_missing_and_outliers():
    df = _build_synthetic_scenario(scenario="S2", n_samples=300, seed=7)

    missing_ratio = float(df["target"].isna().mean())
    assert missing_ratio > 0.0

    s = df["target"].dropna()
    q1, q3 = np.quantile(s, [0.25, 0.75])
    iqr = q3 - q1
    upper = q3 + 1.5 * iqr
    lower = q1 - 1.5 * iqr
    outlier_count = int(((s > upper) | (s < lower)).sum())

    assert outlier_count > 0, "S2 should contain injected outliers"


def test_s3_injects_missing_outliers_and_irregular_sampling():
    df = _build_synthetic_scenario(scenario="S3", n_samples=300, seed=11)

    # Missing exists
    assert df["target"].isna().any()

    # Outlier exists
    s = df["target"].dropna()
    z = (s - s.mean()) / (s.std(ddof=0) + 1e-8)
    assert (np.abs(z) > 3.0).any(), "S3 should contain strong outliers"

    # Irregular sampling exists (non-constant timestamp deltas)
    deltas = df["timestamp"].diff().dropna().dt.total_seconds().to_numpy()
    assert deltas.size > 0
    assert len(np.unique(deltas)) > 1, "S3 should contain irregular sampling intervals"


def test_seed_reproducibility_same_seed_same_output_and_different_seed_changes():
    df_a = _build_synthetic_scenario("S3", n_samples=200, seed=99)
    df_b = _build_synthetic_scenario("S3", n_samples=200, seed=99)
    df_c = _build_synthetic_scenario("S3", n_samples=200, seed=100)

    pd.testing.assert_frame_equal(df_a, df_b)

    # Different seed should alter at least one value (timestamp drop pattern and/or target values)
    assert not df_a.equals(df_c)
