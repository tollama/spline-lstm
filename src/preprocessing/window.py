"""Window generation utilities."""

from __future__ import annotations

from typing import Tuple

import numpy as np


def make_windows(series: np.ndarray, lookback: int, horizon: int = 1) -> Tuple[np.ndarray, np.ndarray]:
    """Create supervised windows.

    Returns:
        X: [batch, lookback, 1]
        y: [batch, horizon]
    """
    s = np.asarray(series, dtype=float)
    if s.ndim != 1:
        raise ValueError(f"series must be 1D, got {s.shape}")
    if np.isnan(s).any() or np.isinf(s).any():
        raise ValueError("series contains NaN/Inf")
    if lookback <= 0 or horizon <= 0:
        raise ValueError("lookback and horizon must be positive")

    n = len(s) - lookback - horizon + 1
    if n <= 0:
        raise ValueError("not enough points for windowing")

    X = np.zeros((n, lookback, 1), dtype=np.float32)
    y = np.zeros((n, horizon), dtype=np.float32)

    for i in range(n):
        X[i, :, 0] = s[i : i + lookback]
        y[i, :] = s[i + lookback : i + lookback + horizon]

    return X, y


def make_windows_multivariate(
    features: np.ndarray,
    target: np.ndarray,
    lookback: int,
    horizon: int = 1,
) -> Tuple[np.ndarray, np.ndarray]:
    """Create windows for multivariate inputs with target-only labels.

    Args:
        features: [time, n_features] matrix (target + covariates).
        target: [time] target series.

    Returns:
        X: [batch, lookback, n_features]
        y: [batch, horizon]
    """
    f = np.asarray(features, dtype=float)
    t = np.asarray(target, dtype=float).reshape(-1)

    if f.ndim != 2:
        raise ValueError(f"features must be 2D [time, n_features], got {f.shape}")
    if len(f) != len(t):
        raise ValueError("features and target must have same time length")
    if np.isnan(f).any() or np.isinf(f).any() or np.isnan(t).any() or np.isinf(t).any():
        raise ValueError("features/target contains NaN/Inf")
    if lookback <= 0 or horizon <= 0:
        raise ValueError("lookback and horizon must be positive")

    n = len(t) - lookback - horizon + 1
    if n <= 0:
        raise ValueError("not enough points for windowing")

    X = np.zeros((n, lookback, f.shape[1]), dtype=np.float32)
    y = np.zeros((n, horizon), dtype=np.float32)

    for i in range(n):
        X[i, :, :] = f[i : i + lookback, :]
        y[i, :] = t[i + lookback : i + lookback + horizon]

    return X, y
