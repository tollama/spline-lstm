from __future__ import annotations

import time

from backend.app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_and_dashboard_contract() -> None:
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    body = health.json()
    assert body["ok"] is True
    assert body["data"]["status"] == "healthy"

    dashboard = client.get("/api/v1/dashboard/summary")
    assert dashboard.status_code == 200
    data = dashboard.json()["data"]
    assert "serviceStatus" in data
    assert "recentJobs" in data
    assert "mobileBenchmarks" in data


def test_run_submit_job_status_logs_cancel_and_results_contract() -> None:
    create = client.post(
        "/api/v1/pipelines/spline-tsfm:run",
        json={
            "run_id": "contract-run-001",
            "model_type": "gru",
            "feature_mode": "multivariate",
            "model_config": {"model_type": "gru", "epochs": 1},
        },
    )
    assert create.status_code == 200
    created = create.json()["data"]
    job_id = created["job_id"]
    assert created["status"] == "queued"

    # Initial job detail
    job = client.get(f"/api/v1/jobs/{job_id}")
    assert job.status_code == 200
    assert job.json()["data"]["run_id"] == "contract-run-001"

    # Logs contract: supports structured lines
    logs = client.get(f"/api/v1/jobs/{job_id}/logs", params={"offset": 0, "limit": 200})
    assert logs.status_code == 200
    lines = logs.json()["data"]["lines"]
    assert isinstance(lines, list)
    assert lines and "message" in lines[0]

    # Wait for synthetic completion and verify run endpoints
    time.sleep(3.2)
    done = client.get(f"/api/v1/jobs/{job_id}")
    assert done.status_code == 200
    assert done.json()["data"]["status"] in {"succeeded", "success"}

    metrics = client.get("/api/v1/runs/contract-run-001/metrics")
    assert metrics.status_code == 200
    metrics_data = metrics.json()["data"]
    assert "metrics" in metrics_data
    assert "rmse" in metrics_data["metrics"]

    artifacts = client.get("/api/v1/runs/contract-run-001/artifacts")
    assert artifacts.status_code == 200
    art_data = artifacts.json()["data"]["artifacts"]
    assert "metrics_json" in art_data

    report = client.get("/api/v1/runs/contract-run-001/report")
    assert report.status_code == 200
    report_data = report.json()["data"]
    assert "report" in report_data

    # cancel contract still returns canceled payload
    cancel = client.post(f"/api/v1/jobs/{job_id}:cancel")
    assert cancel.status_code == 200
    canceled = cancel.json()["data"]
    assert canceled["status"] == "canceled"


def test_mobile_benchmark_ingest_api_contract() -> None:
    payload = {
        "run_id": "contract-mobile-001",
        "device_profile": "android_high_end",
        "expected_platform": "android",
        "benchmark_result": {
            "runtime_stack": "tflite",
            "fallback_chain": ["tflite", "keras"],
            "latency_ms": {"p50": 15.0, "p95": 19.0},
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
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["run_id"] == "contract-mobile-001"
    assert data["device_profile"] == "android_high_end"
    assert data["validation"]["ok"] is True
    assert data["record"]["metadata"]["platform"] == "android"
    assert "receipt_id" in data["receipt"]


def test_mobile_benchmark_batch_ingest_api_contract() -> None:
    payload = {
        "uploads": [
            {
                "run_id": "contract-mobile-batch-001",
                "device_profile": "android_high_end",
                "expected_platform": "android",
                "benchmark_result": {
                    "runtime_stack": "tflite",
                    "latency_ms": {"p50": 15.0, "p95": 19.0},
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
        ]
    }
    response = client.post("/api/v1/mobile/benchmarks:ingest-batch", json=payload)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["count"] == 1
    assert data["items"][0]["device_profile"] == "android_high_end"


def test_mobile_benchmark_summary_api_contract() -> None:
    payload = {
        "run_id": "contract-mobile-summary-001",
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
    }
    upload = client.post("/api/v1/mobile/benchmarks:ingest", json=payload)
    assert upload.status_code == 200

    response = client.get("/api/v1/mobile/benchmarks/summary", params={"run_id": "contract-mobile-summary-001"})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total_receipts"] >= 1
    assert "recent_uploads" in data
    assert data["platform_counts"]["ios"] >= 1
