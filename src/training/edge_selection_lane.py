"""Edge candidate lane orchestrator for champion/fallback selection."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from src.training.edge import utc_now_iso


@dataclass(frozen=True)
class CandidateRun:
    candidate: str
    seed: int
    run_id: str


def _parse_csv(raw: str) -> list[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


def _parse_int_csv(raw: str) -> list[int]:
    out: list[int] = []
    for token in _parse_csv(raw):
        out.append(int(token))
    return out


def _build_experiment_id(prefix: str = "edge-lane") -> str:
    return f"{prefix}-{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def build_candidate_runs(experiment_id: str, candidates: list[str], seeds: list[int]) -> list[CandidateRun]:
    runs: list[CandidateRun] = []
    for candidate in candidates:
        for seed in seeds:
            run_id = f"{experiment_id}-{candidate}-s{seed}"
            runs.append(CandidateRun(candidate=candidate, seed=seed, run_id=run_id))
    return runs


def compute_accuracy_degradation_pct(model_rmse: float | None, baseline_rmse: float | None) -> float | None:
    if model_rmse is None or baseline_rmse is None or baseline_rmse <= 0:
        return None
    return float((model_rmse - baseline_rmse) / baseline_rmse * 100.0)


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _run_command(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True)
    return int(proc.returncode), proc.stdout, proc.stderr


def _default_hidden_units(candidate: str) -> list[int]:
    if candidate == "dlinear":
        return [32]
    if candidate in {"gru", "lstm", "attention_lstm", "tcn"}:
        return [32, 16]
    return [32, 16]


def _collect_run_record(*, artifacts_dir: Path, run_id: str, selection_profile: str) -> dict[str, Any]:
    metrics_payload = _load_json(artifacts_dir / "metrics" / f"{run_id}.json") or {}
    metrics = metrics_payload.get("metrics", {}) if isinstance(metrics_payload.get("metrics"), dict) else {}
    baselines = metrics_payload.get("baselines", {}) if isinstance(metrics_payload.get("baselines"), dict) else {}
    baseline_naive = baselines.get("naive_last", {}) if isinstance(baselines.get("naive_last"), dict) else {}

    model_rmse = _safe_float(metrics.get("rmse"))
    baseline_rmse = _safe_float(baseline_naive.get("rmse"))
    degradation_pct = compute_accuracy_degradation_pct(model_rmse, baseline_rmse)

    bench_payload = _load_json(artifacts_dir / "edge_bench" / run_id / f"{selection_profile}.json") or {}
    release_gate = _load_json(artifacts_dir / "edge_bench" / run_id / "release_gate.json") or {}

    return {
        "run_id": run_id,
        "model_type": metrics_payload.get("config", {}).get("model_type")
        if isinstance(metrics_payload.get("config"), dict)
        else None,
        "rmse": model_rmse,
        "baseline_rmse": baseline_rmse,
        "accuracy_degradation_pct": degradation_pct,
        "edge_score": _safe_float(bench_payload.get("edge_score")),
        "latency_p95_ms": _safe_float(bench_payload.get("latency_p95_ms")),
        "size_mb": _safe_float(bench_payload.get("size_mb")),
        "runtime_stack": bench_payload.get("runtime_stack"),
        "benchmark_status": bench_payload.get("status"),
        "promotion_allowed": release_gate.get("promotion_allowed"),
        "promotion_blockers": release_gate.get("blockers") if isinstance(release_gate.get("blockers"), list) else [],
    }


def select_champion_fallback(
    records: list[dict[str, Any]],
    *,
    max_accuracy_degradation_pct: float,
    require_release_gate: bool,
) -> dict[str, Any]:
    eligible: list[dict[str, Any]] = []
    ineligible: list[dict[str, Any]] = []

    for record in records:
        blockers: list[str] = []
        edge_score = _safe_float(record.get("edge_score"))
        degradation = _safe_float(record.get("accuracy_degradation_pct"))

        if edge_score is None:
            blockers.append("missing edge_score")
        if degradation is None:
            blockers.append("missing accuracy_degradation_pct")
        elif degradation > max_accuracy_degradation_pct:
            blockers.append(
                f"accuracy_degradation_pct={degradation:.4f} > allowed={float(max_accuracy_degradation_pct):.4f}"
            )

        if require_release_gate and record.get("promotion_allowed") is not True:
            blockers.append("release gate did not pass")

        target = eligible if not blockers else ineligible
        target.append({**record, "eligibility_blockers": blockers})

    eligible_sorted = sorted(
        eligible,
        key=lambda r: (
            -float(r.get("edge_score", float("-inf"))),
            float(r.get("accuracy_degradation_pct", float("inf"))),
            float(r.get("rmse", float("inf"))),
        ),
    )

    champion = eligible_sorted[0] if eligible_sorted else None
    fallback = eligible_sorted[1] if len(eligible_sorted) > 1 else None
    return {
        "champion": champion,
        "fallback": fallback,
        "eligible": eligible_sorted,
        "ineligible": ineligible,
    }


def _load_teacher_references(paths: list[str]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for raw in paths:
        payload = _load_json(Path(raw))
        if payload is None:
            continue
        refs.append(payload)
    return refs


def _build_runner_cmd(args: argparse.Namespace, run: CandidateRun) -> list[str]:
    cmd = [
        sys.executable,
        "-m",
        "src.training.runner",
        "--run-id",
        run.run_id,
        "--artifacts-dir",
        args.artifacts_dir,
        "--model-type",
        run.candidate,
        "--feature-mode",
        "univariate",
        "--synthetic",
        "--synthetic-samples",
        str(args.synthetic_samples),
        "--epochs",
        str(args.epochs),
        "--batch-size",
        str(args.batch_size),
        "--sequence-length",
        str(args.sequence_length),
        "--horizon",
        str(args.horizon),
        "--loss",
        args.loss,
        "--edge-profile",
        args.edge_profile,
        "--edge-sla",
        args.edge_sla,
        "--export-formats",
        args.export_formats,
        "--quantization",
        args.quantization,
        "--seed",
        str(run.seed),
        "--verbose",
        "0",
    ]

    units = _parse_int_csv(args.hidden_units) if args.hidden_units else _default_hidden_units(run.candidate)
    cmd.append("--hidden-units")
    cmd.extend([str(x) for x in units])

    if args.quantization == "int8":
        cmd.extend(["--int8-calibration-samples", str(args.int8_calibration_samples)])
    cmd.extend(["--parity-max-abs-diff", str(args.parity_max_abs_diff)])
    cmd.extend(["--parity-rmse-max", str(args.parity_rmse_max)])
    if args.parity_enforce:
        cmd.append("--parity-enforce")
    else:
        cmd.append("--no-parity-enforce")
    return cmd


def _build_benchmark_cmd(args: argparse.Namespace, run: CandidateRun) -> list[str]:
    return [
        sys.executable,
        "scripts/benchmark_edge.py",
        "--run-id",
        run.run_id,
        "--artifacts-dir",
        args.artifacts_dir,
        "--edge-sla",
        args.edge_sla,
        "--device",
        args.selection_profile,
        "--iterations",
        str(args.benchmark_iterations),
        "--warmup",
        str(args.benchmark_warmup),
    ]


def _build_release_gate_cmd(args: argparse.Namespace, run: CandidateRun) -> list[str]:
    cmd = [
        sys.executable,
        "scripts/edge_release_gate.py",
        "--run-id",
        run.run_id,
        "--artifacts-dir",
        args.artifacts_dir,
        "--required-profiles",
        args.selection_profile,
        "--max-accuracy-degradation-pct",
        str(args.max_accuracy_degradation_pct),
        "--size-limit-mb",
        str(args.size_limit_mb),
        "--size-hard-limit-mb",
        str(args.size_hard_limit_mb),
        "--min-stability-attempts",
        str(args.min_stability_attempts),
        "--max-failures",
        str(args.max_failures),
    ]
    if args.skip_memory_check:
        cmd.append("--skip-memory-check")
    if args.allow_extended_size:
        cmd.append("--allow-extended-size")
    if args.memory_budget_mb is not None:
        cmd.extend(["--memory-budget-mb", str(args.memory_budget_mb)])
    return cmd


def run(args: argparse.Namespace) -> dict[str, Any]:
    experiment_id = args.experiment_id or _build_experiment_id()
    workspace = Path(args.workspace_dir).resolve()
    artifacts_dir = Path(args.artifacts_dir).resolve()
    candidates = _parse_csv(args.candidates)
    seeds = _parse_int_csv(args.seeds)

    runs = build_candidate_runs(experiment_id, candidates, seeds)
    command_logs: list[dict[str, Any]] = []

    for run_item in runs:
        if args.execute:
            runner_cmd = _build_runner_cmd(args, run_item)
            rc, stdout, stderr = _run_command(runner_cmd, cwd=workspace)
            command_logs.append(
                {
                    "run_id": run_item.run_id,
                    "stage": "runner",
                    "cmd": runner_cmd,
                    "returncode": rc,
                    "stdout_tail": stdout[-args.log_tail_chars :],
                    "stderr_tail": stderr[-args.log_tail_chars :],
                }
            )
            if rc != 0 and not args.continue_on_error:
                raise RuntimeError(f"runner failed for run_id={run_item.run_id} rc={rc}")

            bench_cmd = _build_benchmark_cmd(args, run_item)
            rc, stdout, stderr = _run_command(bench_cmd, cwd=workspace)
            command_logs.append(
                {
                    "run_id": run_item.run_id,
                    "stage": "benchmark",
                    "cmd": bench_cmd,
                    "returncode": rc,
                    "stdout_tail": stdout[-args.log_tail_chars :],
                    "stderr_tail": stderr[-args.log_tail_chars :],
                }
            )
            if rc != 0 and not args.continue_on_error:
                raise RuntimeError(f"benchmark failed for run_id={run_item.run_id} rc={rc}")

            gate_cmd = _build_release_gate_cmd(args, run_item)
            rc, stdout, stderr = _run_command(gate_cmd, cwd=workspace)
            command_logs.append(
                {
                    "run_id": run_item.run_id,
                    "stage": "release_gate",
                    "cmd": gate_cmd,
                    "returncode": rc,
                    "stdout_tail": stdout[-args.log_tail_chars :],
                    "stderr_tail": stderr[-args.log_tail_chars :],
                }
            )
            if rc != 0 and not args.continue_on_error:
                raise RuntimeError(f"release gate failed for run_id={run_item.run_id} rc={rc}")

    records: list[dict[str, Any]] = []
    for run_item in runs:
        base = _collect_run_record(artifacts_dir=artifacts_dir, run_id=run_item.run_id, selection_profile=args.selection_profile)
        records.append(
            {
                **base,
                "candidate": run_item.candidate,
                "seed": run_item.seed,
            }
        )

    selection = select_champion_fallback(
        records,
        max_accuracy_degradation_pct=args.max_accuracy_degradation_pct,
        require_release_gate=args.require_release_gate,
    )
    teacher_refs = _load_teacher_references(args.teacher_reference_json)

    champion_rmse = _safe_float(selection.get("champion", {}).get("rmse")) if selection.get("champion") else None
    teacher_comparison: list[dict[str, Any]] = []
    for ref in teacher_refs:
        teacher_rmse = _safe_float(ref.get("rmse"))
        gap = None if champion_rmse is None or teacher_rmse is None else float(champion_rmse - teacher_rmse)
        teacher_comparison.append({"name": ref.get("name"), "rmse": teacher_rmse, "champion_rmse_gap": gap, "raw": ref})

    output = {
        "experiment_id": experiment_id,
        "generated_at": utc_now_iso(),
        "config": {
            "candidates": candidates,
            "seeds": seeds,
            "horizon_buckets": args.horizon_buckets,
            "bucket_weights": args.bucket_weights,
            "max_accuracy_degradation_pct": args.max_accuracy_degradation_pct,
            "selection_profile": args.selection_profile,
            "require_release_gate": args.require_release_gate,
            "execute": args.execute,
        },
        "records": records,
        "selection": selection,
        "teacher_references": teacher_comparison,
        "command_logs": command_logs,
    }

    out_dir = artifacts_dir / "edge_selection" / experiment_id
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "selection.json"
    md_path = out_dir / "selection.md"

    json_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    champion = selection.get("champion")
    fallback = selection.get("fallback")
    report = (
        "# Edge Candidate Lane Report\n\n"
        f"- experiment_id: `{experiment_id}`\n"
        f"- selection_profile: `{args.selection_profile}`\n"
        f"- max_accuracy_degradation_pct: `{args.max_accuracy_degradation_pct}`\n"
        f"- champion: `{champion.get('run_id') if champion else 'none'}`\n"
        f"- fallback: `{fallback.get('run_id') if fallback else 'none'}`\n"
        f"- json: `{json_path}`\n"
    )
    md_path.write_text(report, encoding="utf-8")
    output["artifacts"] = {"selection_json": str(json_path), "selection_report": str(md_path)}
    return output


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run edge model candidate lane and select champion/fallback")
    p.add_argument("--experiment-id", type=str, default=None)
    p.add_argument("--workspace-dir", type=str, default=".")
    p.add_argument("--artifacts-dir", type=str, default="artifacts")
    p.add_argument("--candidates", type=str, default="gru,tcn,dlinear")
    p.add_argument("--seeds", type=str, default="41,42,43")
    p.add_argument("--hidden-units", type=str, default="")
    p.add_argument("--loss", type=str, default="mse")
    p.add_argument("--epochs", type=int, default=1)
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--sequence-length", type=int, default=24)
    p.add_argument("--horizon", type=int, default=24)
    p.add_argument("--synthetic-samples", type=int, default=800)
    p.add_argument("--export-formats", type=str, default="onnx,tflite")
    p.add_argument("--quantization", type=str, choices=["none", "fp16", "int8"], default="fp16")
    p.add_argument("--int8-calibration-samples", type=int, default=64)
    p.add_argument("--parity-max-abs-diff", type=float, default=0.5)
    p.add_argument("--parity-rmse-max", type=float, default=0.2)
    p.add_argument("--parity-enforce", action="store_true", default=False)
    p.add_argument("--no-parity-enforce", action="store_false", dest="parity_enforce")
    p.add_argument("--edge-profile", type=str, default="desktop_reference")
    p.add_argument("--edge-sla", type=str, default="balanced")
    p.add_argument("--selection-profile", type=str, default="desktop_reference")
    p.add_argument("--benchmark-iterations", type=int, default=20)
    p.add_argument("--benchmark-warmup", type=int, default=5)
    p.add_argument("--max-accuracy-degradation-pct", type=float, default=2.0)
    p.add_argument("--size-limit-mb", type=float, default=8.0)
    p.add_argument("--size-hard-limit-mb", type=float, default=15.0)
    p.add_argument("--allow-extended-size", action="store_true", default=False)
    p.add_argument("--memory-budget-mb", type=float, default=None)
    p.add_argument("--skip-memory-check", action="store_true", default=False)
    p.add_argument("--min-stability-attempts", type=int, default=20)
    p.add_argument("--max-failures", type=int, default=0)
    p.add_argument("--horizon-buckets", type=str, default="1-24,25-72,73-168")
    p.add_argument("--bucket-weights", type=str, default="0.50,0.30,0.20")
    p.add_argument("--teacher-reference-json", action="append", default=[])
    p.add_argument("--execute", action="store_true", default=True)
    p.add_argument("--no-execute", action="store_false", dest="execute")
    p.add_argument("--require-release-gate", action="store_true", default=True)
    p.add_argument("--no-require-release-gate", action="store_false", dest="require_release_gate")
    p.add_argument("--continue-on-error", action="store_true", default=False)
    p.add_argument("--log-tail-chars", type=int, default=4000)
    return p


def main() -> None:
    args = build_parser().parse_args()
    out = run(args)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
