from __future__ import annotations

import numpy as np

import pytest

from src.training.baselines import Phase3BaselineComparisonError, build_baseline_report


def test_baseline_report_includes_phase3_contract_keys_and_ma_window():
    x_test = np.array(
        [
            [[1.0], [2.0], [3.0], [4.0]],
            [[2.0], [3.0], [4.0], [5.0]],
        ],
        dtype=np.float32,
    )
    y_true = np.array([[4.5], [5.5]], dtype=np.float32)
    y_lstm = np.array([[4.4], [5.4]], dtype=np.float32)

    out = build_baseline_report(y_true=y_true, y_lstm=y_lstm, X_test=x_test, horizon=1, ma_window=2)

    assert "metrics" in out
    assert out["metrics"]["baseline"]["ma"]["window"] == 2
    assert "naive" in out["metrics"]["baseline"]
    assert "delta_vs_baseline" in out["metrics"]
    assert "rmse_improvement_pct" in out["metrics"]["delta_vs_baseline"]["naive"]

    # legacy compatibility keys kept
    assert "naive_last" in out
    assert "moving_average_2" in out


def test_phase3_baseline_report_hard_fails_on_non_finite_rmse():
    x_test = np.array([[[1.0], [2.0], [3.0]]], dtype=np.float32)
    y_true = np.array([[1.0]], dtype=np.float32)
    y_lstm = np.array([[np.nan]], dtype=np.float32)

    with pytest.raises(Phase3BaselineComparisonError, match="phase3 baseline comparison invalid"):
        build_baseline_report(y_true=y_true, y_lstm=y_lstm, X_test=x_test, horizon=1)
