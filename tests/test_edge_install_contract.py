from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path


def test_pyproject_exposes_minimal_edge_install_split() -> None:
    root = Path(__file__).resolve().parents[1]
    payload = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    project = payload["project"]
    deps = project["dependencies"]
    optional = project["optional-dependencies"]

    assert "tensorflow>=2.14.0,<2.17.0" not in deps
    assert "matplotlib>=3.7.0" not in deps
    assert "numpy>=1.24.0" in deps

    assert optional["preprocessing"] == ["scipy>=1.11.0", "pandas>=2.0.0"]
    assert optional["train"] == ["tensorflow>=2.14.0,<2.17.0"]
    assert optional["edge-runtime"] == ["onnxruntime>=1.17.0"]
    assert "tf2onnx>=1.16.0" in optional["edge-export"]
    assert "tensorflow>=2.14.0,<2.17.0" in optional["full"]


def test_validate_edge_environment_ops_mode_runs(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    cache_root = tmp_path / "cache"
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/validate_edge_environment.py",
            "--mode",
            "ops",
            "--cache-root",
            str(cache_root),
            "--skip-python-version-check",
        ],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["mode"] == "ops"
    assert payload["ok"] is True
    assert payload["checks"][0]["skipped"] is True
    assert payload["recommended_env"]["XDG_CACHE_HOME"] == str(cache_root)
