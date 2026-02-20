"""Data contract tests for Spline-LSTM MVP Phase 1.

Covers schema/type/shape guarantees for preprocessing + model input contracts.
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from preprocessing.spline import SplinePreprocessor
from models.lstm import LSTMModel


class TestSupervisedDataContract:
    def test_to_supervised_schema_shape_and_type(self):
        # synthetic univariate series
        y = np.linspace(0, 1, 20, dtype=np.float32)

        pre = SplinePreprocessor()
        X, target = pre.to_supervised(y, lookback=5, horizon=3)

        # shape contract
        assert X.shape == (13, 5, 1)
        assert target.shape == (13, 3)

        # type/schema contract: numpy arrays of numeric dtype
        assert isinstance(X, np.ndarray)
        assert isinstance(target, np.ndarray)
        assert np.issubdtype(X.dtype, np.floating)
        assert np.issubdtype(target.dtype, np.floating)

    def test_to_supervised_rejects_nan_inf(self):
        pre = SplinePreprocessor()

        with pytest.raises(ValueError, match="contains NaN/Inf"):
            pre.to_supervised(np.array([1.0, 2.0, np.nan, 4.0]), lookback=2, horizon=1)

        with pytest.raises(ValueError, match="contains NaN/Inf"):
            pre.to_supervised(np.array([1.0, 2.0, np.inf, 4.0]), lookback=2, horizon=1)

    def test_to_supervised_rejects_invalid_params_or_short_series(self):
        pre = SplinePreprocessor()

        with pytest.raises(ValueError, match="must be positive"):
            pre.to_supervised(np.arange(10, dtype=float), lookback=0, horizon=1)

        with pytest.raises(ValueError, match="must be positive"):
            pre.to_supervised(np.arange(10, dtype=float), lookback=3, horizon=0)

        with pytest.raises(ValueError, match="not enough points"):
            pre.to_supervised(np.arange(5, dtype=float), lookback=4, horizon=2)


class TestLSTMInputContract:
    def test_validate_xy_accepts_contract_shape(self):
        model = LSTMModel(sequence_length=4, output_units=2)
        X = np.random.randn(8, 4, 1).astype(np.float32)
        y = np.random.randn(8, 2).astype(np.float32)

        # Private method is used intentionally for strict contract checks without backend dependency.
        model._validate_xy(X, y)

    def test_validate_xy_rejects_shape_mismatch(self):
        model = LSTMModel(sequence_length=4, output_units=2)

        X_bad_lookback = np.random.randn(8, 3, 1).astype(np.float32)
        y = np.random.randn(8, 2).astype(np.float32)
        with pytest.raises(ValueError, match="lookback mismatch"):
            model._validate_xy(X_bad_lookback, y)

        X_bad_feature = np.random.randn(8, 4, 2).astype(np.float32)
        with pytest.raises(ValueError, match="input feature mismatch"):
            model._validate_xy(X_bad_feature, y)

        X = np.random.randn(8, 4, 1).astype(np.float32)
        y_bad_out = np.random.randn(8, 1).astype(np.float32)
        with pytest.raises(ValueError, match="output width mismatch"):
            model._validate_xy(X, y_bad_out)
