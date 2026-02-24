from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path

import numpy as np
import pytest
from src.training.runner import _validate_run_id_consistency


def _make_processed_bundle(base: Path, run_id: str) -> tuple[Path, Path]:
    pdir = base / "processed" / run_id
    mdir = base / "models" / run_id
    pdir.mkdir(parents=True, exist_ok=True)
    mdir.mkdir(parents=True, exist_ok=True)

    processed = pdir / "processed.npz"
    np.savez_compressed(processed, scaled=np.arange(20, dtype=float))

    meta = pdir / "meta.json"
    meta.write_text(json.dumps({"run_id": run_id}), encoding="utf-8")

    preprocessor = mdir / "preprocessor.pkl"
    with open(preprocessor, "wb") as f:
        pickle.dump({"run_id": run_id, "scaler": {}}, f)

    return processed, preprocessor


def test_run_id_guard_blocks_mismatch_between_cli_and_preprocessor(tmp_path: Path):
    processed, _ = _make_processed_bundle(tmp_path / "artifacts", run_id="run-a")
    wrong_preprocessor_dir = tmp_path / "artifacts" / "models" / "run-b"
    wrong_preprocessor_dir.mkdir(parents=True, exist_ok=True)
    wrong_preprocessor = wrong_preprocessor_dir / "preprocessor.pkl"
    with open(wrong_preprocessor, "wb") as f:
        pickle.dump({"run_id": "run-b"}, f)

    args = argparse.Namespace(processed_npz=str(processed), preprocessor_pkl=str(wrong_preprocessor))

    with pytest.raises(ValueError, match="run_id mismatch"):
        _validate_run_id_consistency("run-a", args)


def test_run_id_guard_accepts_matching_processed_and_preprocessor(tmp_path: Path):
    processed, preprocessor = _make_processed_bundle(tmp_path / "artifacts", run_id="run-ok")
    args = argparse.Namespace(processed_npz=str(processed), preprocessor_pkl=str(preprocessor))

    out = _validate_run_id_consistency("run-ok", args)
    assert out == preprocessor
