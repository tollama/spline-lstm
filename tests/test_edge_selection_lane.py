from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest
import src.training.edge_selection_lane as lane
from src.training.edge_selection_lane import (
    _build_benchmark_cmd,
    _build_release_gate_cmd,
    _collect_run_record,
    _extract_json_object,
    _load_teacher_references_tollama,
    _parse_profile_weights,
    _resolve_gate_device_results_dir,
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


def test_build_benchmark_cmd_supports_multiple_profiles() -> None:
    run = build_candidate_runs("exp", ["gru"], [41])[0]
    args = argparse.Namespace(
        artifacts_dir="artifacts",
        edge_sla="balanced",
        benchmark_iterations=20,
        benchmark_warmup=5,
    )
    cmd = _build_benchmark_cmd(args, run, ["android_high_end", "ios_high_end"])
    assert cmd.count("--device") == 2
    assert "android_high_end" in cmd
    assert "ios_high_end" in cmd


def test_build_release_gate_cmd_uses_required_profiles_csv() -> None:
    run = build_candidate_runs("exp", ["gru"], [41])[0]
    args = argparse.Namespace(
        artifacts_dir="artifacts",
        max_accuracy_degradation_pct=2.0,
        size_limit_mb=8.0,
        size_hard_limit_mb=15.0,
        min_stability_attempts=20,
        max_failures=0,
        skip_memory_check=False,
        allow_extended_size=False,
        memory_budget_mb=None,
        gate_device_results_dir_template="",
    )
    cmd = _build_release_gate_cmd(args, run, ["android_high_end", "ios_high_end"])
    assert "--required-profiles" in cmd
    idx = cmd.index("--required-profiles")
    assert cmd[idx + 1] == "android_high_end,ios_high_end"


def test_build_release_gate_cmd_adds_device_results_dir_from_template() -> None:
    run = build_candidate_runs("exp", ["gru"], [41])[0]
    args = argparse.Namespace(
        artifacts_dir="artifacts",
        max_accuracy_degradation_pct=2.0,
        size_limit_mb=8.0,
        size_hard_limit_mb=15.0,
        min_stability_attempts=20,
        max_failures=0,
        skip_memory_check=False,
        allow_extended_size=False,
        memory_budget_mb=None,
        gate_device_results_dir_template="artifacts/device_results/{run_id}",
    )
    cmd = _build_release_gate_cmd(args, run, ["android_high_end"])
    assert "--device-results-dir" in cmd
    idx = cmd.index("--device-results-dir")
    assert cmd[idx + 1] == f"artifacts/device_results/{run.run_id}"


def test_resolve_gate_device_results_dir_handles_empty_template() -> None:
    assert _resolve_gate_device_results_dir(gate_device_results_dir_template="", run_id="run-1") is None
    assert _resolve_gate_device_results_dir(gate_device_results_dir_template="x/{run_id}", run_id="run-1") == "x/run-1"


def test_parse_profile_weights_normalizes_values() -> None:
    out = _parse_profile_weights(
        "android_high_end=2,ios_high_end=1",
        ["android_high_end", "ios_high_end"],
    )
    assert out["android_high_end"] == pytest.approx(2.0 / 3.0)
    assert out["ios_high_end"] == pytest.approx(1.0 / 3.0)


def test_collect_run_record_aggregates_multi_profile_scores(tmp_path: Path) -> None:
    run_id = "sel-agg-001"
    artifacts = tmp_path / "artifacts"
    metrics_path = artifacts / "metrics" / f"{run_id}.json"
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(
        json.dumps(
            {
                "metrics": {"rmse": 0.99},
                "baselines": {"naive_last": {"rmse": 1.00}},
                "config": {"model_type": "gru"},
            }
        ),
        encoding="utf-8",
    )

    bench_root = artifacts / "edge_bench" / run_id
    bench_root.mkdir(parents=True, exist_ok=True)
    (bench_root / "android_high_end.json").write_text(
        json.dumps(
            {
                "edge_score": 80.0,
                "latency_p95_ms": 30.0,
                "size_mb": 4.0,
                "runtime_stack": "tflite",
                "status": "succeeded",
            }
        ),
        encoding="utf-8",
    )
    (bench_root / "ios_high_end.json").write_text(
        json.dumps(
            {
                "edge_score": 100.0,
                "latency_p95_ms": 40.0,
                "size_mb": 6.0,
                "runtime_stack": "onnx",
                "status": "succeeded",
            }
        ),
        encoding="utf-8",
    )
    (bench_root / "release_gate.json").write_text(
        json.dumps({"promotion_allowed": True, "blockers": []}),
        encoding="utf-8",
    )

    out = _collect_run_record(
        artifacts_dir=artifacts,
        run_id=run_id,
        selection_profile="android_high_end",
        score_profiles=["android_high_end", "ios_high_end"],
        score_profile_weights={"android_high_end": 0.25, "ios_high_end": 0.75},
    )

    assert out["edge_score"] == pytest.approx(95.0)
    assert out["latency_p95_ms"] == pytest.approx(37.5)
    assert out["size_mb"] == pytest.approx(5.5)
    assert out["benchmark_status"] == "succeeded"
    assert out["edge_score_by_profile"]["android_high_end"] == pytest.approx(80.0)
    assert out["edge_score_by_profile"]["ios_high_end"] == pytest.approx(100.0)


def test_extract_json_object_parses_fenced_json() -> None:
    text = "prefix ```json {\"name\":\"chronos-2\",\"rmse\":0.9} ``` suffix"
    parsed = _extract_json_object(text)
    assert parsed is not None
    assert parsed["name"] == "chronos-2"
    assert parsed["rmse"] == pytest.approx(0.9)


def test_load_teacher_references_tollama_parses_response(monkeypatch) -> None:
    args = argparse.Namespace(
        teacher_model=["chronos-2"],
        tollama_base_url="http://127.0.0.1:11434",
        teacher_timeout_sec=3.0,
        teacher_context_topk=3,
        teacher_prompt_template="",
        teacher_enable_forecast_fallback=True,
        teacher_backtest_length=64,
        teacher_backtest_horizon=12,
    )
    records = [
        {"run_id": "r1", "candidate": "gru", "seed": 41, "rmse": 1.01, "edge_score": 90.0, "accuracy_degradation_pct": 1.0},
    ]

    def _fake_post(url: str, payload: dict, timeout_sec: float) -> dict:
        assert url.endswith("/api/chat")
        assert payload["model"] == "chronos-2"
        assert timeout_sec == pytest.approx(3.0)
        return {
            "model": "chronos-2",
            "message": {"role": "assistant", "content": "{\"name\":\"chronos-2\",\"rmse\":0.84,\"notes\":\"ok\"}"},
            "done": True,
        }

    monkeypatch.setattr(lane, "_http_post_json", _fake_post)
    refs = _load_teacher_references_tollama(args=args, records=records)
    assert len(refs) == 1
    assert refs[0]["name"] == "chronos-2"
    assert refs[0]["rmse"] == pytest.approx(0.84)
    assert refs[0]["provider"] == "tollama"


def test_load_teacher_references_tollama_handles_non_json_content(monkeypatch) -> None:
    args = argparse.Namespace(
        teacher_model=["timesfm-2.5"],
        tollama_base_url="http://127.0.0.1:11434",
        teacher_timeout_sec=3.0,
        teacher_context_topk=3,
        teacher_prompt_template="",
        teacher_enable_forecast_fallback=False,
        teacher_backtest_length=64,
        teacher_backtest_horizon=12,
    )
    records = [
        {"run_id": "r1", "candidate": "gru", "seed": 41, "rmse": 1.01, "edge_score": 90.0, "accuracy_degradation_pct": 1.0},
    ]

    def _fake_post(url: str, payload: dict, timeout_sec: float) -> dict:
        return {
            "model": "timesfm-2.5",
            "message": {"role": "assistant", "content": "plain text without json"},
            "done": True,
        }

    monkeypatch.setattr(lane, "_http_post_json", _fake_post)
    refs = _load_teacher_references_tollama(args=args, records=records)
    assert len(refs) == 1
    assert refs[0]["name"] == "timesfm-2.5"
    assert refs[0]["rmse"] is None
    assert "error" in refs[0]


def test_load_teacher_references_tollama_uses_forecast_fallback(monkeypatch) -> None:
    args = argparse.Namespace(
        teacher_model=["chronos2"],
        tollama_base_url="http://127.0.0.1:11434",
        teacher_timeout_sec=3.0,
        teacher_context_topk=3,
        teacher_prompt_template="",
        teacher_enable_forecast_fallback=True,
        teacher_backtest_length=48,
        teacher_backtest_horizon=8,
    )
    records = [
        {"run_id": "r1", "candidate": "gru", "seed": 41, "rmse": 1.01, "edge_score": 90.0, "accuracy_degradation_pct": 1.0},
    ]

    def _fake_post(url: str, payload: dict, timeout_sec: float) -> dict:
        if url.endswith("/api/chat"):
            raise ValueError("chat endpoint unavailable")
        assert url.endswith("/api/forecast")
        assert payload["quantiles"] == [0.1, 0.5, 0.9]
        assert payload["options"] == {}
        return {
            "model": payload["model"],
            "forecasts": [
                {
                    "id": "teacher_backtest",
                    "freq": "H",
                    "start_timestamp": "2024-01-01T00:00:00Z",
                    "mean": [0.0] * payload["horizon"],
                }
            ],
        }

    monkeypatch.setattr(lane, "_http_post_json", _fake_post)
    refs = _load_teacher_references_tollama(args=args, records=records)
    assert len(refs) == 1
    assert refs[0]["provider"] == "tollama_forecast_backtest"
    assert refs[0]["rmse"] is not None
