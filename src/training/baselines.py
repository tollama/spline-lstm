"""Simple baseline forecasters and comparison helpers for Phase 3."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import numpy as np


class Phase3BaselineComparisonError(ValueError):
    """Raised when Phase 3 baseline comparison contract is invalid."""


@dataclass
class BaselineResult:
    name: str
    metrics: Dict[str, float]


def _compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    y_true = np.asarray(y_true, dtype=np.float32).reshape(-1)
    y_pred = np.asarray(y_pred, dtype=np.float32).reshape(-1)

    mae = np.mean(np.abs(y_true - y_pred))
    mse = np.mean((y_true - y_pred) ** 2)
    rmse = np.sqrt(mse)

    mask = y_true != 0
    mape = np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100 if np.any(mask) else np.inf

    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    r2 = 1 - (ss_res / (ss_tot + 1e-8))

    return {
        "mae": float(mae),
        "mse": float(mse),
        "rmse": float(rmse),
        "mape": float(mape),
        "r2": float(r2),
    }


def _validate_phase3_baseline_report(report: Dict[str, Any]) -> None:
    """Validate Phase 3 baseline comparison contract in one place.

    Hard-fails on malformed/non-finite RMSE values because Phase 3 requires
    strict model-vs-baseline comparability.
    """
    try:
        metrics = report["metrics"]
        model_rmse = metrics["model"]["rmse"]
        naive_rmse = metrics["baseline"]["naive"]["rmse"]
        ma_rmse = metrics["baseline"]["ma"]["rmse"]
        _ = metrics["delta_vs_baseline"]["naive"]["rmse_improvement_pct"]
        _ = metrics["delta_vs_baseline"]["ma"]["rmse_improvement_pct"]
    except Exception as exc:  # pragma: no cover - defensive
        raise Phase3BaselineComparisonError("phase3 baseline comparison invalid: missing required keys") from exc

    for name, value in {
        "model.rmse": model_rmse,
        "baseline.naive.rmse": naive_rmse,
        "baseline.ma.rmse": ma_rmse,
    }.items():
        if not np.isfinite(float(value)) or float(value) < 0:
            raise Phase3BaselineComparisonError(
                f"phase3 baseline comparison invalid: non-finite/negative {name}={value}"
            )


def naive_last_value_predict(X_test: np.ndarray, horizon: int = 1) -> np.ndarray:
    """Predict by repeating each window's last observed value."""
    last_values = X_test[:, -1, 0]
    return np.repeat(last_values.reshape(-1, 1), repeats=horizon, axis=1)


def moving_average_predict(X_test: np.ndarray, horizon: int = 1, window: int = 3) -> np.ndarray:
    """Predict by repeating the moving average of the final `window` values in each window."""
    if window <= 0:
        raise ValueError("window must be >= 1")
    eff_window = min(window, X_test.shape[1])
    ma_values = np.mean(X_test[:, -eff_window:, 0], axis=1)
    return np.repeat(ma_values.reshape(-1, 1), repeats=horizon, axis=1)


def build_baseline_report(
    y_true: np.ndarray,
    y_lstm: np.ndarray,
    X_test: np.ndarray,
    horizon: int = 1,
    ma_window: int | None = None,
) -> Dict:
    """Compute baseline predictions + metrics and relative improvement vs LSTM."""
    y_true_2d = np.asarray(y_true, dtype=np.float32).reshape(-1, horizon)
    y_lstm_2d = np.asarray(y_lstm, dtype=np.float32).reshape(-1, horizon)

    ma_w = int(ma_window or X_test.shape[1])
    naive_pred = naive_last_value_predict(X_test, horizon=horizon)
    ma_pred = moving_average_predict(X_test, horizon=horizon, window=ma_w)

    lstm_metrics = _compute_metrics(y_true_2d, y_lstm_2d)
    naive_metrics = _compute_metrics(y_true_2d, naive_pred)
    ma_metrics = _compute_metrics(y_true_2d, ma_pred)

    def _improve(baseline_rmse: float) -> float:
        return float((baseline_rmse - lstm_metrics["rmse"]) / (baseline_rmse + 1e-8) * 100.0)

    improve_naive = _improve(naive_metrics["rmse"])
    improve_ma = _improve(ma_metrics["rmse"])

    report = {
        # legacy keys
        "lstm": lstm_metrics,
        "naive_last": naive_metrics,
        f"moving_average_{ma_w}": {"window": ma_w, **ma_metrics},
        "relative_improvement_rmse_pct": {
            "vs_naive_last": improve_naive,
            f"vs_moving_average_{ma_w}": improve_ma,
        },
        # phase3 contract keys
        "metrics": {
            "model": lstm_metrics,
            "baseline": {
                "naive": naive_metrics,
                "ma": {"window": ma_w, **ma_metrics},
            },
            "delta_vs_baseline": {
                "naive": {"rmse_improvement_pct": improve_naive},
                "ma": {"rmse_improvement_pct": improve_ma},
            },
        },
    }
    _validate_phase3_baseline_report(report)
    return report
