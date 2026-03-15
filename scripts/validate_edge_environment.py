#!/usr/bin/env python3
"""Validate that the current node can run edge-focused spline-lstm workflows."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _check_python_version() -> dict[str, Any]:
    version = sys.version_info
    supported = (version.major, version.minor) in {(3, 10), (3, 11)}
    return {
        "name": "python_version",
        "ok": supported,
        "detail": f"{version.major}.{version.minor}.{version.micro}",
        "expected": "3.10 or 3.11",
    }


def _check_import(module_name: str) -> dict[str, Any]:
    try:
        importlib.import_module(module_name)
        return {"name": f"import:{module_name}", "ok": True, "detail": "ok"}
    except Exception as exc:
        return {"name": f"import:{module_name}", "ok": False, "detail": str(exc)}


def _check_writable_dir(path_str: str) -> dict[str, Any]:
    path = Path(path_str)
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".edge_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return {"name": f"writable:{path}", "ok": True, "detail": "ok"}
    except Exception as exc:
        return {"name": f"writable:{path}", "ok": False, "detail": str(exc)}


def _check_disk_space(path_str: str, min_free_mb: float) -> dict[str, Any]:
    if min_free_mb <= 0:
        return {
            "name": f"disk_free:{path_str}",
            "ok": True,
            "detail": "skipped",
            "expected": "threshold disabled",
            "skipped": True,
        }

    usage = shutil.disk_usage(path_str)
    free_mb = float(usage.free / (1024.0 * 1024.0))
    return {
        "name": f"disk_free:{path_str}",
        "ok": free_mb >= min_free_mb,
        "detail": f"{free_mb:.1f} MiB free",
        "expected": f">= {min_free_mb:.1f} MiB free",
    }


def _detect_total_memory_mb() -> float | None:
    if hasattr(os, "sysconf"):
        try:
            page_size = int(os.sysconf("SC_PAGE_SIZE"))
            phys_pages = int(os.sysconf("SC_PHYS_PAGES"))
            if page_size > 0 and phys_pages > 0:
                return float(page_size * phys_pages / (1024.0 * 1024.0))
        except (OSError, ValueError):
            pass
    return None


def _check_total_memory(min_total_memory_mb: float) -> dict[str, Any]:
    total_memory_mb = _detect_total_memory_mb()
    if min_total_memory_mb <= 0:
        return {
            "name": "total_memory",
            "ok": True,
            "detail": f"{total_memory_mb:.1f} MiB detected" if total_memory_mb is not None else "unavailable",
            "expected": "threshold disabled",
            "skipped": True,
        }

    if total_memory_mb is None:
        return {
            "name": "total_memory",
            "ok": False,
            "detail": "unable to determine system memory",
            "expected": f">= {min_total_memory_mb:.1f} MiB total memory",
        }

    return {
        "name": "total_memory",
        "ok": total_memory_mb >= min_total_memory_mb,
        "detail": f"{total_memory_mb:.1f} MiB detected",
        "expected": f">= {min_total_memory_mb:.1f} MiB total memory",
    }


def _check_cli_help(script_relpath: str) -> dict[str, Any]:
    env = os.environ.copy()
    proc = subprocess.run(
        [sys.executable, str(ROOT / script_relpath), "--help"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
    )
    detail = (proc.stdout or proc.stderr).strip().splitlines()
    first_line = detail[0] if detail else "no output"
    return {
        "name": f"cli_help:{script_relpath}",
        "ok": proc.returncode == 0,
        "detail": first_line,
        "expected": "exit code 0",
    }


def _build_onnx_feed(session: Any) -> dict[str, Any]:
    import numpy as np

    feed: dict[str, Any] = {}
    for meta in session.get_inputs():
        shape = []
        for dim in meta.shape:
            if isinstance(dim, int) and dim > 0:
                shape.append(dim)
            else:
                shape.append(1)
        feed[meta.name] = np.zeros(shape, dtype=np.float32)
    return feed


def _check_onnxruntime_support(onnx_smoke_model: str | None) -> dict[str, Any]:
    try:
        import onnxruntime as ort
    except Exception as exc:
        return {"name": "onnxruntime_functional", "ok": False, "detail": str(exc)}

    providers = ort.get_available_providers()
    detail = f"providers={providers}"
    if "CPUExecutionProvider" not in providers:
        return {
            "name": "onnxruntime_functional",
            "ok": False,
            "detail": detail,
            "expected": "CPUExecutionProvider available",
        }

    if not onnx_smoke_model:
        return {
            "name": "onnxruntime_functional",
            "ok": True,
            "detail": detail,
            "expected": "CPUExecutionProvider available",
        }

    model_path = Path(onnx_smoke_model)
    if not model_path.exists():
        return {
            "name": "onnxruntime_functional",
            "ok": False,
            "detail": f"smoke model not found: {model_path}",
        }

    try:
        session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        outputs = session.run(None, _build_onnx_feed(session))
    except Exception as exc:
        return {
            "name": "onnxruntime_functional",
            "ok": False,
            "detail": f"session/inference failed: {exc}",
        }

    return {
        "name": "onnxruntime_functional",
        "ok": len(outputs) > 0,
        "detail": f"{detail}; outputs={len(outputs)}",
        "expected": "load model and execute at least one output tensor",
    }


def _check_train_export_functional(cache_root: str) -> dict[str, Any]:
    try:
        import numpy as np
        import tensorflow as tf

        from src.training.edge import (
            compute_parity,
            export_onnx_model,
            export_tflite_model,
            run_onnx_inference,
            run_tflite_inference,
        )
    except Exception as exc:
        return {"name": "train_export_functional", "ok": False, "detail": str(exc)}

    try:
        with tempfile.TemporaryDirectory(prefix="edge-train-export-smoke-", dir=cache_root) as tmpdir:
            tmp_root = Path(tmpdir)
            model = tf.keras.Sequential(
                [
                    tf.keras.layers.Input(shape=(4,), name="x"),
                    tf.keras.layers.Dense(
                        2,
                        use_bias=False,
                        kernel_initializer=tf.keras.initializers.Constant(
                            [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0], [0.5, -0.5]]
                        ),
                    ),
                ]
            )
            sample = np.asarray([[1.0, 2.0, 3.0, 4.0]], dtype=np.float32)
            keras_pred = np.asarray(model(sample, training=False), dtype=np.float32)

            tflite_path = tmp_root / "model.tflite"
            onnx_path = tmp_root / "model.onnx"
            tflite_result = export_tflite_model(model, tflite_path, quantization="none")
            onnx_result = export_onnx_model(model, onnx_path)
            if tflite_result.get("status") != "succeeded":
                return {
                    "name": "train_export_functional",
                    "ok": False,
                    "detail": f"tflite export failed: {tflite_result.get('error')}",
                }
            if onnx_result.get("status") != "succeeded":
                return {
                    "name": "train_export_functional",
                    "ok": False,
                    "detail": f"onnx export failed: {onnx_result.get('error')}",
                }

            tflite_pred = run_tflite_inference(tflite_path, sample)
            onnx_pred = run_onnx_inference(onnx_path, sample)
            tflite_parity = compute_parity(keras_pred, tflite_pred)
            onnx_parity = compute_parity(keras_pred, onnx_pred)
            if tflite_parity["rmse"] > 1e-4 or onnx_parity["rmse"] > 1e-4:
                return {
                    "name": "train_export_functional",
                    "ok": False,
                    "detail": (
                        f"parity drift too large: "
                        f"tflite_rmse={tflite_parity['rmse']:.6f}, "
                        f"onnx_rmse={onnx_parity['rmse']:.6f}"
                    ),
                }

            return {
                "name": "train_export_functional",
                "ok": True,
                "detail": (
                    f"tflite_rmse={tflite_parity['rmse']:.6f}, "
                    f"onnx_rmse={onnx_parity['rmse']:.6f}"
                ),
            }
    except Exception as exc:
        return {"name": "train_export_functional", "ok": False, "detail": str(exc)}


def run_validation(
    mode: str,
    cache_root: str,
    skip_python_version_check: bool,
    *,
    artifacts_dir: str,
    min_free_disk_mb: float,
    min_total_memory_mb: float,
    onnx_smoke_model: str | None,
    skip_functional_smoke: bool,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    cache_root_path = Path(cache_root)
    matplotlib_cache = cache_root_path / "matplotlib"
    fontconfig_cache = cache_root_path / "fontconfig"
    artifacts_root = Path(artifacts_dir)
    cache_root_path.mkdir(parents=True, exist_ok=True)
    matplotlib_cache.mkdir(parents=True, exist_ok=True)
    fontconfig_cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("XDG_CACHE_HOME", str(cache_root_path))
    os.environ.setdefault("MPLCONFIGDIR", str(matplotlib_cache))

    if skip_python_version_check:
        checks.append(
            {
                "name": "python_version",
                "ok": True,
                "detail": sys.version.split()[0],
                "expected": "3.10 or 3.11",
                "skipped": True,
            }
        )
    else:
        checks.append(_check_python_version())
    checks.append(_check_import("numpy"))
    checks.append(_check_import("yaml"))
    checks.append(_check_import("src.training.edge_device_ingest"))
    checks.append(_check_import("src.training.edge_release_gate"))

    checks.append(_check_writable_dir(str(cache_root_path)))
    checks.append(_check_writable_dir(str(matplotlib_cache)))
    checks.append(_check_writable_dir(str(fontconfig_cache)))
    checks.append(_check_writable_dir(str(artifacts_root)))
    checks.append(_check_disk_space(str(cache_root_path), min_free_mb=min_free_disk_mb))
    checks.append(_check_total_memory(min_total_memory_mb=min_total_memory_mb))

    if not skip_functional_smoke:
        checks.append(_check_cli_help("scripts/ingest_edge_device_bench.py"))
        checks.append(_check_cli_help("scripts/edge_release_gate.py"))

    if mode in {"benchmark-onnx", "train-export"}:
        checks.append(_check_import("onnxruntime"))
        if not skip_functional_smoke:
            checks.append(_check_onnxruntime_support(onnx_smoke_model=onnx_smoke_model))

    if mode == "train-export":
        checks.append(_check_import("tensorflow"))
        checks.append(_check_import("tf2onnx"))
        if not skip_functional_smoke:
            checks.append(_check_train_export_functional(str(cache_root_path)))

    ok = all(item["ok"] for item in checks)
    return {
        "mode": mode,
        "ok": ok,
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "recommended_env": {
            "MPLCONFIGDIR": str(matplotlib_cache),
            "XDG_CACHE_HOME": str(cache_root_path),
        },
        "checks": checks,
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Validate spline-lstm support level on an edge node")
    p.add_argument(
        "--mode",
        choices=["ops", "benchmark-onnx", "train-export"],
        default="ops",
        help="ops=ingest/gate only, benchmark-onnx=ops+onnxruntime, train-export=benchmark-onnx+tensorflow+tf2onnx",
    )
    p.add_argument(
        "--cache-root",
        type=str,
        default=os.environ.get("XDG_CACHE_HOME", "/tmp/xdg-cache-spline"),
        help="Writable cache root used for validation probes and recommended env vars",
    )
    p.add_argument(
        "--artifacts-dir",
        type=str,
        default="artifacts",
        help="Writable artifacts directory root expected on the node",
    )
    p.add_argument(
        "--min-free-disk-mb",
        type=float,
        default=0.0,
        help="Fail if cache root free disk space is below this threshold; 0 disables the check",
    )
    p.add_argument(
        "--min-total-memory-mb",
        type=float,
        default=0.0,
        help="Fail if detected total system memory is below this threshold; 0 disables the check",
    )
    p.add_argument(
        "--onnx-smoke-model",
        type=str,
        default=None,
        help="Optional ONNX model path used for a real runtime smoke in benchmark-onnx/train-export modes",
    )
    p.add_argument(
        "--skip-python-version-check",
        action="store_true",
        default=False,
        help="Skip the Python 3.10/3.11 gate; useful when validating imports on a non-target workstation",
    )
    p.add_argument(
        "--skip-functional-smoke",
        action="store_true",
        default=False,
        help="Skip CLI/runtime execution smoke checks and only validate imports + writable paths",
    )
    return p


def main() -> None:
    args = build_parser().parse_args()
    payload = run_validation(
        mode=args.mode,
        cache_root=args.cache_root,
        skip_python_version_check=bool(args.skip_python_version_check),
        artifacts_dir=args.artifacts_dir,
        min_free_disk_mb=float(args.min_free_disk_mb),
        min_total_memory_mb=float(args.min_total_memory_mb),
        onnx_smoke_model=args.onnx_smoke_model,
        skip_functional_smoke=bool(args.skip_functional_smoke),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    raise SystemExit(0 if payload["ok"] else 1)


if __name__ == "__main__":
    main()
