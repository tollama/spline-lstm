from __future__ import annotations

import fcntl
import json
import os
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.config import logger
from backend.app.utils import atomic_write_text, ensure_parent, utc_now_iso


@dataclass
class JobRecord:
    job_id: str
    run_id: str
    model_type: str
    feature_mode: str
    created_at: float
    status: str = "queued"
    message: str | None = None
    step: str | None = "queued"
    progress: int | None = 0
    updated_at: str | None = None
    error_message: str | None = None
    canceled: bool = False
    execution_mode: str = "mock"
    exit_code: int | None = None


class JobStore:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()
        self._records: dict[str, JobRecord] = {}
        self.corrupted_file: str | None = None
        self.last_save_error: str | None = None
        self._load()

    @property
    def lock_path(self) -> Path:
        return self.path.with_suffix(self.path.suffix + ".lock")

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception as exc:
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            bad_path = self.path.with_suffix(self.path.suffix + f".corrupt.{ts}")
            try:
                os.replace(self.path, bad_path)
                self.corrupted_file = str(bad_path)
            except Exception:
                self.corrupted_file = str(self.path)
            logger.error("job_store_corrupt_json path=%s error=%s", self.path, exc)
            return
        if not isinstance(raw, dict):
            return
        for item in raw.get("jobs", []):
            try:
                rec = JobRecord(**item)
            except Exception:
                continue
            self._records[rec.job_id] = rec

    def _save(self) -> None:
        ensure_parent(self.path)
        payload = {"jobs": [asdict(v) for v in self._records.values()]}
        serialized = json.dumps(payload, ensure_ascii=False, indent=2)
        try:
            with open(self.lock_path, "a+", encoding="utf-8") as lockf:
                fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)
                atomic_write_text(self.path, serialized)
                fcntl.flock(lockf.fileno(), fcntl.LOCK_UN)
            self.last_save_error = None
        except Exception as exc:
            self.last_save_error = str(exc)
            logger.error("job_store_save_failed path=%s error=%s", self.path, exc)
            raise

    def upsert(self, rec: JobRecord) -> None:
        with self.lock:
            rec.updated_at = utc_now_iso()
            self._records[rec.job_id] = rec
            self._save()

    def get(self, job_id: str) -> JobRecord | None:
        with self.lock:
            rec = self._records.get(job_id)
            return JobRecord(**asdict(rec)) if rec else None

    def list_recent(self, limit: int = 20) -> list[JobRecord]:
        with self.lock:
            values = list(self._records.values())
        values.sort(key=lambda x: x.created_at, reverse=True)
        return [JobRecord(**asdict(v)) for v in values[:limit]]

    def diagnostics(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "lock_path": str(self.lock_path),
            "records": len(self._records),
            "corrupted_file": self.corrupted_file,
            "last_save_error": self.last_save_error,
        }
