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


def test_mobile_benchmark_upload_is_idempotent(monkeypatch, tmp_path: Path) -> None:
    client = _load_app(monkeypatch, tmp_path / "artifacts")
    payload = {
        "run_id": "mobile-upload-idem-001",
        "device_profile": "android_high_end",
        "expected_platform": "android",
        "benchmark_result": {
            "runtime_stack": "tflite",
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
            "accuracy": {"rmse": 0.93, "baseline_rmse": 1.0},
        },
    }
    headers = {"X-Idempotency-Key": "mobile-idem-001"}
    first = client.post("/api/v1/mobile/benchmarks:ingest", json=payload, headers=headers)
    second = client.post("/api/v1/mobile/benchmarks:ingest", json=payload, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()


def test_mobile_benchmark_batch_upload_ingests_multiple_payloads(monkeypatch, tmp_path: Path) -> None:
    client = _load_app(monkeypatch, tmp_path / "artifacts")
    payload = {
        "uploads": [
            {
                "run_id": "mobile-batch-001",
                "device_profile": "android_high_end",
                "expected_platform": "android",
                "benchmark_result": {
                    "runtime_stack": "tflite",
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
                    "accuracy": {"rmse": 0.93, "baseline_rmse": 1.0},
                },
            },
            {
                "run_id": "mobile-batch-001",
                "device_profile": "ios_high_end",
                "expected_platform": "ios",
                "benchmark_result": {
                    "runtime_stack": "onnx",
                    "latency_ms": {"p50": 18.0, "p95": 24.0},
                    "memory_peak_mb": 210.0,
                    "size_mb": 5.1,
                    "attempts": 120,
                    "failures": 0,
                    "metadata": {
                        "platform": "ios",
                        "device_model": "iPhone 15 Pro",
                        "os_version": "iOS 18.2",
                        "app_version": "1.12.0",
                        "build_number": "12034",
                        "bundle_id": "ai.tollama.splineforecast",
                    },
                    "accuracy": {"rmse": 0.95, "baseline_rmse": 1.02},
                },
            },
        ]
    }
    headers = {"X-Idempotency-Key": "mobile-batch-idem-001"}
    response = client.post("/api/v1/mobile/benchmarks:ingest-batch", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["count"] == 2
    assert {item["device_profile"] for item in body["items"]} == {"android_high_end", "ios_high_end"}
