#!/usr/bin/env python3
"""Validate that the current node can run edge-focused spline-lstm workflows."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import platform
import sys
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


def run_validation(mode: str, cache_root: str, skip_python_version_check: bool) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    cache_root_path = Path(cache_root)
    matplotlib_cache = cache_root_path / "matplotlib"
    cache_root_path.mkdir(parents=True, exist_ok=True)
    matplotlib_cache.mkdir(parents=True, exist_ok=True)
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
    checks.append(_check_writable_dir(str(cache_root_path / "fontconfig")))

    if mode in {"benchmark-onnx", "train-export"}:
        checks.append(_check_import("onnxruntime"))

    if mode == "train-export":
        checks.append(_check_import("tensorflow"))
        checks.append(_check_import("tf2onnx"))

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
        "--skip-python-version-check",
        action="store_true",
        default=False,
        help="Skip the Python 3.10/3.11 gate; useful when validating imports on a non-target workstation",
    )
    return p


def main() -> None:
    args = build_parser().parse_args()
    payload = run_validation(
        mode=args.mode,
        cache_root=args.cache_root,
        skip_python_version_check=bool(args.skip_python_version_check),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    raise SystemExit(0 if payload["ok"] else 1)


if __name__ == "__main__":
    main()
