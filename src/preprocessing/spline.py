"""Spline-based preprocessing for time series.

Data contract (MVP):
- Input series: 1D array-like [time]
- Window output X: [batch, lookback, 1]
- Label output y: [batch, horizon]
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from scipy import interpolate
from scipy.signal import savgol_filter

logger = logging.getLogger(__name__)


class SplinePreprocessor:
    """B-Spline based preprocessor for time series smoothing and interpolation.

    Parameters
    ----------
    degree : int
        Spline polynomial degree (1–3).  Automatically reduced when there is
        insufficient data.
    smoothing_factor : float
        Controls how closely the spline follows the data points.  Must be ≥ 0.

        Internally this maps to the ``s`` parameter of
        :class:`scipy.interpolate.UnivariateSpline` as::

            s = smoothing_factor * n_valid_points

        where ``n_valid_points`` is the number of non-NaN data points.

        Practical guide (assuming moderate-variance, pre-smoothed data):

        - ``0.0`` → interpolating spline (passes through every point, no smoothing).
        - ``0.5`` → moderate noise reduction while preserving trend & seasonality (default).
        - ``1.0`` → heavy smoothing; retains only the broad trend.
        - ``> 1.0`` → aggressive smoothing; use with care.

        .. note::
            Because ``s`` scales with ``n``, larger datasets receive
            proportionally more smoothing for the same ``smoothing_factor``.
            If your series has unusually high amplitude variance you may need to
            lower this value, and vice-versa.
    num_knots : int
        Maximum number of interior knots (budget) for adaptive/uniform strategies.
    knot_strategy : str
        ``"auto"`` (scipy default), ``"curvature"`` (adaptive placement based
        on second-derivative density), or ``"uniform"`` (evenly spaced knots).
    smoothing_method : str
        ``"legacy"`` uses UnivariateSpline + optional Savitzky-Golay.
        ``"pspline"`` uses ``scipy.interpolate.make_smoothing_spline`` for
        integrated penalised B-spline smoothing (requires scipy >= 1.11).
    """

    KNOT_STRATEGIES = ("auto", "curvature", "uniform")
    SMOOTHING_METHODS = ("legacy", "pspline")

    def __init__(
        self,
        degree: int = 3,
        smoothing_factor: float = 0.5,
        num_knots: int = 10,
        knot_strategy: str = "auto",
        smoothing_method: str = "legacy",
    ):
        if smoothing_factor < 0:
            raise ValueError(f"smoothing_factor must be >= 0, got {smoothing_factor}")
        if knot_strategy not in self.KNOT_STRATEGIES:
            raise ValueError(f"knot_strategy must be one of {self.KNOT_STRATEGIES}, got {knot_strategy!r}")
        if smoothing_method not in self.SMOOTHING_METHODS:
            raise ValueError(f"smoothing_method must be one of {self.SMOOTHING_METHODS}, got {smoothing_method!r}")
        self.degree = degree
        self.smoothing_factor = smoothing_factor
        self.num_knots = num_knots
        self.knot_strategy = knot_strategy
        self.smoothing_method = smoothing_method
        self._spline: Any = None
        self._fitted = False

    @staticmethod
    def _to_1d_float_array(arr: np.ndarray, name: str) -> np.ndarray:
        a = np.asarray(arr, dtype=float)
        if a.ndim != 1:
            raise ValueError(f"{name} must be 1D, got shape={a.shape}")
        if a.size == 0:
            raise ValueError(f"{name} must be non-empty")
        return a

    @staticmethod
    def _validate_contract_shapes(X: np.ndarray, y: np.ndarray, lookback: int, horizon: int) -> None:
        if X.ndim != 3:
            raise ValueError(f"X must be 3D [batch, lookback, 1], got shape={X.shape}")
        if y.ndim != 2:
            raise ValueError(f"y must be 2D [batch, horizon], got shape={y.shape}")
        if X.shape[1] != lookback or X.shape[2] != 1:
            raise ValueError(f"X contract violated: expected [batch, {lookback}, 1], got {X.shape}")
        if y.shape[1] != horizon:
            raise ValueError(f"y contract violated: expected [batch, {horizon}], got {y.shape}")
        if X.shape[0] != y.shape[0]:
            raise ValueError("X and y batch size must match")

    @staticmethod
    def _select_knots_uniform(x: np.ndarray, max_knots: int) -> np.ndarray:
        """Place knots evenly across the data range (interior only)."""
        n_knots = min(max_knots, len(x) - 2)
        if n_knots <= 0:
            return np.array([], dtype=float)
        return np.linspace(x[0], x[-1], n_knots + 2)[1:-1]  # type: ignore[no-any-return]

    @staticmethod
    def _select_knots_curvature(x: np.ndarray, y: np.ndarray, max_knots: int, degree: int) -> np.ndarray:
        """Place knots based on curvature density (more knots where signal bends).

        Uses a rough uniform spline to estimate second derivatives, then
        concentrates knots in regions of high curvature via inverse-CDF sampling.
        """
        n_knots = min(max_knots, len(x) - 2)
        if n_knots <= 0 or len(x) < 5:
            return np.linspace(x[0], x[-1], max(n_knots, 0) + 2)[1:-1] if n_knots > 0 else np.array([], dtype=float)

        # Rough spline for curvature estimation
        try:
            rough = interpolate.UnivariateSpline(x, y, k=min(degree, 3), s=len(x))
            d2 = np.abs(rough.derivative(2)(x))
        except Exception:
            # Fallback to finite differences
            d2 = np.abs(np.gradient(np.gradient(y, x), x))

        # Curvature density with a small floor to avoid all-zero
        density = d2 + 1e-10
        cdf = np.cumsum(density)
        cdf /= cdf[-1]

        # Inverse-CDF sampling for knot locations
        quantiles = np.linspace(0, 1, n_knots + 2)[1:-1]
        knot_positions = np.interp(quantiles, cdf, x)

        # Ensure knots are strictly inside the data range
        eps = (x[-1] - x[0]) * 1e-6
        knot_positions = np.clip(knot_positions, x[0] + eps, x[-1] - eps)
        return np.unique(knot_positions)  # type: ignore[no-any-return]

    def fit(self, x: np.ndarray, y: np.ndarray) -> SplinePreprocessor:
        """Fit spline to data."""
        x = self._to_1d_float_array(x, "x")
        y = self._to_1d_float_array(y, "y")

        if len(x) != len(y):
            raise ValueError("x and y must have same length")
        if np.isnan(x).any() or np.isinf(x).any():
            raise ValueError("x contains NaN/Inf")

        valid_mask = ~(np.isnan(y) | np.isinf(y))
        x_valid = x[valid_mask]
        y_valid = y[valid_mask]

        if len(x_valid) < 2:
            raise ValueError("at least 2 valid y points are required for interpolation")

        # Interpolation functions require strictly increasing x.
        if np.any(np.diff(x_valid) <= 0):
            raise ValueError("x must be strictly increasing")

        degree = min(self.degree, 3)
        if len(x_valid) <= degree:
            degree = 1
            logger.warning("Insufficient data for high-degree spline, using linear")

        try:
            # P-spline path: single integrated smoothing (WI-7)
            if self.smoothing_method == "pspline" and len(x_valid) > degree + 1:
                try:
                    self._spline = interpolate.make_smoothing_spline(x_valid, y_valid)
                    self._fitted = True
                    logger.info("Fitted P-spline (make_smoothing_spline)")
                    return self
                except Exception as e:
                    logger.warning("P-spline failed (%s), falling back to legacy", e)

            # Adaptive / uniform knot strategies → use LSQUnivariateSpline (WI-6)
            if self.knot_strategy in ("curvature", "uniform") and len(x_valid) > degree + 2:
                if self.knot_strategy == "curvature":
                    knots = self._select_knots_curvature(x_valid, y_valid, self.num_knots, degree)
                else:
                    knots = self._select_knots_uniform(x_valid, self.num_knots)

                # LSQUnivariateSpline needs at least 1 interior knot
                if len(knots) > 0:
                    try:
                        self._spline = interpolate.LSQUnivariateSpline(
                            x_valid,
                            y_valid,
                            t=knots,
                            k=degree,
                        )
                        self._fitted = True
                        logger.info(
                            "Fitted %s-degree LSQ spline with %d %s knots", degree, len(knots), self.knot_strategy
                        )
                        return self
                    except Exception as e:
                        logger.warning("LSQ spline failed (%s), falling back to auto", e)

            # Legacy auto path: UnivariateSpline or interp1d
            if self.smoothing_factor > 0 and len(x_valid) > degree:
                self._spline = interpolate.UnivariateSpline(
                    x_valid,
                    y_valid,
                    k=degree,
                    s=self.smoothing_factor * len(x_valid),
                )
            else:
                self._spline = interpolate.interp1d(
                    x_valid,
                    y_valid,
                    kind="cubic" if degree >= 3 and len(x_valid) > 3 else "linear",
                    fill_value="extrapolate",
                    assume_sorted=True,
                )
            self._fitted = True
            logger.info("Fitted %s-degree spline", degree)
        except Exception as e:
            logger.error("Spline fitting failed: %s; fallback to linear interpolation", e)
            self._spline = interpolate.interp1d(
                x_valid,
                y_valid,
                kind="linear",
                fill_value="extrapolate",
                assume_sorted=True,
            )
            self._fitted = True

        return self

    def transform(self, x: np.ndarray) -> np.ndarray:
        """Transform data using fitted spline."""
        if not self._fitted:
            raise RuntimeError("Spline not fitted. Call fit() first.")
        x = self._to_1d_float_array(x, "x")
        return np.asarray(self._spline(x), dtype=float)

    def fit_transform(self, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        """Fit and transform in one step."""
        return self.fit(x, y).transform(x)

    def interpolate_missing(
        self,
        y: np.ndarray,
        missing_mask: np.ndarray | None = None,
    ) -> np.ndarray:
        """Interpolate missing values (NaN)."""
        y = self._to_1d_float_array(y, "y").copy()

        if missing_mask is None:
            missing_mask = np.isnan(y)
        else:
            missing_mask = np.asarray(missing_mask, dtype=bool)
            if missing_mask.shape != y.shape:
                raise ValueError(f"missing_mask must match y shape {y.shape}, got {missing_mask.shape}")

        # No missing values: return equivalent array without fitting/interpolating.
        if not missing_mask.any():
            return y

        x = np.arange(len(y), dtype=float)
        valid_mask = ~missing_mask

        if valid_mask.sum() < 2:
            logger.warning("Not enough valid points for interpolation")
            return y

        self.fit(x[valid_mask], y[valid_mask])
        y[missing_mask] = self.transform(x[missing_mask])

        return y

    def smooth(self, y: np.ndarray, window: int = 5) -> np.ndarray:
        """Smooth noisy data.

        When ``smoothing_method="pspline"``, smoothing is already handled by
        the P-spline fit, so this method returns the input unchanged.
        """
        y = self._to_1d_float_array(y, "y")
        if self.smoothing_method == "pspline":
            return y
        if window < 3:
            return y
        if window % 2 == 0:
            window += 1
        if len(y) <= window:
            return y
        polyorder = min(3, window - 1)
        return np.asarray(savgol_filter(y, window, polyorder), dtype=float)

    def extrapolate(self, x_future: np.ndarray) -> np.ndarray:
        """Evaluate the fitted spline at future x-positions (extrapolation).

        Useful for residual learning: the spline provides a trend forecast and
        the LSTM models only the residual.
        """
        if not self._fitted:
            raise RuntimeError("Spline not fitted. Call fit() first.")
        x_future = self._to_1d_float_array(x_future, "x_future")
        return np.asarray(self._spline(x_future), dtype=float)

    def evaluate_derivatives(self, x: np.ndarray, order: int = 1) -> np.ndarray:
        """Evaluate spline derivative of given order at positions x.

        Returns zeros if the fitted spline does not support derivatives
        (e.g. linear interp1d fallback).
        """
        if not self._fitted:
            raise RuntimeError("Spline not fitted. Call fit() first.")
        x = self._to_1d_float_array(x, "x")
        if hasattr(self._spline, "derivative"):
            return np.asarray(self._spline.derivative(order)(x), dtype=float)
        # Fallback: numerical differencing
        eps = 1e-6
        if order == 1:
            return np.asarray((self._spline(x + eps) - self._spline(x - eps)) / (2 * eps), dtype=float)
        if order == 2:
            return np.asarray(
                (self._spline(x + eps) - 2 * self._spline(x) + self._spline(x - eps)) / (eps**2), dtype=float
            )
        return np.zeros_like(x, dtype=float)

    def compute_residuals(self, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        """Compute residuals: y - spline(x).

        The spline must be fitted before calling this method.
        """
        if not self._fitted:
            raise RuntimeError("Spline not fitted. Call fit() first.")
        x = self._to_1d_float_array(x, "x")
        y = self._to_1d_float_array(y, "y")
        return y - np.asarray(self._spline(x), dtype=float)  # type: ignore[no-any-return]

    def extract_features(self, y: np.ndarray) -> dict:
        """Extract simple features from a spline fitted to *y*.

        This method does **not** modify the preprocessor's internal state.
        A temporary ``SplinePreprocessor`` is used for the transient fit so
        that any previously fitted spline is preserved.
        """
        y = self._to_1d_float_array(y, "y")
        x = np.arange(len(y), dtype=float)

        # Use a throw-away instance to avoid overwriting the fitted spline.
        tmp = SplinePreprocessor(
            degree=self.degree,
            smoothing_factor=self.smoothing_factor,
            num_knots=self.num_knots,
            knot_strategy=self.knot_strategy,
            smoothing_method=self.smoothing_method,
        )
        tmp.fit(x, y)

        features = {
            "mean": float(np.mean(y)),
            "std": float(np.std(y)),
            "min": float(np.min(y)),
            "max": float(np.max(y)),
        }

        if hasattr(tmp._spline, "derivative"):
            dy = tmp._spline.derivative(1)(x)
            features["trend_mean"] = float(np.mean(dy))
            features["trend_std"] = float(np.std(dy))

        return features

    def to_supervised(
        self,
        y: np.ndarray,
        lookback: int,
        horizon: int = 1,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Create supervised windows following MVP contract.

        Returns:
            X: [batch, lookback, 1]
            y: [batch, horizon]
        """
        series = self._to_1d_float_array(y, "y")
        if np.isnan(series).any() or np.isinf(series).any():
            raise ValueError("y contains NaN/Inf; interpolate or clean before windowing")
        if lookback <= 0 or horizon <= 0:
            raise ValueError("lookback and horizon must be positive")

        n = len(series) - lookback - horizon + 1
        if n <= 0:
            raise ValueError(f"not enough points ({len(series)}) for lookback={lookback}, horizon={horizon}")

        X = np.zeros((n, lookback, 1), dtype=np.float32)
        target = np.zeros((n, horizon), dtype=np.float32)

        for i in range(n):
            X[i, :, 0] = series[i : i + lookback]
            target[i, :] = series[i + lookback : i + lookback + horizon]

        self._validate_contract_shapes(X, target, lookback, horizon)
        return X, target
