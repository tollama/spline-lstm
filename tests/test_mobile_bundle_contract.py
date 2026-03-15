from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.training.edge_device_ingest import run


def _write_export_manifest(root: Path) -> Path:
    export_root = root / "artifacts" / "exports" / "mobile-demo-001"
    export_root.mkdir(parents=True, exist_ok=True)
    tflite_path = export_root / "tflite" / "model.tflite"
    onnx_path = export_root / "onnx" / "model.onnx"
    tflite_path.parent.mkdir(parents=True, exist_ok=True)
    onnx_path.parent.mkdir(parents=True, exist_ok=True)
    tflite_path.write_bytes(b"tflite-model")
    onnx_path.write_bytes(b"onnx-model")
    edge_eval_path = export_root / "edge_eval.npz"
    edge_eval_path.write_bytes(b"edge-eval")
    payload = {
        "run_id": "mobile-demo-001",
        "quantization": "fp16",
        "fallback_chain": ["tflite", "onnx", "keras"],
        "input_specs": [{"name": "x", "shape": [1, 24, 8], "dtype": "float32"}],
        "runtime_compatibility": {
            "tflite": {
                "supported": True,
                "path": str(tflite_path),
                "sha256": "tflite-sha",
                "size_bytes": 12,
            },
            "onnx": {
                "supported": True,
                "path": str(onnx_path),
                "sha256": "onnx-sha",
                "size_bytes": 10,
            },
            "keras": {"supported": True, "path": str(export_root / "best.keras")},
        },
        "edge_evaluation": {"path": str(edge_eval_path)},
        "ota_manifest": {
            "model_id": "spline-edge-forecast",
            "semantic_version": "1.2.3",
            "min_app_version": "1.12.0",
            "sha256": "ota-sha",
            "target_runtime": "tflite",
            "run_id": "mobile-demo-001",
        },
    }
    manifest_path = export_root / "manifest.json"
    ota_path = export_root / "ota_manifest.json"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    ota_path.write_text(json.dumps(payload["ota_manifest"]), encoding="utf-8")
    return manifest_path


def test_make_mobile_bundle_manifest_selects_platform_runtime_defaults(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    manifest_path = _write_export_manifest(tmp_path)
    android_out = tmp_path / "android_bundle.json"
    ios_out = tmp_path / "ios_bundle.json"

    for platform, out_path in (("android", android_out), ("ios", ios_out)):
        proc = subprocess.run(
            [
                sys.executable,
                "scripts/make_mobile_bundle_manifest.py",
                "--platform",
                platform,
                "--export-manifest",
                str(manifest_path),
                "--output",
                str(out_path),
                "--bundle-id",
                "ai.tollama.splineforecast",
                "--build-number",
                "12034",
            ],
            cwd=str(root),
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stderr

    android_payload = json.loads(android_out.read_text(encoding="utf-8"))
    ios_payload = json.loads(ios_out.read_text(encoding="utf-8"))

    assert android_payload["platform"] == "android"
    assert android_payload["model"]["runtime_stack"] == "tflite"
    assert android_payload["platform_config"]["runtime_library"] == "org.tensorflow:tensorflow-lite"
    assert android_payload["model"]["relative_path"] == "assets/models/model.tflite"

    assert ios_payload["platform"] == "ios"
    assert ios_payload["model"]["runtime_stack"] == "onnx"
    assert ios_payload["platform_config"]["runtime_library"] == "onnxruntime-mobile"
    assert ios_payload["model"]["relative_path"] == "BundleModels/model.onnx"

    for out_path in (android_out, ios_out):
        proc = subprocess.run(
            [
                sys.executable,
                "scripts/validate_mobile_bundle.py",
                "--bundle-manifest",
                str(out_path),
            ],
            cwd=str(root),
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stderr


def test_mobile_device_ingest_preserves_metadata_block(tmp_path: Path) -> None:
    source = tmp_path / "android_mobile.json"
    source.write_text(
        json.dumps(
            {
                "runtime_stack": "tflite",
                "latency_ms": {"p50": 12.3, "p95": 18.9},
                "memory_peak_mb": 180.0,
                "size_mb": 4.1,
                "attempts": 200,
                "failures": 0,
                "metadata": {
                    "platform": "android",
                    "device_model": "Pixel 8",
                    "os_version": "Android 15",
                    "app_version": "1.12.0",
                },
                "accuracy": {
                    "rmse": 0.91,
                    "baseline_rmse": 1.0,
                },
            }
        ),
        encoding="utf-8",
    )

    out = run(
        type(
            "Args",
            (),
            {
                "run_id": "mobile-ingest-001",
                "artifacts_dir": str(tmp_path / "artifacts"),
                "device_result": [f"android_high_end={source}"],
                "device_results_dir": None,
                "edge_sla": "balanced",
                "device_benchmark_config": None,
                "metrics_json": None,
                "merge_existing": True,
            },
        )()
    )

    result = out["results"][0]
    assert result["metadata"]["platform"] == "android"
    assert result["metadata"]["device_model"] == "Pixel 8"


def test_mobile_bundle_examples_validate() -> None:
    root = Path(__file__).resolve().parents[1]
    for path in (
        "examples/mobile_bundle_android_tflite.json",
        "examples/mobile_bundle_ios_onnx.json",
    ):
        proc = subprocess.run(
            [
                sys.executable,
                "scripts/validate_mobile_bundle.py",
                "--bundle-manifest",
                path,
            ],
            cwd=str(root),
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stderr
