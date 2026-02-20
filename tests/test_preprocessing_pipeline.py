"""Preprocessing pipeline tests for missing values and irregular timestamps.

All inputs are synthetic and deterministic.
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from preprocessing.spline import SplinePreprocessor


class TestPreprocessingPipeline:
    def test_interpolate_missing_with_internal_and_edge_nans(self):
        # synthetic series with internal + edge missing values
        y = np.array([np.nan, 1.0, 2.0, np.nan, 4.0, 5.0, np.nan, 7.0, 8.0, np.nan])

        pre = SplinePreprocessor()
        y_filled = pre.interpolate_missing(y)

        # The implementation uses index-based interpolation; with >=2 valid points it should fill all NaNs.
        assert y_filled.shape == y.shape
        assert not np.isnan(y_filled).any()

    def test_interpolate_missing_returns_equivalent_when_no_missing(self):
        y = np.array([0.5, 1.0, 1.5, 2.0, 2.5])

        pre = SplinePreprocessor()
        y_filled = pre.interpolate_missing(y)

        assert y_filled.shape == y.shape
        assert np.array_equal(y_filled, y)

    def test_irregular_timestamp_fit_and_missing_point_reconstruction(self):
        # strictly increasing but irregular timestamps
        x = np.array([0.0, 0.7, 1.4, 2.8, 3.1, 5.0, 8.2, 8.9, 10.5])
        y_full = np.sin(x) + 0.05 * x

        # remove a couple of observations
        missing_idx = np.array([3, 6])
        keep = np.ones_like(x, dtype=bool)
        keep[missing_idx] = False

        pre = SplinePreprocessor(degree=3, smoothing_factor=0.0)
        pre.fit(x[keep], y_full[keep])
        y_est = pre.transform(x[missing_idx])

        assert y_est.shape == (len(missing_idx),)
        assert np.isfinite(y_est).all()

        # reconstruction should be reasonably close for smooth synthetic signal
        mae = np.mean(np.abs(y_est - y_full[missing_idx]))
        assert mae < 0.35

    def test_fit_rejects_non_increasing_timestamps(self):
        x_bad = np.array([0.0, 1.0, 0.5, 2.0])
        y = np.array([1.0, 1.2, 1.1, 1.5])

        pre = SplinePreprocessor()
        with pytest.raises(ValueError, match="strictly increasing"):
            pre.fit(x_bad, y)
