from __future__ import annotations

import pytest
from src.training.edge_selection_lane import (
    build_candidate_runs,
    compute_accuracy_degradation_pct,
    select_champion_fallback,
)


def test_build_candidate_runs_cross_product() -> None:
    runs = build_candidate_runs("exp-001", ["gru", "dlinear"], [41, 42])
    run_ids = [x.run_id for x in runs]
    assert len(runs) == 4
    assert "exp-001-gru-s41" in run_ids
    assert "exp-001-gru-s42" in run_ids
    assert "exp-001-dlinear-s41" in run_ids
    assert "exp-001-dlinear-s42" in run_ids


def test_compute_accuracy_degradation_pct() -> None:
    assert compute_accuracy_degradation_pct(1.02, 1.0) == pytest.approx(2.0)
    assert compute_accuracy_degradation_pct(0.98, 1.0) == pytest.approx(-2.0)
    assert compute_accuracy_degradation_pct(None, 1.0) is None
    assert compute_accuracy_degradation_pct(1.0, 0.0) is None


def test_select_champion_fallback_by_edge_score_then_accuracy() -> None:
    records = [
        {
            "run_id": "a",
            "edge_score": 91.0,
            "accuracy_degradation_pct": 1.8,
            "rmse": 1.02,
            "promotion_allowed": True,
        },
        {
            "run_id": "b",
            "edge_score": 92.5,
            "accuracy_degradation_pct": 1.9,
            "rmse": 1.03,
            "promotion_allowed": True,
        },
        {
            "run_id": "c",
            "edge_score": 88.0,
            "accuracy_degradation_pct": 2.8,
            "rmse": 1.06,
            "promotion_allowed": True,
        },
    ]
    out = select_champion_fallback(records, max_accuracy_degradation_pct=2.0, require_release_gate=True)
    assert out["champion"]["run_id"] == "b"
    assert out["fallback"]["run_id"] == "a"
    assert any(x["run_id"] == "c" for x in out["ineligible"])


def test_select_requires_release_gate_when_enabled() -> None:
    records = [
        {
            "run_id": "pass",
            "edge_score": 90.0,
            "accuracy_degradation_pct": 0.5,
            "rmse": 1.0,
            "promotion_allowed": True,
        },
        {
            "run_id": "blocked",
            "edge_score": 99.0,
            "accuracy_degradation_pct": 0.1,
            "rmse": 0.98,
            "promotion_allowed": False,
        },
    ]
    out = select_champion_fallback(records, max_accuracy_degradation_pct=2.0, require_release_gate=True)
    assert out["champion"]["run_id"] == "pass"
    assert out["fallback"] is None
