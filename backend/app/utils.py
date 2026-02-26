from __future__ import annotations

import copy
import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.config import _REQUEST_ID
from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse

_IDEMPOTENCY_LOCK = threading.Lock()
_IDEMPOTENCY_CACHE: dict[str, dict[str, Any]] = {}
_RATE_LOCK = threading.Lock()
_RATE_BUCKETS: dict[str, list[float]] = {}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def atomic_write_text(path: Path, text: str) -> None:
    ensure_parent(path)
    tmp = path.with_suffix(path.suffix + f".tmp.{uuid.uuid4().hex[:8]}")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def sanitize_line(raw: str) -> str:
    return raw.rstrip("\r\n")[:2000]


def rate_limit_or_raise(key: str, limit: int = 30, window_sec: int = 60) -> None:
    now = time.time()
    with _RATE_LOCK:
        bucket = [ts for ts in _RATE_BUCKETS.get(key, []) if now - ts < window_sec]
        if len(bucket) >= limit:
            raise HTTPException(status_code=429, detail="rate limit exceeded")
        bucket.append(now)
        _RATE_BUCKETS[key] = bucket


def idempotency_get(key: str) -> dict[str, Any] | None:
    with _IDEMPOTENCY_LOCK:
        return copy.deepcopy(_IDEMPOTENCY_CACHE.get(key))


def idempotency_put(key: str, value: dict[str, Any]) -> None:
    with _IDEMPOTENCY_LOCK:
        _IDEMPOTENCY_CACHE[key] = copy.deepcopy(value)


def corr(request: Request | None = None, job_id: str | None = None, run_id: str | None = None) -> dict[str, str]:
    rid = getattr(getattr(request, "state", None), "request_id", None) or _REQUEST_ID.get() or ""
    out: dict[str, str] = {"request_id": rid}
    if job_id:
        out["job_id"] = job_id
    if run_id:
        out["run_id"] = run_id
    return out


def read_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def jsonl_stream(chunks: list[dict[str, Any]]) -> StreamingResponse:
    def _iter():
        for chunk in chunks:
            yield json.dumps(chunk, ensure_ascii=False) + "\n"

    return StreamingResponse(_iter(), media_type="application/x-ndjson")
