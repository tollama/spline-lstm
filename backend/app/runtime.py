from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.app.config import ARTIFACTS_DIR


def _load_manifest(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _runtime_supported(runtime_compatibility: dict[str, Any], runtime: str) -> bool:
    raw = runtime_compatibility.get(runtime, {})
    return isinstance(raw, dict) and bool(raw.get("supported"))


def select_runtime_stack(
    runtime_compatibility: dict[str, Any],
    preferred_order: list[str] | None = None,
) -> tuple[str, list[str]]:
    order = preferred_order or ["tflite", "onnx", "keras"]
    supported = [name for name in order if _runtime_supported(runtime_compatibility, name)]
    if not supported:
        return "keras", ["keras"]

    primary = supported[0]
    fallback = [x for x in supported if x != primary]
    if primary != "keras" and "keras" not in fallback:
        fallback.append("keras")
    return primary, [primary, *fallback]


def resolve_runtime_for_run(run_id: str, preferred_order: list[str] | None = None) -> dict[str, Any]:
    manifest_path = ARTIFACTS_DIR / "exports" / run_id / "manifest.json"
    manifest = _load_manifest(manifest_path)
    if manifest is None:
        return {
            "manifest_path": str(manifest_path),
            "runtime_stack": "keras",
            "fallback_chain": ["keras"],
            "runtime_compatibility": {"keras": {"supported": True, "path": None, "reason": "manifest not found"}},
        }

    runtime_compatibility = manifest.get("runtime_compatibility")
    if not isinstance(runtime_compatibility, dict):
        runtime_compatibility = {"keras": {"supported": True, "path": None, "reason": "missing compatibility matrix"}}

    runtime_stack, fallback_chain = select_runtime_stack(runtime_compatibility, preferred_order=preferred_order)
    return {
        "manifest_path": str(manifest_path),
        "runtime_stack": runtime_stack,
        "fallback_chain": fallback_chain,
        "runtime_compatibility": runtime_compatibility,
        "manifest": manifest,
    }
