"""Edge export, runtime selection, and scoring utilities."""

from __future__ import annotations

import copy
import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


EDGE_DEVICE_PROFILES: dict[str, dict[str, Any]] = {
    "android_high_end": {
        "runtime_order": ["tflite", "onnx", "keras"],
        "latency_p95_target_ms": 50.0,
        "size_target_mb": 8.0,
        "size_hard_limit_mb": 15.0,
        "memory_budget_mb": 256.0,
    },
    "ios_high_end": {
        "runtime_order": ["tflite", "onnx", "keras"],
        "latency_p95_target_ms": 50.0,
        "size_target_mb": 8.0,
        "size_hard_limit_mb": 15.0,
        "memory_budget_mb": 256.0,
    },
    "desktop_reference": {
        "runtime_order": ["tflite", "onnx", "keras"],
        "latency_p95_target_ms": 50.0,
        "size_target_mb": 8.0,
        "size_hard_limit_mb": 15.0,
        "memory_budget_mb": 1024.0,
    },
}

EDGE_SLA_PRESETS: dict[str, dict[str, Any]] = {
    "balanced": {
        "accuracy_weight": 0.45,
        "latency_weight": 0.30,
        "size_weight": 0.15,
        "stability_weight": 0.10,
        "max_rmse_degradation_pct": 2.0,
    },
    "accuracy_biased": {
        "accuracy_weight": 0.60,
        "latency_weight": 0.20,
        "size_weight": 0.10,
        "stability_weight": 0.10,
        "max_rmse_degradation_pct": 3.0,
    },
    "latency_biased": {
        "accuracy_weight": 0.30,
        "latency_weight": 0.45,
        "size_weight": 0.15,
        "stability_weight": 0.10,
        "max_rmse_degradation_pct": 2.0,
    },
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_device_profiles(config_path: str | None) -> dict[str, dict[str, Any]]:
    profiles = copy.deepcopy(EDGE_DEVICE_PROFILES)
    if not config_path:
        return profiles

    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"device benchmark config not found: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("device benchmark config must be a JSON object")

    user_profiles = raw.get("profiles", raw)
    if not isinstance(user_profiles, dict):
        raise ValueError("device benchmark config profiles must be an object")

    for key, value in user_profiles.items():
        if not isinstance(value, dict):
            raise ValueError(f"profile '{key}' must be an object")
        base = profiles.get(key, {}).copy()
        base.update(value)
        profiles[key] = base
    return profiles


def parse_edge_sla(sla_name: str) -> dict[str, Any]:
    preset = EDGE_SLA_PRESETS.get(sla_name)
    if preset is None:
        raise ValueError(f"unsupported edge SLA preset: {sla_name}")
    return copy.deepcopy(preset)


def _as_input_list(inputs: Any) -> list[np.ndarray]:
    out = [np.asarray(x) for x in inputs if x is not None] if isinstance(inputs, list) else [np.asarray(inputs)]
    if not out:
        raise ValueError("no model inputs available")
    return out


def _truncate_calibration_inputs(inputs: Any, max_samples: int = 64) -> list[np.ndarray]:
    arrs = _as_input_list(inputs)
    return [np.asarray(x[:max_samples], dtype=np.float32) for x in arrs]


def _representative_dataset(calibration_inputs: list[np.ndarray]):
    n = int(min(x.shape[0] for x in calibration_inputs))
    n = max(1, n)
    for idx in range(n):
        yield [np.asarray(x[idx : idx + 1], dtype=np.float32) for x in calibration_inputs]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_input_specs(keras_model: Any) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for tensor in keras_model.inputs:
        shape = [int(dim) if dim is not None else -1 for dim in tensor.shape]
        dtype = getattr(getattr(tensor, "dtype", None), "name", str(getattr(tensor, "dtype", "float32")))
        name = str(getattr(tensor, "name", "input")).split(":")[0]
        specs.append({"name": name, "shape": shape, "dtype": dtype})
    return specs


def export_tflite_model(
    keras_model: Any,
    out_path: Path,
    quantization: str,
    calibration_inputs: Any | None = None,
    calibration_max_samples: int = 64,
) -> dict[str, Any]:
    try:
        import tensorflow as tf
    except ImportError as exc:
        return {"status": "failed", "error": f"tensorflow unavailable: {exc}"}

    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        converter = tf.lite.TFLiteConverter.from_keras_model(keras_model)

        if quantization == "fp16":
            converter.optimizations = [tf.lite.Optimize.DEFAULT]
            converter.target_spec.supported_types = [tf.float16]
        elif quantization == "int8":
            if calibration_inputs is None:
                raise ValueError("int8 quantization requires calibration inputs")
            cal = _truncate_calibration_inputs(calibration_inputs, max_samples=max(1, int(calibration_max_samples)))
            converter.optimizations = [tf.lite.Optimize.DEFAULT]
            converter.representative_dataset = lambda: _representative_dataset(cal)
            converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
            converter.inference_input_type = tf.int8
            converter.inference_output_type = tf.int8
        elif quantization != "none":
            raise ValueError(f"unsupported quantization: {quantization}")

        tflite_data = converter.convert()
        out_path.write_bytes(tflite_data)
        return {
            "status": "succeeded",
            "path": str(out_path),
            "size_bytes": int(out_path.stat().st_size),
            "sha256": _sha256(out_path),
            "quantization": quantization,
            "calibration_samples": int(calibration_max_samples) if quantization == "int8" else None,
        }
    except Exception as exc:  # pragma: no cover - runtime dependent
        logger.exception("TFLite export failed")
        return {"status": "failed", "error": str(exc), "quantization": quantization}


def export_onnx_model(keras_model: Any, out_path: Path) -> dict[str, Any]:
    try:
        import tensorflow as tf
        import tf2onnx
    except ImportError as exc:
        return {"status": "failed", "error": f"onnx export dependencies unavailable: {exc}"}

    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        signature = tuple(
            tf.TensorSpec(t.shape, t.dtype, name=str(getattr(t, "name", "input")).split(":")[0])
            for t in keras_model.inputs
        )
        tf2onnx.convert.from_keras(keras_model, input_signature=signature, opset=17, output_path=str(out_path))
        return {
            "status": "succeeded",
            "path": str(out_path),
            "size_bytes": int(out_path.stat().st_size),
            "sha256": _sha256(out_path),
        }
    except Exception as exc:  # pragma: no cover - runtime dependent
        logger.exception("ONNX export failed")
        return {"status": "failed", "error": str(exc)}


def run_tflite_inference(model_path: Path, sample_inputs: Any) -> np.ndarray:
    import tensorflow as tf

    interpreter = tf.lite.Interpreter(model_path=str(model_path))
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    inputs = _as_input_list(sample_inputs)
    if len(inputs) != len(input_details):
        raise ValueError(f"tflite input count mismatch: got {len(inputs)} expected {len(input_details)}")

    for i, detail in enumerate(input_details):
        arr = np.asarray(inputs[i], dtype=np.dtype(detail["dtype"]))
        interpreter.set_tensor(detail["index"], arr)
    interpreter.invoke()
    out = interpreter.get_tensor(output_details[0]["index"])
    return np.asarray(out, dtype=np.float32)


def run_onnx_inference(model_path: Path, sample_inputs: Any) -> np.ndarray:
    import onnxruntime as ort

    sess = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    feed: dict[str, Any] = {}
    inputs = _as_input_list(sample_inputs)
    sess_inputs = sess.get_inputs()
    if len(inputs) != len(sess_inputs):
        raise ValueError(f"onnx input count mismatch: got {len(inputs)} expected {len(sess_inputs)}")
    for i, meta in enumerate(sess_inputs):
        feed[meta.name] = np.asarray(inputs[i], dtype=np.float32)
    outputs = sess.run(None, feed)
    return np.asarray(outputs[0], dtype=np.float32)


def compute_parity(reference: np.ndarray, candidate: np.ndarray) -> dict[str, float]:
    ref = np.asarray(reference, dtype=np.float32).reshape(-1)
    cand = np.asarray(candidate, dtype=np.float32).reshape(-1)
    if ref.shape != cand.shape:
        raise ValueError(f"parity shape mismatch: ref={ref.shape} cand={cand.shape}")
    diff = np.abs(ref - cand)
    return {
        "max_abs_diff": float(np.max(diff)),
        "mean_abs_diff": float(np.mean(diff)),
        "rmse": float(np.sqrt(np.mean((ref - cand) ** 2))),
    }


def parity_within_thresholds(
    parity_result: dict[str, Any],
    *,
    max_abs_diff: float,
    rmse: float,
) -> bool:
    if "error" in parity_result:
        return False
    result_max_abs = parity_result.get("max_abs_diff")
    result_rmse = parity_result.get("rmse")
    if result_max_abs is None or result_rmse is None:
        return False
    return float(result_max_abs) <= float(max_abs_diff) and float(result_rmse) <= float(rmse)


def build_runtime_compatibility(export_results: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    matrix: dict[str, dict[str, Any]] = {
        "tflite": {
            "supported": export_results.get("tflite", {}).get("status") == "succeeded",
            "path": export_results.get("tflite", {}).get("path"),
            "reason": export_results.get("tflite", {}).get("error"),
        },
        "onnx": {
            "supported": export_results.get("onnx", {}).get("status") == "succeeded",
            "path": export_results.get("onnx", {}).get("path"),
            "reason": export_results.get("onnx", {}).get("error"),
        },
        "keras": {
            "supported": True,
            "path": None,
            "reason": None,
        },
    }
    return matrix


def select_runtime_stack(
    runtime_compatibility: dict[str, dict[str, Any]],
    preferred_order: list[str] | None = None,
) -> tuple[str, list[str]]:
    order = preferred_order or ["tflite", "onnx", "keras"]
    supported = [name for name in order if runtime_compatibility.get(name, {}).get("supported")]
    if not supported:
        return "keras", ["keras"]
    primary = supported[0]
    fallback = [x for x in supported if x != primary]
    if "keras" not in fallback and primary != "keras":
        fallback.append("keras")
    return primary, [primary, *fallback]


def build_ota_manifest(
    *,
    run_id: str,
    model_id: str,
    semantic_version: str,
    min_app_version: str,
    target_runtime: str,
    rollback_to: str | None,
    target_path: str | None,
) -> dict[str, Any]:
    return {
        "model_id": model_id,
        "semantic_version": semantic_version,
        "min_app_version": min_app_version,
        "sha256": _sha256(Path(target_path)) if target_path and Path(target_path).exists() else None,
        "target_runtime": target_runtime,
        "rollback_to": rollback_to,
        "run_id": run_id,
        "generated_at": utc_now_iso(),
    }


def _clip(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return float(max(low, min(high, value)))


def compute_accuracy_score(
    model_rmse: float | None, baseline_rmse: float | None, allowed_degradation_pct: float = 2.0
) -> float:
    if model_rmse is None or baseline_rmse is None or baseline_rmse <= 0:
        return 50.0
    degradation_pct = (model_rmse - baseline_rmse) / baseline_rmse * 100.0
    if degradation_pct <= 0:
        return 100.0
    if degradation_pct <= allowed_degradation_pct:
        return _clip(100.0 - degradation_pct * 10.0, 80.0, 100.0)
    return _clip(80.0 - (degradation_pct - allowed_degradation_pct) * 8.0, 0.0, 80.0)


def compute_latency_score(latency_p95_ms: float | None, target_ms: float) -> float:
    if latency_p95_ms is None:
        return 0.0
    if latency_p95_ms <= target_ms:
        return 100.0
    return _clip(100.0 - (latency_p95_ms - target_ms) * 2.0)


def compute_size_score(size_mb: float | None, target_mb: float, hard_limit_mb: float) -> float:
    if size_mb is None:
        return 0.0
    if size_mb <= target_mb:
        return 100.0
    if size_mb >= hard_limit_mb:
        return 0.0
    span = hard_limit_mb - target_mb
    return _clip(100.0 * (hard_limit_mb - size_mb) / max(span, 1e-8))


def compute_stability_score(failures: int, attempts: int) -> float:
    if attempts <= 0:
        return 0.0
    success_rate = max(0.0, (attempts - failures) / attempts)
    return _clip(success_rate * 100.0)


def compute_edge_score(
    *,
    accuracy_score: float,
    latency_score: float,
    size_score: float,
    stability_score: float,
    sla: dict[str, Any],
) -> float:
    return float(
        accuracy_score * float(sla["accuracy_weight"])
        + latency_score * float(sla["latency_weight"])
        + size_score * float(sla["size_weight"])
        + stability_score * float(sla["stability_weight"])
    )
