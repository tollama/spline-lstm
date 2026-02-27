from __future__ import annotations

import contextlib
import os
import shlex
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from backend.app.config import ARTIFACTS_DIR, ROOT_DIR
from backend.app.store import JobRecord, JobStore
from backend.app.utils import sanitize_line, utc_now_iso


@dataclass
class JobRuntime:
    process: subprocess.Popen[str] | None = None
    logs: list[dict[str, Any]] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None

    def append_log(self, level: str, message: str, source: str = "runtime") -> None:
        with self.lock:
            self.logs.append({"ts": utc_now_iso(), "level": level, "source": source, "message": sanitize_line(message)})
            if len(self.logs) > 5000:
                self.logs = self.logs[-5000:]

    def read_logs(self, offset: int, limit: int) -> list[dict[str, Any]]:
        with self.lock:
            return list(self.logs[offset : offset + limit])


class JobExecutor:
    def __init__(self, store: JobStore):
        self.store = store
        self._runtimes: dict[str, JobRuntime] = {}
        self._lock = threading.Lock()

    def _mode(self) -> str:
        return os.getenv("SPLINE_BACKEND_EXECUTOR_MODE", "auto").strip().lower()

    def _command_template(self) -> list[str]:
        raw = os.getenv("SPLINE_BACKEND_RUNNER_CMD", f"{sys.executable} -m src.training.runner")
        return shlex.split(raw)

    def _timeout_sec(self) -> int:
        try:
            return max(5, int(os.getenv("SPLINE_BACKEND_RUN_TIMEOUT_SEC", "1800")))
        except Exception:
            return 1800

    def should_use_real(self) -> bool:
        mode = self._mode()
        if mode == "mock":
            return False
        if mode == "real":
            return True
        return bool(shlex.split(os.getenv("SPLINE_BACKEND_RUNNER_CMD", "")))

    def submit(self, rec: JobRecord) -> None:
        if self.should_use_real():
            rec.execution_mode = "real"
            self.store.upsert(rec)
            self._start_real_job(rec)
            return

        rec.execution_mode = "mock"
        self.store.upsert(rec)

    def _start_real_job(self, rec: JobRecord) -> None:
        runtime = JobRuntime()
        with self._lock:
            self._runtimes[rec.job_id] = runtime

        args = self._command_template() + [
            "--run-id",
            rec.run_id,
            "--artifacts-dir",
            str(ARTIFACTS_DIR),
            "--model-type",
            rec.model_type,
            "--feature-mode",
            rec.feature_mode,
            "--epochs",
            os.getenv("SPLINE_BACKEND_RUNNER_EPOCHS", "1"),
            "--verbose",
            "0",
        ]

        try:
            process = subprocess.Popen(
                args,
                cwd=str(ROOT_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                start_new_session=True,
            )
            runtime.process = process
            runtime.append_log("INFO", f"spawned pid={process.pid} cmd={' '.join(args)}")
            rec.status = "running"
            rec.step = "training"
            rec.progress = 5
            rec.message = "runner started"
            self.store.upsert(rec)

            threading.Thread(target=self._pump_stream, args=(rec.job_id, process.stdout, "stdout"), daemon=True).start()
            threading.Thread(target=self._pump_stream, args=(rec.job_id, process.stderr, "stderr"), daemon=True).start()
            threading.Thread(
                target=self._wait_and_finalize, args=(rec.job_id, process, self._timeout_sec()), daemon=True
            ).start()
        except Exception as exc:
            runtime.append_log("ERROR", f"executor spawn failed: {exc}")
            rec.status = "failed"
            rec.step = "failed"
            rec.progress = 100
            rec.error_message = f"executor spawn failed: {exc}"
            rec.message = "runner failed to start"
            self.store.upsert(rec)

    def _pump_stream(self, job_id: str, stream: Any, source: str) -> None:
        if stream is None:
            return
        for line in stream:
            runtime = self._runtimes.get(job_id)
            if runtime is None:
                return
            runtime.append_log("INFO" if source == "stdout" else "WARN", line, source=source)

    def _wait_and_finalize(self, job_id: str, process: subprocess.Popen[str], timeout_sec: int) -> None:
        from backend.app.routes.jobs import ensure_mock_run_artifacts

        runtime = self._runtimes.get(job_id)
        rec = self.store.get(job_id)
        if rec is None:
            return

        try:
            exit_code = process.wait(timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            self._terminate_process(process)
            exit_code = -signal.SIGKILL
            if runtime:
                runtime.append_log("ERROR", f"timeout exceeded ({timeout_sec}s)")

        rec = self.store.get(job_id)
        if rec is None:
            return

        rec.exit_code = int(exit_code)
        rec.progress = 100

        if rec.canceled:
            rec.status = "canceled"
            rec.step = "canceled"
            rec.message = "cancel accepted"
            rec.error_message = (
                rec.error_message
                or "\uc0ac\uc6a9\uc790 \uc694\uccad\uc73c\ub85c \uc791\uc5c5\uc774 \ucde8\uc18c\ub418\uc5c8\uc2b5\ub2c8\ub2e4."
            )
        elif exit_code == 0:
            rec.status = "succeeded"
            rec.step = "finished"
            rec.message = "completed"
            ensure_mock_run_artifacts(rec)
        else:
            rec.status = "failed"
            rec.step = "failed"
            rec.message = "failed"
            rec.error_message = rec.error_message or f"runner exited with code {exit_code}"
        self.store.upsert(rec)

        if runtime:
            runtime.finished_at = time.time()
            runtime.append_log("INFO", f"process finished exit_code={exit_code}")

    def _terminate_process(self, process: subprocess.Popen[str]) -> None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except Exception:
            with contextlib.suppress(Exception):
                process.terminate()
        try:
            process.wait(timeout=3)
        except Exception:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except Exception:
                with contextlib.suppress(Exception):
                    process.kill()

    def cancel(self, job_id: str) -> bool:
        runtime = self._runtimes.get(job_id)
        if runtime and runtime.process and runtime.process.poll() is None:
            runtime.append_log("WARN", "cancel requested")
            self._terminate_process(runtime.process)
            return True
        return False

    def logs(self, job_id: str, offset: int, limit: int) -> list[dict[str, Any]]:
        runtime = self._runtimes.get(job_id)
        if runtime is None:
            return []
        return runtime.read_logs(offset, limit)
