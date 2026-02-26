from __future__ import annotations

import importlib
import sys

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
]


def _load_app(monkeypatch, *, dev_mode: bool, token: str | None = None, raise_server_exceptions: bool = True):
    monkeypatch.setenv("SPLINE_DEV_MODE", "1" if dev_mode else "0")
    if token is None:
        monkeypatch.delenv("SPLINE_API_TOKEN", raising=False)
    else:
        monkeypatch.setenv("SPLINE_API_TOKEN", token)
    monkeypatch.setenv("SPLINE_TRUSTED_HOSTS", "localhost,127.0.0.1,testserver")

    for mod_name in _BACKEND_MODULES:
        sys.modules.pop(mod_name, None)
    mod = importlib.import_module("backend.app.main")
    return mod, TestClient(mod.app, raise_server_exceptions=raise_server_exceptions)


def test_dev_mode_allows_requests_without_token(monkeypatch) -> None:
    _, client = _load_app(monkeypatch, dev_mode=True, token=None)
    res = client.get("/api/v1/dashboard/summary")
    assert res.status_code == 200


def test_prod_mode_requires_token(monkeypatch) -> None:
    _, client = _load_app(monkeypatch, dev_mode=False, token="secret-token")

    unauth = client.get("/api/v1/jobs")
    assert unauth.status_code == 401
    assert unauth.json()["error"] == "unauthorized"

    auth = client.get("/api/v1/jobs", headers={"X-API-Token": "secret-token"})
    assert auth.status_code == 200
    assert auth.json()["ok"] is True


def test_prod_mode_fails_fast_without_token(monkeypatch) -> None:
    monkeypatch.setenv("SPLINE_DEV_MODE", "0")
    monkeypatch.delenv("SPLINE_API_TOKEN", raising=False)
    monkeypatch.setenv("SPLINE_TRUSTED_HOSTS", "localhost,127.0.0.1,testserver")

    for mod_name in _BACKEND_MODULES:
        sys.modules.pop(mod_name, None)
    try:
        importlib.import_module("backend.app.main")
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "SPLINE_API_TOKEN" in str(exc)


def test_security_headers_present(monkeypatch) -> None:
    _, client = _load_app(monkeypatch, dev_mode=True, token=None)
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["x-frame-options"] == "DENY"


def test_internal_errors_are_sanitized(monkeypatch) -> None:
    mod, client = _load_app(monkeypatch, dev_mode=False, token="secret-token", raise_server_exceptions=False)

    def _boom(*args, **kwargs):
        raise RuntimeError("db password leaked: super-secret")

    # Patch read_json_if_exists in the runs route module where it's used
    runs_mod = importlib.import_module("backend.app.routes.runs")
    monkeypatch.setattr(runs_mod, "read_json_if_exists", _boom)
    res = client.get("/api/v1/runs/some-run/metrics", headers={"X-API-Token": "secret-token"})
    assert res.status_code == 500
    body = res.json()
    assert body["ok"] is False
    assert body["error"] == "internal server error"
    assert "super-secret" not in str(body)
