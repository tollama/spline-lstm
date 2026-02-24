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
