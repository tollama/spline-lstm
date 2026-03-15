from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

_BACKEND_MODULES = [
    "backend.app.main",
    "backend.app.config",
    "backend.app.utils",
    "backend.app.models",
    "backend.app.store",
    "backend.app.executor",
    "backend.app.routes",
    "backend.app.routes.health",
    "backend.app.routes.jobs",
    "backend.app.routes.forecast",
    "backend.app.routes.agent",
    "backend.app.routes.tollama",
    "backend.app.routes.runs",
    "backend.app.routes.mobile",
]


def _load_app(monkeypatch, artifacts_dir: Path) -> TestClient:
    monkeypatch.setenv("SPLINE_DEV_MODE", "1")
    monkeypatch.setenv("SPLINE_BACKEND_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("SPLINE_TRUSTED_HOSTS", "localhost,127.0.0.1,testserver")
    for mod_name in _BACKEND_MODULES:
        sys.modules.pop(mod_name, None)
    mod = importlib.import_module("backend.app.main")
    return TestClient(mod.app)


def test_mobile_benchmark_upload_ingests_payload(monkeypatch, tmp_path: Path) -> None:
    client = _load_app(monkeypatch, tmp_path / "artifacts")
    payload = {
        "run_id": "mobile-upload-001",
        "device_profile": "android_high_end",
        "expected_platform": "android",
        "benchmark_result": {
            "runtime_stack": "tflite",
            "fallback_chain": ["tflite", "keras"],
            "latency_ms": {"p50": 15.0, "p95": 20.0},
            "memory_peak_mb": 190.0,
            "size_mb": 4.2,
            "attempts": 120,
            "failures": 0,
            "metadata": {
                "platform": "android",
                "device_model": "Pixel 8",
                "os_version": "Android 15",
                "app_version": "1.12.0",
                "build_number": "12034",
                "bundle_id": "ai.tollama.splineforecast",
            },
            "accuracy": {
                "rmse": 0.93,
                "baseline_rmse": 1.0,
                "per_horizon_rmse": [0.8, 0.9, 1.0],
            },
        },
    }
    response = client.post("/api/v1/mobile/benchmarks:ingest", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    data = body["data"]
    assert data["run_id"] == "mobile-upload-001"
    assert data["device_profile"] == "android_high_end"
    assert data["record"]["metadata"]["device_model"] == "Pixel 8"
    assert data["validation"]["ok"] is True
    assert Path(data["source_path"]).exists()

    record_path = tmp_path / "artifacts" / "edge_bench" / "mobile-upload-001" / "android_high_end.json"
    assert record_path.exists()
    stored = json.loads(record_path.read_text(encoding="utf-8"))
    assert stored["metadata"]["platform"] == "android"


def test_mobile_benchmark_upload_rejects_invalid_payload(monkeypatch, tmp_path: Path) -> None:
    client = _load_app(monkeypatch, tmp_path / "artifacts")
    payload = {
        "run_id": "mobile-upload-bad-001",
        "device_profile": "ios_high_end",
        "expected_platform": "ios",
        "benchmark_result": {
            "runtime_stack": "tflite",
            "latency_ms": {"p50": 11.0, "p95": 14.0},
            "memory_peak_mb": 180.0,
            "size_mb": 4.0,
            "attempts": 100,
            "failures": 0,
            "metadata": {
                "platform": "android",
                "device_model": "Pixel 8",
                "os_version": "Android 15",
                "app_version": "1.12.0",
                "build_number": "12034",
                "bundle_id": "ai.tollama.splineforecast",
            },
            "accuracy": {"rmse": 0.9, "baseline_rmse": 1.0},
        },
    }
    response = client.post("/api/v1/mobile/benchmarks:ingest", json=payload)
    assert response.status_code == 400
    detail = response.json()["error"]
    assert detail["message"] == "invalid mobile benchmark payload"
    assert any("does not match expected platform" in item for item in detail["errors"])
