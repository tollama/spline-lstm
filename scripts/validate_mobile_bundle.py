#!/usr/bin/env python3
"""Validate a mobile bundle manifest against export artifacts and platform policy."""

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


def _resolve_path(raw: str | None, *, anchors: list[Path]) -> Path | None:
    if not raw:
        return None
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    for anchor in anchors:
        resolved = (anchor / candidate).resolve()
        if resolved.exists():
            return resolved
    return (anchors[0] / candidate).resolve()


def _is_nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _runtime_library_matches(runtime: str, runtime_library: str | None) -> bool:
    if not runtime_library:
        return False
    normalized = runtime_library.lower()
    if runtime == "tflite":
        return "tensorflow" in normalized or "tflite" in normalized
    if runtime == "onnx":
        return "onnx" in normalized
    if runtime == "keras":
        return "keras" in normalized or "tensorflow" in normalized
    return False


def _preferred_runtime(platform: str) -> str:
    return "tflite" if platform == "android" else "onnx"


def validate_bundle(bundle_manifest_path: Path, *, strict_platform_policy: bool) -> dict[str, Any]:
    anchors = [Path.cwd(), bundle_manifest_path.parent]
    payload = _load_json(bundle_manifest_path)
    errors: list[str] = []
    warnings: list[str] = []

    if payload.get("schema_version") != "mobile_bundle.v1":
        errors.append("schema_version must be 'mobile_bundle.v1'")

    platform = payload.get("platform")
    if platform not in {"android", "ios"}:
        errors.append("platform must be 'android' or 'ios'")
        platform = "android"

    app = payload.get("app")
    if not isinstance(app, dict):
        errors.append("app must be an object")
        app = {}
    for key in ("bundle_id", "min_version"):
        if not _is_nonempty_str(app.get(key)):
            errors.append(f"app.{key} must be a non-empty string")

    model = payload.get("model")
    if not isinstance(model, dict):
        errors.append("model must be an object")
        model = {}
    for key in ("model_id", "run_id", "semantic_version", "relative_path", "source_export_path", "sha256"):
        if not _is_nonempty_str(model.get(key)):
            errors.append(f"model.{key} must be a non-empty string")

    runtime = model.get("runtime_stack")
    if runtime not in {"tflite", "onnx", "keras"}:
        errors.append("model.runtime_stack must be one of: tflite, onnx, keras")
        runtime = "keras"

    fallback_chain = model.get("fallback_chain")
    if not isinstance(fallback_chain, list) or not fallback_chain or not all(_is_nonempty_str(x) for x in fallback_chain):
        errors.append("model.fallback_chain must be a non-empty string list")

    size_bytes = model.get("size_bytes")
    if not isinstance(size_bytes, int) or size_bytes <= 0:
        errors.append("model.size_bytes must be a positive integer")

    export_artifacts = payload.get("export_artifacts")
    if not isinstance(export_artifacts, dict):
        errors.append("export_artifacts must be an object")
        export_artifacts = {}

    for key in ("export_manifest_path", "ota_manifest_path"):
        if not _is_nonempty_str(export_artifacts.get(key)):
            errors.append(f"export_artifacts.{key} must be a non-empty string")

    input_specs = payload.get("input_specs")
    if not isinstance(input_specs, list):
        errors.append("input_specs must be a list")

    platform_config = payload.get("platform_config")
    if not isinstance(platform_config, dict):
        errors.append("platform_config must be an object")
        platform_config = {}

    if platform == "android":
        if not isinstance(platform_config.get("abi_filters"), list) or not platform_config.get("abi_filters"):
            errors.append("platform_config.abi_filters must be a non-empty list for Android")
        if not isinstance(platform_config.get("min_sdk"), int):
            errors.append("platform_config.min_sdk must be an integer for Android")
        if _is_nonempty_str(model.get("relative_path")) and not str(model["relative_path"]).startswith("assets/"):
            warnings.append("Android bundle usually stores the model under assets/")
    else:
        if not _is_nonempty_str(platform_config.get("bundle_resource_subdir")):
            errors.append("platform_config.bundle_resource_subdir must be set for iOS")
        if not _is_nonempty_str(platform_config.get("minimum_ios_version")):
            errors.append("platform_config.minimum_ios_version must be set for iOS")

    runtime_library = platform_config.get("runtime_library")
    if not _is_nonempty_str(runtime_library):
        errors.append("platform_config.runtime_library must be a non-empty string")
    elif runtime not in {None, "keras"} and not _runtime_library_matches(str(runtime), str(runtime_library)):
        errors.append(
            f"platform_config.runtime_library='{runtime_library}' is inconsistent with model.runtime_stack='{runtime}'"
        )

    source_export_path = _resolve_path(model.get("source_export_path"), anchors=anchors)
    export_manifest_path = _resolve_path(export_artifacts.get("export_manifest_path"), anchors=anchors)
    ota_manifest_path = _resolve_path(export_artifacts.get("ota_manifest_path"), anchors=anchors)
    edge_eval_path = _resolve_path(export_artifacts.get("edge_eval_path"), anchors=anchors)

    for label, path in (
        ("model.source_export_path", source_export_path),
        ("export_artifacts.export_manifest_path", export_manifest_path),
        ("export_artifacts.ota_manifest_path", ota_manifest_path),
    ):
        if path is None or not path.exists():
            errors.append(f"{label} does not exist")
    if export_artifacts.get("edge_eval_path") and (edge_eval_path is None or not edge_eval_path.exists()):
        errors.append("export_artifacts.edge_eval_path does not exist")

    if export_manifest_path is not None and export_manifest_path.exists():
        export_manifest = _load_json(export_manifest_path)
        if export_manifest.get("run_id") != model.get("run_id"):
            errors.append("model.run_id does not match export manifest run_id")
        runtime_compat = export_manifest.get("runtime_compatibility")
        if not isinstance(runtime_compat, dict):
            errors.append("export manifest missing runtime_compatibility")
            runtime_compat = {}
        runtime_row = runtime_compat.get(runtime, {})
        if not isinstance(runtime_row, dict) or runtime_row.get("supported") is not True:
            errors.append(f"runtime '{runtime}' is not marked supported in export manifest")
        if source_export_path is not None and runtime_row.get("path"):
            manifest_runtime_path = _resolve_path(runtime_row.get("path"), anchors=[export_manifest_path.parent, Path.cwd()])
            if manifest_runtime_path is not None and manifest_runtime_path.exists():
                if source_export_path.resolve() != manifest_runtime_path.resolve():
                    errors.append("model.source_export_path does not match export manifest runtime path")

        preferred_runtime = _preferred_runtime(platform)
        preferred_supported = isinstance(runtime_compat.get(preferred_runtime), dict) and runtime_compat.get(
            preferred_runtime, {}
        ).get("supported")
        if runtime != preferred_runtime and preferred_supported:
            message = (
                f"{platform} bundle uses runtime '{runtime}' while preferred runtime '{preferred_runtime}' "
                f"is available in export manifest"
            )
            if strict_platform_policy:
                errors.append(message)
            else:
                warnings.append(message)

    if ota_manifest_path is not None and ota_manifest_path.exists():
        ota_manifest = _load_json(ota_manifest_path)
        if ota_manifest.get("model_id") != model.get("model_id"):
            errors.append("model.model_id does not match ota manifest model_id")
        if ota_manifest.get("semantic_version") != model.get("semantic_version"):
            errors.append("model.semantic_version does not match ota manifest semantic_version")
        if ota_manifest.get("min_app_version") != app.get("min_version"):
            errors.append("app.min_version does not match ota manifest min_app_version")

    return {
        "bundle_manifest_path": str(bundle_manifest_path),
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Validate a mobile bundle manifest against export artifacts")
    p.add_argument("--bundle-manifest", type=str, required=True)
    p.add_argument(
        "--strict-platform-policy",
        action="store_true",
        default=False,
        help="Fail when the chosen runtime differs from the preferred platform runtime while the preferred one is available",
    )
    return p


def main() -> None:
    args = build_parser().parse_args()
    report = validate_bundle(Path(args.bundle_manifest), strict_platform_policy=bool(args.strict_platform_policy))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
