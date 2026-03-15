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


def test_importing_src_does_not_eagerly_load_tensorflow() -> None:
    root = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json, sys; import src; print(json.dumps({'tensorflow_loaded': 'tensorflow' in sys.modules}))",
        ],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["tensorflow_loaded"] is False


def _run_help_without_tensorflow(script_path: str) -> dict[str, object]:
    root = Path(__file__).resolve().parents[1]
    code = f"""
import contextlib
import io
import json
import runpy
import sys

sys.argv = [{script_path!r}, "--help"]
exit_code = 0
stdout = io.StringIO()
stderr = io.StringIO()
with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
    try:
        runpy.run_path(sys.argv[0], run_name="__main__")
    except SystemExit as exc:
        exit_code = exc.code if isinstance(exc.code, int) else 0
print(json.dumps({{
    "exit_code": exit_code,
    "tensorflow_loaded": "tensorflow" in sys.modules,
    "stdout": stdout.getvalue(),
    "stderr": stderr.getvalue(),
}}))
sys.exit(exit_code)
"""
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
        ],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_ingest_cli_help_does_not_load_tensorflow() -> None:
    payload = _run_help_without_tensorflow("scripts/ingest_edge_device_bench.py")
    assert payload["exit_code"] == 0
    assert payload["tensorflow_loaded"] is False
    assert "Ingest real-device benchmark results into edge benchmark artifacts" in str(payload["stdout"])


def test_release_gate_cli_help_does_not_load_tensorflow() -> None:
    payload = _run_help_without_tensorflow("scripts/edge_release_gate.py")
    assert payload["exit_code"] == 0
    assert payload["tensorflow_loaded"] is False
    assert "Apply edge SLA gate before OTA promotion" in str(payload["stdout"])
