"""Reproducibility helpers for Phase 3."""

from __future__ import annotations

import os
import platform
import random
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np


def set_global_seed(seed: int, deterministic: bool = True) -> Dict[str, Any]:
    """Set seeds for Python, NumPy, and TensorFlow when available."""
    os.environ["PYTHONHASHSEED"] = str(seed)
    if deterministic:
        os.environ["TF_DETERMINISTIC_OPS"] = "1"
    random.seed(seed)
    np.random.seed(seed)

    tf_set = False
    tf_deterministic = False

    try:
        import tensorflow as tf  # type: ignore

        tf.random.set_seed(seed)
        tf_set = True
        if deterministic:
            try:
                tf.config.experimental.enable_op_determinism()
                tf_deterministic = True
            except Exception:
                tf_deterministic = False
    except Exception:
        tf_set = False

    return {
        "seed": int(seed),
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "python_random": True,
        "numpy_random": True,
        "tensorflow_random": tf_set,
        "tensorflow_op_determinism": tf_deterministic,
        "deterministic_requested": bool(deterministic),
    }


def get_git_commit_info(repo_dir: str | Path = ".") -> Dict[str, Optional[str]]:
    """Return git commit metadata.

    Policy:
    - git repository + valid HEAD -> commit_hash is full SHA, source='git'
    - non-git or unavailable -> commit_hash=None, source='unavailable'
    """
    try:
        commit_out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_dir),
            stderr=subprocess.DEVNULL,
            text=True,
        )
        commit = commit_out.strip() or None

        branch_out = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(repo_dir),
            stderr=subprocess.DEVNULL,
            text=True,
        )
        branch = branch_out.strip() or None

        status_out = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=str(repo_dir),
            stderr=subprocess.DEVNULL,
            text=True,
        )
        dirty = bool(status_out.strip())

        if commit:
            return {
                "commit_hash": commit,
                "source": "git",
                "branch": branch,
                "dirty": dirty,
            }
        return {"commit_hash": None, "source": "unavailable", "branch": None, "dirty": None}
    except Exception:
        return {"commit_hash": None, "source": "unavailable", "branch": None, "dirty": None}


def build_run_metadata(
    run_id: str,
    seed_info: Dict[str, Any],
    config: Dict[str, Any],
    repo_dir: str | Path = ".",
) -> Dict[str, Any]:
    """Build a metadata payload for reproducible run tracking (legacy-compatible)."""
    git_info = get_git_commit_info(repo_dir)
    return {
        "run_id": run_id,
        "created_at": datetime.now().isoformat(),
        "cwd": str(Path(repo_dir).resolve()),
        "commit_hash": git_info["commit_hash"],
        "commit_hash_source": git_info["source"],
        # Backward-compatible alias.
        "git_commit": git_info["commit_hash"],
        "seed": seed_info,
        "config_snapshot": config,
    }


def build_phase3_run_metadata(
    run_id: str,
    seed: int,
    deterministic: bool,
    split_indices: Dict[str, Any],
    config: Dict[str, Any],
    artifacts: Dict[str, str],
    status: str = "success",
    error: Optional[str] = None,
    repo_dir: str | Path = ".",
) -> Dict[str, Any]:
    """Build Phase 3 fixed run metadata schema (phase3.runmeta.v1)."""
    git_info = get_git_commit_info(repo_dir)
    seq = {
        "n_train_seq": int(split_indices.get("train", {}).get("end", 0) - split_indices.get("train", {}).get("start", 0)),
        "n_val_seq": int(split_indices.get("val", {}).get("end", 0) - split_indices.get("val", {}).get("start", 0)),
        "n_test_seq": int(split_indices.get("test", {}).get("end", 0) - split_indices.get("test", {}).get("start", 0)),
        "lookback": int(config.get("sequence_length", 0)),
        "horizon": int(config.get("horizon", 1)),
    }
    raw = {
        "n_total": int(split_indices.get("n_total", 0)),
        "train_end": int(split_indices.get("train", {}).get("end", 0)),
        "val_end": int(split_indices.get("val", {}).get("end", 0)),
        "test_start": int(split_indices.get("test", {}).get("start", 0)),
    }

    return {
        "schema_version": "phase3.runmeta.v1",
        "run_id": run_id,
        "created_at": datetime.now().isoformat(),
        "project": "spline-lstm",
        "git": {
            "commit": git_info.get("commit_hash"),
            "branch": git_info.get("branch"),
            "dirty": git_info.get("dirty"),
            "source": git_info.get("source"),
        },
        "runtime": {
            "python": sys.version.split()[0],
            "platform": platform.system().lower(),
            "backend": "tensorflow",
        },
        "reproducibility": {
            "seed": {"python": int(seed), "numpy": int(seed), "tensorflow": int(seed)},
            "deterministic": {
                "enabled": bool(deterministic),
                "tf_deterministic_ops": bool(deterministic),
                "shuffle": False,
            },
            "split_index": {
                "raw": raw,
                "sequence": seq,
            },
        },
        "config": config,
        "artifacts": artifacts,
        "status": status,
        "error": error,
    }
