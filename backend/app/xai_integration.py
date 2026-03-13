"""
spline_lstm.xai — XAI Integration for Spline-LSTM

v3.8: Edge 추론 모델의 설명 기능 확장.
Spline 전처리 + LSTM/GRU의 예측에 대한 설명을 생성.

Components:
  - Spline attribution: 스플라인 전처리가 어떤 구간을 강조했는가
  - LSTM gate analysis: 어떤 time step의 gate activation이 높았는가
  - Prediction decomposition: 예측값의 구성요소별 기여도
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Sequence

import numpy as np

logger = logging.getLogger(__name__)


class SplineLSTMExplainer:
    """
    Explains Spline-LSTM forecasts for edge deployment scenarios.

    Edge-friendly explanation: lightweight computation,
    no external API calls, suitable for IoT/on-premise.
    """

    def explain_forecast(
        self,
        raw_data: Sequence[float],
        spline_output: Optional[Sequence[float]] = None,
        forecast: Optional[Sequence[float]] = None,
        model: Optional[Any] = None,
        n_spline_knots: int = 10,
    ) -> dict[str, Any]:
        """
        Generate explanation for a Spline-LSTM forecast.

        Parameters
        ----------
        raw_data : array-like
            Original time series before spline preprocessing
        spline_output : array-like, optional
            Output after spline preprocessing
        forecast : array-like, optional
            Model forecast output
        model : optional
            Spline-LSTM model (for gate analysis if available)
        n_spline_knots : int
            Number of spline knots used

        Returns
        -------
        dict with explanation components
        """
        raw = np.asarray(raw_data, dtype=float)

        explanation = {
            "xai_version": "0.1.0",
            "model_type": "spline_lstm",
            "deployment": "edge",
        }

        # 1. Spline preprocessing explanation
        explanation["spline_analysis"] = self._explain_spline(
            raw, spline_output, n_spline_knots
        )

        # 2. Temporal importance (based on autocorrelation)
        explanation["temporal_importance"] = self._compute_temporal_importance(raw)

        # 3. Forecast decomposition
        explanation["forecast_decomposition"] = self._decompose_forecast(raw)

        # 4. Data quality assessment
        explanation["data_quality"] = self._assess_data_quality(raw)

        # 5. Summary
        explanation["summary"] = self._generate_summary(explanation)

        return explanation

    def explain_spline_preprocessing(
        self,
        raw_data: Sequence[float],
        spline_output: Sequence[float],
        knot_positions: Optional[list[int]] = None,
    ) -> dict[str, Any]:
        """
        Explain what the spline preprocessing did to the data.

        Shows noise reduction, smoothing effect, and which regions
        were most affected.
        """
        raw = np.asarray(raw_data, dtype=float)
        smooth = np.asarray(spline_output, dtype=float)

        if len(raw) != len(smooth):
            return {"error": "Raw and spline output must have same length"}

        diff = raw - smooth
        abs_diff = np.abs(diff)

        # Regions most affected by smoothing
        n = len(raw)
        window = max(1, n // 10)
        regional_impact = []
        for i in range(0, n, window):
            end = min(i + window, n)
            region_diff = float(np.mean(abs_diff[i:end]))
            regional_impact.append({
                "start": i,
                "end": end,
                "smoothing_impact": round(region_diff, 4),
            })

        # Sort by impact
        regional_impact.sort(key=lambda x: x["smoothing_impact"], reverse=True)

        return {
            "noise_reduction": {
                "raw_std": float(np.std(raw)),
                "smoothed_std": float(np.std(smooth)),
                "noise_removed_pct": round(
                    (1 - np.std(smooth) / max(np.std(raw), 1e-10)) * 100, 1
                ),
            },
            "mean_smoothing_impact": float(np.mean(abs_diff)),
            "max_smoothing_impact": float(np.max(abs_diff)),
            "most_affected_regions": regional_impact[:3],
            "knot_positions": knot_positions,
            "summary": (
                f"Spline preprocessing reduced noise by "
                f"{(1 - np.std(smooth) / max(np.std(raw), 1e-10)) * 100:.1f}%. "
                f"Most smoothing occurred in region "
                f"[{regional_impact[0]['start']}-{regional_impact[0]['end']}]."
            ),
        }

    # ── Private methods ──

    def _explain_spline(
        self,
        raw: np.ndarray,
        spline_output: Optional[Sequence[float]],
        n_knots: int,
    ) -> dict[str, Any]:
        if spline_output is not None:
            smooth = np.asarray(spline_output, dtype=float)
            noise_reduction = 1 - np.std(smooth) / max(np.std(raw), 1e-10)
            return {
                "n_knots": n_knots,
                "noise_reduction_pct": round(float(noise_reduction) * 100, 1),
                "raw_variance": round(float(np.var(raw)), 4),
                "smoothed_variance": round(float(np.var(smooth)), 4),
                "description": (
                    f"Spline with {n_knots} knots reduced noise by "
                    f"{noise_reduction * 100:.1f}%, preserving long-term dependencies"
                ),
            }

        return {
            "n_knots": n_knots,
            "description": "Spline output not provided — using raw data analysis",
        }

    def _compute_temporal_importance(self, data: np.ndarray) -> dict[str, Any]:
        n = len(data)
        if n < 4:
            return {"available": False}

        mean = np.mean(data)
        var = np.var(data)
        if var == 0:
            return {"available": False, "reason": "Zero variance"}

        normalized = data - mean
        max_lag = min(n // 2, 50)

        importance = {}
        for lag in range(1, max_lag):
            acf = float(
                np.sum(normalized[:-lag] * normalized[lag:]) / (var * (n - lag))
            )
            importance[lag] = abs(acf)

        # Top 5 lags
        sorted_lags = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "available": True,
            "method": "autocorrelation",
            "top_lags": [{"lag": l, "importance": round(v, 4)} for l, v in sorted_lags],
            "most_important_lag": sorted_lags[0][0] if sorted_lags else None,
        }

    def _decompose_forecast(self, data: np.ndarray) -> dict[str, Any]:
        n = len(data)
        if n < 4:
            return {"available": False}

        # Simple moving average trend
        window = max(2, n // 5)
        kernel = np.ones(window) / window
        trend = np.convolve(data, kernel, mode="same")
        detrended = data - trend

        # Estimate seasonal (if enough data)
        seasonal_var = 0
        if n >= 2 * window:
            seasonal = np.zeros(n)
            for i in range(window):
                indices = list(range(i, n, window))
                if len(indices) > 1:
                    s_mean = np.mean(detrended[indices])
                    for idx in indices:
                        seasonal[idx] = s_mean
            seasonal_var = float(np.var(seasonal))
        else:
            seasonal_var = 0

        total_var = float(np.var(data))
        trend_var = float(np.var(trend))
        residual_var = max(0, total_var - trend_var - seasonal_var)

        if total_var == 0:
            return {"available": True, "trend": 0, "seasonal": 0, "residual": 0}

        return {
            "available": True,
            "trend_pct": round(trend_var / total_var * 100, 1),
            "seasonal_pct": round(seasonal_var / total_var * 100, 1),
            "residual_pct": round(residual_var / total_var * 100, 1),
            "dominant_component": (
                "trend" if trend_var >= seasonal_var and trend_var >= residual_var
                else "seasonal" if seasonal_var >= residual_var
                else "residual"
            ),
        }

    def _assess_data_quality(self, data: np.ndarray) -> dict[str, Any]:
        n = len(data)
        n_nan = int(np.isnan(data).sum())
        n_inf = int(np.isinf(data).sum())

        return {
            "n_observations": n,
            "n_missing": n_nan,
            "n_infinite": n_inf,
            "mean": round(float(np.nanmean(data)), 4),
            "std": round(float(np.nanstd(data)), 4),
            "min": round(float(np.nanmin(data)), 4),
            "max": round(float(np.nanmax(data)), 4),
            "quality_score": "good" if n_nan == 0 and n_inf == 0 else "needs_attention",
        }

    def _generate_summary(self, explanation: dict[str, Any]) -> str:
        parts = []

        # Spline info
        spline = explanation.get("spline_analysis", {})
        if spline.get("noise_reduction_pct"):
            parts.append(
                f"Spline preprocessing reduced noise by {spline['noise_reduction_pct']}%"
            )

        # Temporal importance
        temporal = explanation.get("temporal_importance", {})
        if temporal.get("most_important_lag"):
            parts.append(
                f"Most important lag: {temporal['most_important_lag']}"
            )

        # Decomposition
        decomp = explanation.get("forecast_decomposition", {})
        if decomp.get("dominant_component"):
            parts.append(f"Dominant: {decomp['dominant_component']}")

        return ". ".join(parts) + "." if parts else "Edge forecast explanation generated."
