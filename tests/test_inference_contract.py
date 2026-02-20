from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from src.training.baselines import Phase3BaselineComparisonError
from src.training.runner import (
    Phase3BaselineComparisonSkippedError,
    Phase3MetadataContractError,
    _map_exception_to_exit_code,
    _write_predictions_csv,
)


def test_predictions_csv_contract_columns_and_rows(tmp_path: Path):
    out_path = tmp_path / "predictions" / "run-1.csv"
    _write_predictions_csv(out_path, run_id="run-1", y_pred_last=np.array([0.11, 0.22], dtype=np.float32))

    assert out_path.exists()

    with open(out_path, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    assert rows
    assert list(rows[0].keys()) == ["run_id", "horizon_step", "y_pred", "generated_at"]
    assert [r["horizon_step"] for r in rows] == ["1", "2"]
    assert all(r["run_id"] == "run-1" for r in rows)
    assert all(r["generated_at"] for r in rows)


def test_runner_exit_code_mapping_contracts():
    assert _map_exception_to_exit_code(ValueError("run_id mismatch")) == 27
    assert _map_exception_to_exit_code(ValueError("X must be 3D")) == 23
    assert _map_exception_to_exit_code(FileNotFoundError("missing")) == 21
    assert _map_exception_to_exit_code(Phase3BaselineComparisonError("phase3 baseline comparison invalid")) == 32
    assert _map_exception_to_exit_code(Phase3BaselineComparisonSkippedError("x")) == 33
    assert _map_exception_to_exit_code(Phase3MetadataContractError("x")) == 34
    assert _map_exception_to_exit_code(RuntimeError("unknown backend crash")) == 24
