from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pytest
from src.training.runner import (
    Phase3BaselineComparisonSkippedError,
    Phase3MetadataContractError,
    _build_error_payload,
    _load_series,
    _map_exception_to_exit_code,
    _validate_phase3_metadata_contract,
)


def _base_args(npz_path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        processed_npz=str(npz_path),
        input_npy=None,
        synthetic_samples=32,
        synthetic_noise=0.0,
        seed=42,
    )


def test_load_series_rejects_missing_required_artifact_keys(tmp_path: Path):
    npz_path = tmp_path / "processed.npz"
    np.savez_compressed(npz_path, scaled=np.arange(16, dtype=np.float32))

    with pytest.raises(ValueError, match="ARTIFACT_CONTRACT_ERROR"):
        _load_series(_base_args(npz_path))


def test_load_series_rejects_missing_split_contract_when_layout_is_artifacts_style(tmp_path: Path):
    run_id = "rid-a"
    npz_path = tmp_path / "artifacts" / "processed" / run_id / "processed.npz"
    npz_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        npz_path,
        scaled=np.arange(16, dtype=np.float32),
        feature_names=np.asarray(["target"], dtype=str),
        target_indices=np.asarray([0], dtype=int),
    )

    with pytest.raises(ValueError, match="split_contract.json"):
        _load_series(_base_args(npz_path))


def test_runner_error_payload_standardized_for_contract_violation():
    exc = ValueError("[ARTIFACT_CONTRACT_ERROR] processed.npz missing required keys: ['feature_names']")
    assert _map_exception_to_exit_code(exc) == 22

    payload = _build_error_payload(exc)
    assert payload["ok"] is False
    assert payload["exit_code"] == 22
    assert payload["error"]["code"] == "ARTIFACT_CONTRACT_ERROR"
    assert "feature_names" in payload["error"]["message"]


def test_runner_error_payload_standardized_for_run_id_mismatch():
    payload = _build_error_payload(ValueError("run_id mismatch: cli run_id=a but meta.json run_id=b"))
    assert payload["exit_code"] == 27
    assert payload["error"]["code"] == "RUN_ID_MISMATCH"
    assert payload["error"]["type"] == "ValueError"


def test_phase3_explicit_exceptions_map_deterministically_to_33_34():
    assert _map_exception_to_exit_code(Phase3BaselineComparisonSkippedError("skip")) == 33
    assert _map_exception_to_exit_code(Phase3MetadataContractError("invalid")) == 34


def test_phase3_metadata_contract_validator_raises_typed_error_for_invalid_schema():
    bad_runmeta = {
        "schema_version": "phase3.runmeta.v0",
        "run_id": "rid",
    }
    with pytest.raises(Phase3MetadataContractError, match="phase3 metadata contract invalid"):
        _validate_phase3_metadata_contract(run_id="rid", runmeta=bad_runmeta)


def test_phase3_metadata_contract_validator_rejects_wrong_run_id():
    bad_runmeta = {
        "schema_version": "phase3.runmeta.v1",
        "run_id": "other",
        "created_at": "2026-02-20T00:00:00",
        "project": "spline-lstm",
        "git": {"commit": None, "source": "unavailable"},
        "runtime": {"python": "3.11", "platform": "darwin", "backend": "tensorflow"},
        "reproducibility": {
            "seed": {"python": 1, "numpy": 1, "tensorflow": 1},
            "deterministic": {"enabled": True, "tf_deterministic_ops": True, "shuffle": False},
            "split_index": {
                "raw": {"n_total": 100, "train_end": 70, "val_end": 85, "test_start": 85},
                "sequence": {"n_train_seq": 50, "n_val_seq": 10, "n_test_seq": 10, "lookback": 24, "horizon": 1},
            },
        },
        "config": {},
        "artifacts": {},
    }
    with pytest.raises(Phase3MetadataContractError, match="run_id"):
        _validate_phase3_metadata_contract(run_id="rid", runmeta=bad_runmeta)


def test_phase3_metadata_contract_validator_rejects_split_type_mismatch_and_maps_exit_34():
    bad_runmeta = {
        "schema_version": "phase3.runmeta.v1",
        "run_id": "rid",
        "created_at": "2026-02-20T00:00:00",
        "project": "spline-lstm",
        "git": {"commit": None, "source": "unavailable"},
        "runtime": {"python": "3.11", "platform": "darwin", "backend": "tensorflow"},
        "reproducibility": {
            "seed": {"python": 1, "numpy": 1, "tensorflow": 1},
            "deterministic": {"enabled": True, "tf_deterministic_ops": True, "shuffle": False},
            "split_index": {
                "raw": {"n_total": "100", "train_end": 70, "val_end": 85, "test_start": 85},
                "sequence": {"n_train_seq": 50, "n_val_seq": 10, "n_test_seq": 10, "lookback": 24, "horizon": 1},
            },
        },
        "config": {},
        "artifacts": {},
    }
    with pytest.raises(Phase3MetadataContractError, match="reproducibility.split_index.raw.n_total") as e:
        _validate_phase3_metadata_contract(run_id="rid", runmeta=bad_runmeta)
    assert _map_exception_to_exit_code(e.value) == 34
