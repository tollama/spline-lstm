from __future__ import annotations

from src.utils.repro import build_phase3_run_metadata


def test_phase3_run_metadata_schema_v1_has_required_fields():
    meta = build_phase3_run_metadata(
        run_id="unit-meta",
        seed=42,
        deterministic=True,
        split_indices={
            "n_total": 100,
            "train": {"start": 0, "end": 64},
            "val": {"start": 64, "end": 80},
            "test": {"start": 80, "end": 100},
        },
        config={"sequence_length": 24, "horizon": 1},
        artifacts={
            "best_checkpoint": "artifacts/checkpoints/unit-meta/best.keras",
            "last_checkpoint": "artifacts/checkpoints/unit-meta/last.keras",
            "metrics": "artifacts/metrics/unit-meta.json",
            "report": "artifacts/reports/unit-meta.md",
        },
    )

    assert meta["schema_version"] == "phase3.runmeta.v1"
    assert meta["run_id"] == "unit-meta"
    assert "git" in meta and "commit" in meta["git"]
    assert "reproducibility" in meta
    assert "split_index" in meta["reproducibility"]
    assert meta["reproducibility"]["deterministic"]["enabled"] is True
    assert meta["reproducibility"]["split_index"]["raw"]["test_start"] == 80
