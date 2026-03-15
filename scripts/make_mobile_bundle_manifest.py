#!/usr/bin/env python3
"""Generate a smartphone deployment bundle manifest from an edge export manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _choose_runtime(platform: str, runtime_compatibility: dict[str, Any], requested_runtime: str | None) -> str:
    if requested_runtime:
        chosen = runtime_compatibility.get(requested_runtime, {})
        if not chosen.get("supported"):
            raise ValueError(f"requested runtime '{requested_runtime}' is not supported by export manifest")
        return requested_runtime

    preferred_order = ["tflite", "onnx", "keras"] if platform == "android" else ["onnx", "tflite", "keras"]
    for runtime in preferred_order:
        if runtime_compatibility.get(runtime, {}).get("supported"):
            return runtime
    raise ValueError("no supported runtime found in export manifest")


def _default_relative_model_path(platform: str, runtime: str) -> str:
    suffix = {"tflite": "model.tflite", "onnx": "model.onnx", "keras": "model.keras"}.get(runtime, "model.bin")
    if platform == "android":
        return f"assets/models/{suffix}"
    return f"BundleModels/{suffix}"


def _platform_config(platform: str, args: argparse.Namespace) -> dict[str, Any]:
    if platform == "android":
        return {
            "asset_pack": args.asset_pack or "forecast_models",
            "abi_filters": [x.strip() for x in args.abi_filters.split(",") if x.strip()],
            "runtime_library": args.runtime_library or "org.tensorflow:tensorflow-lite",
            "min_sdk": int(args.min_sdk),
        }
    return {
        "bundle_resource_subdir": args.bundle_resource_subdir or "BundleModels",
        "runtime_library": args.runtime_library or "onnxruntime-mobile",
        "minimum_ios_version": args.minimum_ios_version or "16.0",
    }


def build_manifest(args: argparse.Namespace) -> dict[str, Any]:
    export_manifest_path = Path(args.export_manifest)
    export_manifest = _load_json(export_manifest_path)
    runtime_compatibility = export_manifest.get("runtime_compatibility")
    if not isinstance(runtime_compatibility, dict):
        raise ValueError("export manifest missing runtime_compatibility")

    runtime = _choose_runtime(args.platform, runtime_compatibility, args.runtime_stack)
    runtime_entry = runtime_compatibility.get(runtime, {})
    fallback_chain = export_manifest.get("fallback_chain")
    if not isinstance(fallback_chain, list) or not fallback_chain:
        fallback_chain = [runtime, "keras"] if runtime != "keras" else ["keras"]

    model_path = runtime_entry.get("path")
    model_file = Path(model_path) if isinstance(model_path, str) and model_path else None
    relative_model_path = args.relative_model_path or _default_relative_model_path(args.platform, runtime)
    ota_manifest = export_manifest.get("ota_manifest")
    if not isinstance(ota_manifest, dict):
        raise ValueError("export manifest missing ota_manifest block")

    platform_config = _platform_config(args.platform, args)

    return {
        "schema_version": "mobile_bundle.v1",
        "platform": args.platform,
        "app": {
            "bundle_id": args.bundle_id,
            "min_version": ota_manifest.get("min_app_version"),
            "build_number": args.build_number,
        },
        "model": {
            "model_id": ota_manifest.get("model_id"),
            "run_id": export_manifest.get("run_id"),
            "semantic_version": ota_manifest.get("semantic_version"),
            "runtime_stack": runtime,
            "fallback_chain": fallback_chain,
            "quantization": export_manifest.get("quantization"),
            "relative_path": relative_model_path,
            "source_export_path": str(model_file) if model_file is not None else None,
            "sha256": runtime_entry.get("sha256", ota_manifest.get("sha256")),
            "size_bytes": runtime_entry.get("size_bytes"),
        },
        "export_artifacts": {
            "export_manifest_path": str(export_manifest_path),
            "ota_manifest_path": str(export_manifest_path.with_name("ota_manifest.json")),
            "edge_eval_path": (
                str(export_manifest["edge_evaluation"].get("path"))
                if isinstance(export_manifest.get("edge_evaluation"), dict)
                else None
            ),
        },
        "input_specs": export_manifest.get("input_specs", []),
        "platform_config": platform_config,
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Generate a mobile bundle manifest for Android or iOS app integration")
    p.add_argument("--platform", type=str, choices=["android", "ios"], required=True)
    p.add_argument("--export-manifest", type=str, required=True, help="Path to artifacts/exports/<run_id>/manifest.json")
    p.add_argument("--output", type=str, required=True)
    p.add_argument("--bundle-id", type=str, required=True, help="App bundle id / applicationId")
    p.add_argument("--build-number", type=str, default=None, help="Optional app build number")
    p.add_argument("--runtime-stack", type=str, choices=["tflite", "onnx", "keras"], default=None)
    p.add_argument("--relative-model-path", type=str, default=None, help="Path used inside the mobile app bundle")
    p.add_argument("--asset-pack", type=str, default=None, help="Android asset pack name")
    p.add_argument("--abi-filters", type=str, default="arm64-v8a", help="Android ABI list, comma-separated")
    p.add_argument("--runtime-library", type=str, default=None, help="Native runtime package name")
    p.add_argument("--min-sdk", type=int, default=26, help="Android minSdkVersion")
    p.add_argument("--bundle-resource-subdir", type=str, default=None, help="iOS resource bundle subdir")
    p.add_argument("--minimum-ios-version", type=str, default=None, help="iOS deployment target")
    return p


def main() -> None:
    args = build_parser().parse_args()
    payload = build_manifest(args)
    _write_json(Path(args.output), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
