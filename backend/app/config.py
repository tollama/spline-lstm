from __future__ import annotations

import contextvars
import logging
import os
from pathlib import Path
from typing import Any

API_PREFIX = "/api/v1"
ROOT_DIR = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = Path(os.getenv("SPLINE_BACKEND_ARTIFACTS_DIR", str(ROOT_DIR / "artifacts"))).resolve()
STORE_PATH = Path(
    os.getenv("SPLINE_BACKEND_STORE_PATH", str(ROOT_DIR / "backend" / "data" / "jobs_store.json"))
).resolve()


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_csv(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if not raw:
        return default
    return [x.strip() for x in raw.split(",") if x.strip()]


def _security_config() -> dict[str, Any]:
    env = os.getenv("SPLINE_ENV", "dev").strip().lower()
    dev_mode = _env_flag("SPLINE_DEV_MODE", default=(env != "prod"))
    api_token = os.getenv("SPLINE_API_TOKEN")
    auth_required = not dev_mode
    if auth_required and not api_token:
        raise RuntimeError("SPLINE_API_TOKEN must be set when SPLINE_DEV_MODE=0")

    cors_origins = _env_csv(
        "SPLINE_CORS_ORIGINS",
        [
            "http://localhost",
            "http://127.0.0.1",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
            "http://localhost:4174",
            "http://127.0.0.1:4174",
        ]
        if dev_mode
        else [],
    )
    trusted_hosts = _env_csv("SPLINE_TRUSTED_HOSTS", ["localhost", "127.0.0.1", "testserver"])
    return {
        "env": env,
        "dev_mode": dev_mode,
        "api_token": api_token,
        "auth_required": auth_required,
        "cors_origins": cors_origins,
        "trusted_hosts": trusted_hosts,
    }


SECURITY = _security_config()

PHASE6_FLAGS = {
    "enable_adjusted_execute": _env_flag("SPLINE_PHASE6_ENABLE_ADJUSTED_EXECUTE", True),
    "enable_tollama_adapter": _env_flag("SPLINE_PHASE6_ENABLE_TOLLAMA_ADAPTER", True),
    "enable_mcp": _env_flag("SPLINE_PHASE6_ENABLE_MCP", True),
}

_REQUEST_ID: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = _REQUEST_ID.get() or ""
        return True


logger = logging.getLogger("backend.app")
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s %(message)s"))
    _h.addFilter(RequestIdFilter())
    logger.addHandler(_h)
logger.setLevel(logging.INFO)
logger.propagate = False
