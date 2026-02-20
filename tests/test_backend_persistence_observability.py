from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import main as backend_main
from backend.app.main import JobRecord, JobStore, app


client = TestClient(app)


def test_job_store_corruption_quarantine(tmp_path: Path) -> None:
    path = tmp_path / "jobs_store.json"
    path.write_text('{"jobs": [', encoding="utf-8")

    store = JobStore(path)
    assert store.diagnostics()["records"] == 0
    assert store.corrupted_file is not None
    assert not path.exists()
    assert Path(store.corrupted_file).exists()


def test_job_store_atomic_upsert_and_reload(tmp_path: Path) -> None:
    path = tmp_path / "jobs_store.json"
    store = JobStore(path)

    rec = JobRecord(
        job_id="job-1",
        run_id="run-1",
        model_type="lstm",
        feature_mode="univariate",
        created_at=1.0,
    )
    store.upsert(rec)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["jobs"][0]["job_id"] == "job-1"

    reloaded = JobStore(path)
    got = reloaded.get("job-1")
    assert got is not None
    assert got.run_id == "run-1"


def test_correlation_id_surfaces_in_response_and_logs() -> None:
    req_id = "req-contract-abc123"
    create = client.post(
        "/api/v1/pipelines/spline-tsfm:run",
        headers={"x-request-id": req_id},
        json={"run_id": "corr-run-001", "model_type": "gru", "feature_mode": "multivariate"},
    )
    assert create.status_code == 200
    body = create.json()["data"]
    job_id = body["job_id"]
    assert body["correlation"]["request_id"] == req_id
    assert body["correlation"]["job_id"] == job_id
    assert create.headers.get("x-request-id") == req_id

    logs = client.get(f"/api/v1/jobs/{job_id}/logs", headers={"x-request-id": req_id})
    assert logs.status_code == 200
    lines = logs.json()["data"]["lines"]
    assert lines
    assert all(line.get("request_id") == req_id for line in lines)
    assert all(line.get("job_id") == job_id for line in lines)


def test_health_details_include_store_diagnostics() -> None:
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    data = health.json()["data"]
    assert data["status"] == "healthy"
    details = data.get("details")
    assert isinstance(details, dict)
    assert "store" in details
    assert "store_dir_writable" in details
    assert details["store"]["path"] == str(backend_main.STORE_PATH)
