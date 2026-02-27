from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from backend.app.config import ARTIFACTS_DIR
from backend.app.runtime import resolve_runtime_for_run


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


def _normalize_input_shape(shape: Any) -> list[int]:
    if not isinstance(shape, list) or not shape:
        return [1, 24, 1]
    dims: list[int] = []
    for dim in shape:
        try:
            val = int(dim)
        except Exception:
            val = -1
        dims.append(1 if val <= 0 else val)
    return dims


def _naive_forecast(inputs: dict[str, Any]) -> list[float]:
    horizon = inputs.get("horizon", 1)
    horizon = horizon if isinstance(horizon, int) and horizon > 0 else 1
    history = _as_numeric_list(inputs.get("target_history", []))
    last = history[-1] if history else 0.0

    cov = inputs.get("known_future_covariates", {})
    cov_values = _as_numeric_list(cov)
    cov_effect = (sum(cov_values) / len(cov_values) * 0.01) if cov_values else 0.0
    return [round(last + cov_effect, 6) for _ in range(horizon)]


def _build_model_inputs(base_inputs: dict[str, Any], input_specs: list[dict[str, Any]]) -> list[np.ndarray]:
    history = _as_numeric_list(base_inputs.get("target_history", []))
    future_values = _as_numeric_list(base_inputs.get("known_future_covariates", {}))
    static_values = _as_numeric_list(base_inputs.get("static_covariates", {}))

    if not input_specs:
        lookback = max(1, len(history))
        arr = np.zeros((1, lookback, 1), dtype=np.float32)
        if history:
            seq = np.asarray(history[-lookback:], dtype=np.float32)
            arr[0, -len(seq) :, 0] = seq
        return [arr]

    inputs: list[np.ndarray] = []
    for idx, spec in enumerate(input_specs):
        name = str(spec.get("name", f"input_{idx}")).lower()
        shape = _normalize_input_shape(spec.get("shape"))

        if len(shape) == 3:
            _, timesteps, features = shape
            arr = np.zeros((1, timesteps, features), dtype=np.float32)
            if "future" in name and future_values:
                seq = np.asarray(future_values[-timesteps:], dtype=np.float32)
            else:
                seq = np.asarray(history[-timesteps:], dtype=np.float32) if history else np.zeros(0, dtype=np.float32)
            if seq.size > 0:
                arr[0, -len(seq) :, 0] = seq
            inputs.append(arr)
            continue

        if len(shape) == 2:
            _, width = shape
            arr = np.zeros((1, width), dtype=np.float32)
            source = static_values if ("static" in name and static_values) else history
            if source:
                seq = np.asarray(source[-width:], dtype=np.float32)
                arr[0, -len(seq) :] = seq
            inputs.append(arr)
            continue

        width = shape[0]
        arr = np.zeros((width,), dtype=np.float32)
        if history:
            seq = np.asarray(history[-width:], dtype=np.float32)
            arr[-len(seq) :] = seq
        inputs.append(arr)

    return inputs


def _find_keras_checkpoint(run_id: str) -> Path | None:
    checkpoint_dir = ARTIFACTS_DIR / "checkpoints" / run_id
    for name in ("best.keras", "best.h5", "last.keras", "last.h5"):
        candidate = checkpoint_dir / name
        if candidate.exists():
            return candidate
    return None


def _predict_tflite(model_path: Path, model_inputs: list[np.ndarray]) -> np.ndarray:
    from src.training.edge import run_tflite_inference

    return np.asarray(run_tflite_inference(model_path, model_inputs), dtype=np.float32)


def _predict_onnx(model_path: Path, model_inputs: list[np.ndarray]) -> np.ndarray:
    from src.training.edge import run_onnx_inference

    return np.asarray(run_onnx_inference(model_path, model_inputs), dtype=np.float32)


def _predict_keras(model_path: Path, model_inputs: list[np.ndarray]) -> np.ndarray:
    import tensorflow as tf

    model = tf.keras.models.load_model(str(model_path), compile=False)
    payload: Any = model_inputs if len(model_inputs) > 1 else model_inputs[0]
    return np.asarray(model.predict(payload, verbose=0), dtype=np.float32)


def infer_with_runtime_fallback(
    *,
    run_id: str,
    base_inputs: dict[str, Any],
    preferred_order: list[str] | None = None,
) -> dict[str, Any]:
    resolved = resolve_runtime_for_run(run_id=run_id, preferred_order=preferred_order)
    runtime_compatibility = resolved.get("runtime_compatibility", {})
    manifest = resolved.get("manifest") if isinstance(resolved.get("manifest"), dict) else {}
    input_specs = manifest.get("input_specs") if isinstance(manifest.get("input_specs"), list) else []
    model_inputs = _build_model_inputs(base_inputs, input_specs)

    fallback_chain = resolved.get("fallback_chain")
    if not isinstance(fallback_chain, list) or not fallback_chain:
        fallback_chain = [resolved.get("runtime_stack", "keras")]

    attempts: list[dict[str, Any]] = []
    for runtime in [x for x in fallback_chain if isinstance(x, str) and x]:
        runtime_row = runtime_compatibility.get(runtime, {}) if isinstance(runtime_compatibility, dict) else {}
        model_path_raw = runtime_row.get("path")
        model_path = Path(str(model_path_raw)) if isinstance(model_path_raw, str) and model_path_raw else None
        if runtime == "keras" and model_path is None:
            model_path = _find_keras_checkpoint(run_id)

        try:
            if runtime == "tflite":
                if model_path is None:
                    raise FileNotFoundError("tflite model path missing")
                prediction = _predict_tflite(model_path, model_inputs)
            elif runtime == "onnx":
                if model_path is None:
                    raise FileNotFoundError("onnx model path missing")
                prediction = _predict_onnx(model_path, model_inputs)
            elif runtime == "keras":
                if model_path is None:
                    raise FileNotFoundError("keras checkpoint not found")
                prediction = _predict_keras(model_path, model_inputs)
            else:
                raise ValueError(f"unsupported runtime '{runtime}'")

            flat = np.asarray(prediction, dtype=np.float32).reshape(-1).tolist()
            attempts.append({"runtime": runtime, "ok": True, "model_path": str(model_path) if model_path else None})
            return {
                "runtime_stack_requested": resolved.get("runtime_stack"),
                "fallback_chain": fallback_chain,
                "runtime_used": runtime,
                "fallback_used": runtime != resolved.get("runtime_stack"),
                "predictions": [float(x) for x in flat],
                "attempts": attempts,
                "manifest_path": resolved.get("manifest_path"),
            }
        except Exception as exc:
            attempts.append(
                {
                    "runtime": runtime,
                    "ok": False,
                    "model_path": str(model_path) if model_path else None,
                    "error": str(exc),
                }
            )

    naive = _naive_forecast(base_inputs)
    attempts.append({"runtime": "naive", "ok": True, "model_path": None})
    return {
        "runtime_stack_requested": resolved.get("runtime_stack"),
        "fallback_chain": fallback_chain,
        "runtime_used": "naive",
        "fallback_used": True,
        "predictions": [float(x) for x in naive],
        "attempts": attempts,
        "manifest_path": resolved.get("manifest_path"),
    }
