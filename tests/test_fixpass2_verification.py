"""Verification tests for Phase2 FixPass2 requirements."""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from preprocessing.spline import SplinePreprocessor


def test_interpolate_missing_no_missing_input_no_exception_and_identity():
    """No-missing input should not raise and should preserve values."""
    y = np.array([0.1, 1.2, 2.3, 3.4, 4.5], dtype=float)

    pre = SplinePreprocessor()
    y_out = pre.interpolate_missing(y)

    assert y_out.shape == y.shape
    assert np.allclose(y_out, y)
    assert np.isfinite(y_out).all()
