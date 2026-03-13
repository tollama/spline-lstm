from __future__ import annotations

import math
from typing import Any


def _as_numeric_list(value: Any) -> list[float]:
    out: list[float] = []
    if isinstance(value, (int, float)):
        out.append(float(value))
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, (int, float)):
                out.append(float(item))
    elif isinstance(value, dict):
        for item in value.values():
            out.extend(_as_numeric_list(item))
    return out


def build_forecast_explanation(
    *,
    run_id: str,
    base_inputs: dict[str, Any],
    inference_result: dict[str, Any],
) -> dict[str, Any]:
    history = _as_numeric_list(base_inputs.get("target_history", []))
    predictions = [
        float(item)
        for item in inference_result.get("predictions", [])
        if isinstance(item, (int, float))
    ]
    known_future_covariates = base_inputs.get("known_future_covariates", {})
    static_covariates = base_inputs.get("static_covariates", {})

    temporal_importance = _build_temporal_importance(history)
    covariate_importance = _build_covariate_importance(
        known_future_covariates=known_future_covariates,
        static_covariates=static_covariates,
        history=history,
    )
    decomposition = _build_forecast_decomposition(
        history=history,
        predictions=predictions,
    )
    runtime_trace = {
        "runtime_used": inference_result.get("runtime_used"),
        "fallback_used": bool(inference_result.get("fallback_used")),
        "fallback_chain": inference_result.get("fallback_chain", []),
        "attempts": inference_result.get("attempts", []),
    }

    return {
        "run_id": run_id,
        "summary": _summary(
            history=history,
            predictions=predictions,
            decomposition=decomposition,
        ),
        "temporal_importance": temporal_importance,
        "covariate_importance": covariate_importance,
        "forecast_decomposition": decomposition,
        "runtime_trace": runtime_trace,
    }


def _build_temporal_importance(history: list[float], top_k: int = 8) -> list[dict[str, Any]]:
    if not history:
        return []

    n = len(history)
    diffs = [0.0]
    for idx in range(1, n):
        diffs.append(abs(history[idx] - history[idx - 1]))

    center = sum(history) / len(history)
    magnitudes = [abs(value - center) for value in history]
    diff_max = max(diffs) or 1.0
    mag_max = max(magnitudes) or 1.0

    scores: list[float] = []
    for idx, (diff, magnitude) in enumerate(zip(diffs, magnitudes, strict=True)):
        recency = (idx + 1) / n
        scores.append(0.45 * recency + 0.35 * (diff / diff_max) + 0.20 * (magnitude / mag_max))

    score_max = max(scores) or 1.0
    normalized = [score / score_max for score in scores]
    keep = sorted(range(n), key=lambda idx: normalized[idx], reverse=True)[
        : max(1, min(top_k, n))
    ]
    keep = sorted(keep)

    out: list[dict[str, Any]] = []
    for idx in keep:
        lag = n - idx
        reason = (
            "recent point with above-baseline local movement"
            if normalized[idx] >= 0.75
            else "point contributed through recency and deviation"
        )
        out.append(
            {
                "lag": lag,
                "index": idx,
                "value": round(history[idx], 6),
                "importance": round(normalized[idx], 4),
                "reason": reason,
            }
        )
    return out


def _build_covariate_importance(
    *,
    known_future_covariates: Any,
    static_covariates: Any,
    history: list[float],
) -> list[dict[str, Any]]:
    scale = abs(sum(history) / len(history)) if history else 1.0
    scale = scale if scale > 0 else 1.0

    rows: list[dict[str, Any]] = []
    for group_name, payload in (
        ("known_future_covariates", known_future_covariates),
        ("static_covariates", static_covariates),
    ):
        if not isinstance(payload, dict):
            continue
        for name, value in payload.items():
            numbers = _as_numeric_list(value)
            if not numbers:
                continue
            mean_value = sum(numbers) / len(numbers)
            strength = min(1.0, abs(mean_value) / scale)
            sign = "positive" if mean_value > 0 else "negative" if mean_value < 0 else "neutral"
            rows.append(
                {
                    "group": group_name,
                    "name": str(name),
                    "mean_value": round(mean_value, 6),
                    "importance": round(strength, 4),
                    "sign": sign,
                    "reason": f"{group_name}.{name} shifted the naive baseline by relative magnitude {strength:.2f}",
                }
            )
    rows.sort(key=lambda item: item["importance"], reverse=True)
    return rows[:10]


def _build_forecast_decomposition(*, history: list[float], predictions: list[float]) -> dict[str, Any]:
    trend_strength = abs((predictions[-1] if predictions else 0.0) - (history[-1] if history else 0.0))
    seasonal_strength = _seasonality_strength(history)
    residual_strength = _volatility_strength(history)
    total = trend_strength + seasonal_strength + residual_strength
    if total <= 0:
        shares = (0.34, 0.33, 0.33)
    else:
        shares = (
            trend_strength / total,
            seasonal_strength / total,
            residual_strength / total,
        )

    parts = {
        "trend": round(shares[0], 4),
        "seasonal": round(shares[1], 4),
        "residual": round(shares[2], 4),
    }
    parts["dominant_driver"] = max(parts, key=parts.get)
    return parts


def _seasonality_strength(history: list[float]) -> float:
    if len(history) < 6:
        return 0.0
    best = 0.0
    for lag in (7, 12, 24, 30):
        if len(history) < lag * 2:
            continue
        left = history[:-lag]
        right = history[lag:]
        corr = _correlation(left, right)
        best = max(best, max(0.0, corr))
    return best


def _volatility_strength(history: list[float]) -> float:
    if len(history) < 3:
        return 0.0
    diffs = [history[i] - history[i - 1] for i in range(1, len(history))]
    mean = sum(diffs) / len(diffs)
    variance = sum((item - mean) ** 2 for item in diffs) / len(diffs)
    return math.sqrt(variance)


def _correlation(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or len(left) < 2:
        return 0.0
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right, strict=True))
    left_var = sum((a - left_mean) ** 2 for a in left)
    right_var = sum((b - right_mean) ** 2 for b in right)
    denom = math.sqrt(left_var * right_var)
    return numerator / denom if denom > 0 else 0.0


def _summary(*, history: list[float], predictions: list[float], decomposition: dict[str, Any]) -> str:
    if not predictions:
        return "no predictions were returned; explanation is based on inputs only"
    baseline = history[-1] if history else 0.0
    delta = predictions[-1] - baseline
    direction = "up" if delta > 0 else "down" if delta < 0 else "flat"
    return (
        f"forecast ended {direction} relative to the latest observed point; "
        f"dominant driver={decomposition.get('dominant_driver')}"
    )
