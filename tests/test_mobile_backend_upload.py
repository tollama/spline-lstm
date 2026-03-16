from __future__ import annotations

import importlib
import json
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.utils import compute_hmac_sha256

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


def _load_app(monkeypatch, artifacts_dir: Path, *, signing_secret: str | None = None) -> TestClient:
    monkeypatch.setenv("SPLINE_DEV_MODE", "1")
    monkeypatch.setenv("SPLINE_BACKEND_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("SPLINE_TRUSTED_HOSTS", "localhost,127.0.0.1,testserver")
    if signing_secret is None:
        monkeypatch.delenv("SPLINE_MOBILE_UPLOAD_SIGNING_SECRET", raising=False)
    else:
        monkeypatch.setenv("SPLINE_MOBILE_UPLOAD_SIGNING_SECRET", signing_secret)
    for mod_name in _BACKEND_MODULES:
        sys.modules.pop(mod_name, None)
    mod = importlib.import_module("backend.app.main")
    return TestClient(mod.app)


def _signed_headers(secret: str, body: str, *, idem: str | None = None) -> dict[str, str]:
    timestamp = str(int(time.time()))
    signature = compute_hmac_sha256(secret, f"{timestamp}\n{body}")
    headers = {
        "Content-Type": "application/json",
        "X-Mobile-Timestamp": timestamp,
        "X-Mobile-Signature": signature,
    }
    if idem:
        headers["X-Idempotency-Key"] = idem
    return headers


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
    assert "receipt" in detail

    receipt_id = detail["receipt"]["receipt_id"]
    receipt_response = client.get(f"/api/v1/mobile/benchmarks/receipts/{receipt_id}")
    assert receipt_response.status_code == 200
    assert receipt_response.json()["data"]["status"] == "validation_failed"


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


def test_mobile_benchmark_upload_requires_valid_signature_when_enabled(monkeypatch, tmp_path: Path) -> None:
    secret = "mobile-secret"
    client = _load_app(monkeypatch, tmp_path / "artifacts", signing_secret=secret)
    payload = {
        "run_id": "mobile-signed-001",
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
    response = client.post("/api/v1/mobile/benchmarks:ingest", json=payload)
    assert response.status_code == 401

    body = json.dumps(payload)
    bad_headers = {
        "Content-Type": "application/json",
        "X-Mobile-Timestamp": str(int(time.time())),
        "X-Mobile-Signature": "bad",
    }
    response = client.post("/api/v1/mobile/benchmarks:ingest", content=body, headers=bad_headers)
    assert response.status_code == 401

    good_headers = _signed_headers(secret, body)
    response = client.post("/api/v1/mobile/benchmarks:ingest", content=body, headers=good_headers)
    assert response.status_code == 200


def test_mobile_benchmark_upload_receipt_endpoints(monkeypatch, tmp_path: Path) -> None:
    client = _load_app(monkeypatch, tmp_path / "artifacts")
    payload = {
        "run_id": "mobile-receipts-001",
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
    response = client.post("/api/v1/mobile/benchmarks:ingest", json=payload)
    assert response.status_code == 200
    receipt = response.json()["data"]["receipt"]
    receipt_id = receipt["receipt_id"]

    get_response = client.get(f"/api/v1/mobile/benchmarks/receipts/{receipt_id}")
    assert get_response.status_code == 200
    assert get_response.json()["data"]["receipt_id"] == receipt_id

    list_response = client.get("/api/v1/mobile/benchmarks/receipts", params={"run_id": "mobile-receipts-001"})
    assert list_response.status_code == 200
    listed = list_response.json()["data"]["items"]
    assert any(item["receipt_id"] == receipt_id for item in listed)


def test_mobile_benchmark_summary_endpoint(monkeypatch, tmp_path: Path) -> None:
    client = _load_app(monkeypatch, tmp_path / "artifacts")
    valid_payload = {
        "run_id": "mobile-summary-001",
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
    invalid_payload = {
        "run_id": "mobile-summary-001",
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

    ok_response = client.post("/api/v1/mobile/benchmarks:ingest", json=valid_payload)
    assert ok_response.status_code == 200
    bad_response = client.post("/api/v1/mobile/benchmarks:ingest", json=invalid_payload)
    assert bad_response.status_code == 400

    summary_response = client.get("/api/v1/mobile/benchmarks/summary", params={"run_id": "mobile-summary-001"})
    assert summary_response.status_code == 200
    data = summary_response.json()["data"]
    assert data["total_receipts"] == 2
    assert data["successful_receipts"] == 1
    assert data["failed_receipts"] == 1
    assert data["runtime_stack_counts"]["tflite"] == 1
    assert data["platform_counts"]["android"] == 1
    assert data["recent_uploads"]


def test_dashboard_summary_includes_mobile_aggregation(monkeypatch, tmp_path: Path) -> None:
    client = _load_app(monkeypatch, tmp_path / "artifacts")
    valid_payload = {
        "run_id": "mobile-dashboard-001",
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
    invalid_payload = {
        "run_id": "mobile-dashboard-001",
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
                "platform": "android",
                "device_model": "Pixel 8",
                "os_version": "Android 15",
                "app_version": "1.12.0",
                "build_number": "12034",
                "bundle_id": "ai.tollama.splineforecast",
            },
            "accuracy": {"rmse": 0.95, "baseline_rmse": 1.02},
        },
    }

    assert client.post("/api/v1/mobile/benchmarks:ingest", json=valid_payload).status_code == 200
    assert client.post("/api/v1/mobile/benchmarks:ingest", json=invalid_payload).status_code == 400

    response = client.get("/api/v1/dashboard/summary")
    assert response.status_code == 200
    mobile = response.json()["data"]["mobileBenchmarks"]
    assert mobile["total_receipts"] == 2
    assert mobile["successful_receipts"] == 1
    assert mobile["failed_receipts"] == 1
    assert mobile["status_counts"]["succeeded"] == 1
    assert mobile["status_counts"]["validation_failed"] == 1
    assert mobile["runtime_stack_counts"]["tflite"] == 1
    assert mobile["platform_counts"]["android"] == 1
