from __future__ import annotations

import importlib
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

_BACKEND_MODULES = [
    "backend.app.routes.runs",
    "backend.app.routes.tollama",
    "backend.app.routes.agent",
    "backend.app.routes.forecast",
    "backend.app.routes.jobs",
    "backend.app.routes.health",
    "backend.app.routes",
    "backend.app.executor",
    "backend.app.store",
    "backend.app.utils",
    "backend.app.models",
    "backend.app.config",
    "backend.app.main",
]


def _load_client(tmp_path: Path, monkeypatch, *, mode: str, cmd: str):
    artifacts_dir = tmp_path / "artifacts"
    store_path = tmp_path / "backend" / "data" / "jobs_store.json"
    monkeypatch.setenv("SPLINE_BACKEND_EXECUTOR_MODE", mode)
    monkeypatch.setenv("SPLINE_BACKEND_RUNNER_CMD", cmd)
    monkeypatch.setenv("SPLINE_BACKEND_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("SPLINE_BACKEND_STORE_PATH", str(store_path))
    monkeypatch.setenv("SPLINE_BACKEND_RUN_TIMEOUT_SEC", "5")

    for mod_name in _BACKEND_MODULES:
        sys.modules.pop(mod_name, None)

    backend_main = importlib.import_module("backend.app.main")
    return TestClient(backend_main.app)


def _wait_for_terminal(client: TestClient, job_id: str, timeout: float = 4.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        res = client.get(f"/api/v1/jobs/{job_id}")
        data = res.json()["data"]
        if data["status"] in {"succeeded", "failed", "canceled"}:
            return data
        time.sleep(0.1)
    raise AssertionError("job did not reach terminal state in time")


def test_executor_mode_mock_keeps_time_simulation(tmp_path: Path, monkeypatch) -> None:
    client = _load_client(tmp_path, monkeypatch, mode="mock", cmd="")

    create = client.post("/api/v1/pipelines/spline-tsfm:run", json={"run_id": "mode-mock-001"})
    assert create.status_code == 200
    payload = create.json()["data"]
    assert payload["execution_mode"] == "mock"

    job_id = payload["job_id"]
    done = _wait_for_terminal(client, job_id, timeout=4.5)
    assert done["status"] == "succeeded"


def test_real_executor_success_and_structured_logs(tmp_path: Path, monkeypatch) -> None:
    cmd = f"{sys.executable} -c \"import time; print('start'); time.sleep(0.2); print('ok')\""
    client = _load_client(tmp_path, monkeypatch, mode="real", cmd=cmd)

    create = client.post("/api/v1/pipelines/spline-tsfm:run", json={"run_id": "real-success-001"})
    payload = create.json()["data"]
    job_id = payload["job_id"]
    assert payload["execution_mode"] == "real"

    done = _wait_for_terminal(client, job_id)
    assert done["status"] == "succeeded"
    assert done["exit_code"] == 0

    logs = client.get(f"/api/v1/jobs/{job_id}/logs").json()["data"]["lines"]
    assert logs
    assert {"ts", "level", "source", "message"}.issubset(logs[0].keys())


def test_real_executor_failure_surfaces_exit_code(tmp_path: Path, monkeypatch) -> None:
    cmd = f"{sys.executable} -c \"import sys,time; print('bad'); time.sleep(0.1); sys.stderr.write('boom\\n'); sys.exit(3)\""
    client = _load_client(tmp_path, monkeypatch, mode="real", cmd=cmd)

    create = client.post("/api/v1/pipelines/spline-tsfm:run", json={"run_id": "real-fail-001"})
    job_id = create.json()["data"]["job_id"]

    done = _wait_for_terminal(client, job_id)
    assert done["status"] == "failed"
    assert done["exit_code"] == 3
    assert "runner exited" in (done.get("error_message") or "")


def test_real_executor_cancel(tmp_path: Path, monkeypatch) -> None:
    cmd = f"{sys.executable} -c \"import time; print('sleeping'); time.sleep(5)\""
    client = _load_client(tmp_path, monkeypatch, mode="real", cmd=cmd)

    create = client.post("/api/v1/pipelines/spline-tsfm:run", json={"run_id": "real-cancel-001"})
    job_id = create.json()["data"]["job_id"]
    time.sleep(0.2)

    cancel = client.post(f"/api/v1/jobs/{job_id}:cancel")
    assert cancel.status_code == 200

    done = _wait_for_terminal(client, job_id)
    assert done["status"] == "canceled"
