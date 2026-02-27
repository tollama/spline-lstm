"""Edge candidate lane orchestrator for champion/fallback selection."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib import error as url_error
from urllib import request as url_request

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


def _http_post_json(url: str, payload: dict[str, Any], timeout_sec: float) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = url_request.Request(
        url=url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with url_request.urlopen(req, timeout=float(timeout_sec)) as resp:
        raw = resp.read().decode("utf-8")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("tollama response must be a JSON object")
    return parsed


def _extract_json_object(text: str) -> dict[str, Any] | None:
    raw = text.strip()
    if not raw:
        return None

    candidates: list[str] = [raw]
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            snippet = part.strip()
            if not snippet:
                continue
            if snippet.startswith("json"):
                snippet = snippet[4:].strip()
            candidates.append(snippet)

    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        candidates.append(raw[start : end + 1])

    for cand in candidates:
        try:
            parsed = json.loads(cand)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _compact_teacher_context(records: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    ranked = sorted(
        records,
        key=lambda r: (
            -(_safe_float(r.get("edge_score")) if _safe_float(r.get("edge_score")) is not None else float("-inf")),
            (_safe_float(r.get("accuracy_degradation_pct")) if _safe_float(r.get("accuracy_degradation_pct")) is not None else float("inf")),
            (_safe_float(r.get("rmse")) if _safe_float(r.get("rmse")) is not None else float("inf")),
        ),
    )
    out: list[dict[str, Any]] = []
    for row in ranked[: max(1, int(top_k))]:
        out.append(
            {
                "run_id": row.get("run_id"),
                "candidate": row.get("candidate"),
                "seed": row.get("seed"),
                "rmse": row.get("rmse"),
                "edge_score": row.get("edge_score"),
                "accuracy_degradation_pct": row.get("accuracy_degradation_pct"),
                "promotion_allowed": row.get("promotion_allowed"),
            }
        )
    return out


def _default_teacher_prompt(model: str, context_rows: list[dict[str, Any]]) -> str:
    summary = json.dumps(context_rows, ensure_ascii=False)
    return (
        "You are evaluating a teacher forecasting model for edge selection. "
        f"Teacher model hint: {model}. "
        "Return STRICT JSON only with keys: name (string), rmse (number|null), notes (string). "
        f"Candidate summary: {summary}"
    )


def _resolve_teacher_prompt(
    *,
    template: str,
    model: str,
    context_rows: list[dict[str, Any]],
) -> str:
    if not template.strip():
        return _default_teacher_prompt(model=model, context_rows=context_rows)

    context_json = json.dumps(context_rows, ensure_ascii=False)
    try:
        return template.format(model=model, candidate_summary_json=context_json)
    except KeyError:
        # Keep operation robust when template placeholders are incomplete.
        return template


def _parse_tollama_teacher_reference(*, model: str, response_payload: dict[str, Any]) -> dict[str, Any]:
    message = response_payload.get("message")
    content = message.get("content") if isinstance(message, dict) else response_payload.get("response")
    text = str(content) if content is not None else ""
    parsed = _extract_json_object(text)

    if parsed is None:
        return {
            "name": model,
            "rmse": None,
            "provider": "tollama",
            "model": model,
            "error": "teacher response did not include parseable JSON object",
            "raw_response": response_payload,
        }

    return {
        "name": str(parsed.get("name") or model),
        "rmse": _safe_float(parsed.get("rmse")),
        "provider": "tollama",
        "model": model,
        "notes": parsed.get("notes"),
        "raw_response": response_payload,
    }


def _build_teacher_backtest_series(*, length: int) -> tuple[list[str], list[float]]:
    n = max(16, int(length))
    t0 = datetime(2024, 1, 1, 0, 0, 0)
    timestamps = [(t0 + timedelta(hours=i)).isoformat() + "Z" for i in range(n)]
    values = [
        float(0.03 * i + 2.0 * math.sin(i / 8.0) + 0.6 * math.cos(i / 13.0))
        for i in range(n)
    ]
    return timestamps, values


def _parse_tollama_forecast_rmse(*, response_payload: dict[str, Any], actual: list[float], horizon: int) -> float:
    forecasts = response_payload.get("forecasts")
    if not isinstance(forecasts, list) or not forecasts:
        raise ValueError(f"forecast response missing forecasts payload: {response_payload}")
    first = forecasts[0] if isinstance(forecasts[0], dict) else {}
    mean = first.get("mean")
    if not isinstance(mean, list) or len(mean) < horizon:
        raise ValueError("forecast response mean length is shorter than requested horizon")

    pred = [_safe_float(x) for x in mean[:horizon]]
    if any(x is None for x in pred):
        raise ValueError("forecast response includes non-numeric mean values")

    sq_err = [(float(p) - float(a)) ** 2 for p, a in zip(pred, actual[:horizon], strict=False)]
    return float(math.sqrt(sum(sq_err) / max(1, horizon)))


def _load_teacher_reference_tollama_forecast(
    *,
    base_url: str,
    model: str,
    timeout_sec: float,
    backtest_length: int,
    backtest_horizon: int,
) -> dict[str, Any]:
    n = max(16, int(backtest_length))
    h = max(1, int(backtest_horizon))
    if h >= n:
        raise ValueError("teacher backtest horizon must be smaller than backtest length")

    timestamps, values = _build_teacher_backtest_series(length=n)
    history_t = timestamps[: n - h]
    history_y = values[: n - h]
    actual_y = values[n - h :]

    payload = {
        "model": model,
        "horizon": h,
        # chronos2 currently requires explicit quantiles in /api/forecast requests.
        "quantiles": [0.1, 0.5, 0.9],
        "options": {},
        "series": [
            {
                "id": "teacher_backtest",
                "timestamps": history_t,
                "target": history_y,
            }
        ],
        "stream": False,
    }

    endpoint = f"{base_url}/api/forecast"
    response_payload = _http_post_json(endpoint, payload, timeout_sec=timeout_sec)
    rmse = _parse_tollama_forecast_rmse(response_payload=response_payload, actual=actual_y, horizon=h)
    return {
        "name": model,
        "rmse": rmse,
        "provider": "tollama_forecast_backtest",
        "model": model,
        "notes": f"synthetic_backtest_length={n}, horizon={h}",
        "raw_response": response_payload,
    }


def _resolve_teacher_models(args: argparse.Namespace) -> list[str]:
    if args.teacher_model:
        return [x.strip() for x in args.teacher_model if x and x.strip()]
    return ["chronos-2", "timesfm-2.5"]


def _load_teacher_references_tollama(
    *,
    args: argparse.Namespace,
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    models = _resolve_teacher_models(args)
    if not models:
        return []

    base_url = args.tollama_base_url.rstrip("/")
    context_rows = _compact_teacher_context(records, top_k=args.teacher_context_topk)

    refs: list[dict[str, Any]] = []
    for model in models:
        chat_error: str | None = None
        try:
            prompt = _resolve_teacher_prompt(
                template=args.teacher_prompt_template,
                model=model,
                context_rows=context_rows,
            )
            response_payload = _http_post_json(
                f"{base_url}/api/chat",
                {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                },
                timeout_sec=args.teacher_timeout_sec,
            )
            parsed = _parse_tollama_teacher_reference(model=model, response_payload=response_payload)
            if parsed.get("rmse") is not None:
                refs.append(parsed)
                continue
            chat_error = str(parsed.get("error") or "teacher chat response missing rmse")
        except (url_error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            chat_error = str(exc)

        if not args.teacher_enable_forecast_fallback:
            refs.append(
                {
                    "name": model,
                    "rmse": None,
                    "provider": "tollama",
                    "model": model,
                    "error": chat_error or "teacher chat failed",
                }
            )
            continue

        try:
            refs.append(
                _load_teacher_reference_tollama_forecast(
                    base_url=base_url,
                    model=model,
                    timeout_sec=args.teacher_timeout_sec,
                    backtest_length=args.teacher_backtest_length,
                    backtest_horizon=args.teacher_backtest_horizon,
                )
            )
        except (url_error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            refs.append(
                {
                    "name": model,
                    "rmse": None,
                    "provider": "tollama",
                    "model": model,
                    "error": f"chat_error={chat_error}; forecast_fallback_error={exc}",
                }
            )
    return refs


def _parse_profile_weights(raw: str, profiles: list[str]) -> dict[str, float]:
    if not profiles:
        raise ValueError("profiles must not be empty for weight parsing")
    if not raw.strip():
        uniform = 1.0 / float(len(profiles))
        return {name: uniform for name in profiles}

    weights: dict[str, float] = {}
    for token in _parse_csv(raw):
        if "=" not in token:
            raise ValueError(f"invalid score profile weight token '{token}', expected '<profile>=<weight>'")
        profile, weight_raw = token.split("=", 1)
        profile_name = profile.strip()
        if not profile_name:
            raise ValueError(f"invalid score profile weight token '{token}', profile must not be empty")
        if profile_name not in profiles:
            raise ValueError(f"score profile weight references unknown profile '{profile_name}'")
        weight = float(weight_raw)
        if weight <= 0:
            raise ValueError(f"score profile weight must be > 0 for '{profile_name}'")
        weights[profile_name] = weight

    missing = [name for name in profiles if name not in weights]
    if missing:
        raise ValueError(f"missing score profile weights for profiles: {missing}")

    total = sum(weights.values())
    if total <= 0:
        raise ValueError("invalid score profile weight sum <= 0")
    return {name: float(value / total) for name, value in weights.items()}


def _weighted_aggregate(
    *,
    values: dict[str, float | None],
    weights: dict[str, float],
    profiles: list[str],
) -> float | None:
    if any(values.get(name) is None for name in profiles):
        return None
    return float(sum(float(weights[name]) * float(values[name]) for name in profiles))


def _aggregate_benchmark_status(status_by_profile: dict[str, Any], profiles: list[str]) -> str | None:
    statuses = [str(status_by_profile.get(name)) for name in profiles if status_by_profile.get(name) is not None]
    if not statuses:
        return None
    if all(s == "succeeded" for s in statuses) and len(statuses) == len(profiles):
        return "succeeded"
    if any(s == "failed" for s in statuses):
        return "failed"
    return "partial"


def _run_command(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True)
    return int(proc.returncode), proc.stdout, proc.stderr


def _default_hidden_units(candidate: str) -> list[int]:
    if candidate == "dlinear":
        return [32]
    if candidate in {"gru", "lstm", "attention_lstm", "tcn"}:
        return [32, 16]
    return [32, 16]


def _collect_run_record(
    *,
    artifacts_dir: Path,
    run_id: str,
    selection_profile: str,
    score_profiles: list[str],
    score_profile_weights: dict[str, float],
) -> dict[str, Any]:
    metrics_payload = _load_json(artifacts_dir / "metrics" / f"{run_id}.json") or {}
    metrics = metrics_payload.get("metrics", {}) if isinstance(metrics_payload.get("metrics"), dict) else {}
    baselines = metrics_payload.get("baselines", {}) if isinstance(metrics_payload.get("baselines"), dict) else {}
    baseline_naive = baselines.get("naive_last", {}) if isinstance(baselines.get("naive_last"), dict) else {}

    model_rmse = _safe_float(metrics.get("rmse"))
    baseline_rmse = _safe_float(baseline_naive.get("rmse"))
    degradation_pct = compute_accuracy_degradation_pct(model_rmse, baseline_rmse)

    bench_payloads = {
        profile: _load_json(artifacts_dir / "edge_bench" / run_id / f"{profile}.json") or {}
        for profile in score_profiles
    }
    edge_score_by_profile = {profile: _safe_float(payload.get("edge_score")) for profile, payload in bench_payloads.items()}
    latency_by_profile = {profile: _safe_float(payload.get("latency_p95_ms")) for profile, payload in bench_payloads.items()}
    size_by_profile = {profile: _safe_float(payload.get("size_mb")) for profile, payload in bench_payloads.items()}
    status_by_profile = {profile: payload.get("status") for profile, payload in bench_payloads.items()}
    runtime_stack_by_profile = {profile: payload.get("runtime_stack") for profile, payload in bench_payloads.items()}
    missing_score_profiles = [profile for profile in score_profiles if not bench_payloads.get(profile)]

    weighted_edge_score = _weighted_aggregate(
        values=edge_score_by_profile,
        weights=score_profile_weights,
        profiles=score_profiles,
    )
    weighted_latency = _weighted_aggregate(
        values=latency_by_profile,
        weights=score_profile_weights,
        profiles=score_profiles,
    )
    weighted_size = _weighted_aggregate(
        values=size_by_profile,
        weights=score_profile_weights,
        profiles=score_profiles,
    )

    primary_profile = selection_profile if selection_profile in bench_payloads else score_profiles[0]
    bench_payload = bench_payloads.get(primary_profile, {})
    release_gate = _load_json(artifacts_dir / "edge_bench" / run_id / "release_gate.json") or {}

    return {
        "run_id": run_id,
        "model_type": metrics_payload.get("config", {}).get("model_type")
        if isinstance(metrics_payload.get("config"), dict)
        else None,
        "rmse": model_rmse,
        "baseline_rmse": baseline_rmse,
        "accuracy_degradation_pct": degradation_pct,
        "edge_score": weighted_edge_score,
        "latency_p95_ms": weighted_latency,
        "size_mb": weighted_size,
        "runtime_stack": bench_payload.get("runtime_stack"),
        "benchmark_status": _aggregate_benchmark_status(status_by_profile, score_profiles),
        "selection_primary_profile": primary_profile,
        "score_profiles": score_profiles,
        "score_profile_weights": score_profile_weights,
        "edge_score_by_profile": edge_score_by_profile,
        "latency_p95_ms_by_profile": latency_by_profile,
        "size_mb_by_profile": size_by_profile,
        "runtime_stack_by_profile": runtime_stack_by_profile,
        "missing_score_profiles": missing_score_profiles,
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


def _resolve_benchmark_profiles(args: argparse.Namespace) -> list[str]:
    profiles = _parse_csv(args.benchmark_profiles) if args.benchmark_profiles else [args.selection_profile]
    return profiles if profiles else [args.selection_profile]


def _resolve_gate_required_profiles(args: argparse.Namespace, benchmark_profiles: list[str]) -> list[str]:
    required = _parse_csv(args.gate_required_profiles) if args.gate_required_profiles else benchmark_profiles
    return required if required else [args.selection_profile]


def _resolve_score_profiles(args: argparse.Namespace, gate_required_profiles: list[str]) -> list[str]:
    profiles = _parse_csv(args.score_profiles) if args.score_profiles else gate_required_profiles
    return profiles if profiles else [args.selection_profile]


def _resolve_gate_device_results_dir(
    *,
    gate_device_results_dir_template: str,
    run_id: str,
) -> str | None:
    template = gate_device_results_dir_template.strip()
    if not template:
        return None
    return template.format(run_id=run_id)


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


def _build_benchmark_cmd(args: argparse.Namespace, run: CandidateRun, benchmark_profiles: list[str]) -> list[str]:
    cmd = [
        sys.executable,
        "scripts/benchmark_edge.py",
        "--run-id",
        run.run_id,
        "--artifacts-dir",
        args.artifacts_dir,
        "--edge-sla",
        args.edge_sla,
        "--iterations",
        str(args.benchmark_iterations),
        "--warmup",
        str(args.benchmark_warmup),
    ]
    for profile in benchmark_profiles:
        cmd.extend(["--device", profile])
    return cmd


def _build_release_gate_cmd(
    args: argparse.Namespace,
    run: CandidateRun,
    gate_required_profiles: list[str],
) -> list[str]:
    cmd = [
        sys.executable,
        "scripts/edge_release_gate.py",
        "--run-id",
        run.run_id,
        "--artifacts-dir",
        args.artifacts_dir,
        "--required-profiles",
        ",".join(gate_required_profiles),
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
    device_results_dir = _resolve_gate_device_results_dir(
        gate_device_results_dir_template=args.gate_device_results_dir_template,
        run_id=run.run_id,
    )
    if device_results_dir:
        cmd.extend(["--device-results-dir", device_results_dir])
    return cmd


def run(args: argparse.Namespace) -> dict[str, Any]:
    experiment_id = args.experiment_id or _build_experiment_id()
    workspace = Path(args.workspace_dir).resolve()
    artifacts_dir = Path(args.artifacts_dir).resolve()
    candidates = _parse_csv(args.candidates)
    seeds = _parse_int_csv(args.seeds)
    benchmark_profiles = _resolve_benchmark_profiles(args)
    gate_required_profiles = _resolve_gate_required_profiles(args, benchmark_profiles)
    score_profiles = _resolve_score_profiles(args, gate_required_profiles)
    score_profile_weights = _parse_profile_weights(args.score_profile_weights, score_profiles)

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

            bench_cmd = _build_benchmark_cmd(args, run_item, benchmark_profiles)
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

            gate_cmd = _build_release_gate_cmd(args, run_item, gate_required_profiles)
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
        base = _collect_run_record(
            artifacts_dir=artifacts_dir,
            run_id=run_item.run_id,
            selection_profile=args.selection_profile,
            score_profiles=score_profiles,
            score_profile_weights=score_profile_weights,
        )
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
    teacher_refs: list[dict[str, Any]] = []
    if args.teacher_provider in {"json", "json+tollama"}:
        teacher_refs.extend(_load_teacher_references(args.teacher_reference_json))
    if args.teacher_provider in {"tollama", "json+tollama"}:
        teacher_refs.extend(_load_teacher_references_tollama(args=args, records=records))

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
            "benchmark_profiles": benchmark_profiles,
            "gate_required_profiles": gate_required_profiles,
            "score_profiles": score_profiles,
            "score_profile_weights": score_profile_weights,
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
        f"- score_profiles: `{','.join(score_profiles)}`\n"
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
    p.add_argument(
        "--benchmark-profiles",
        type=str,
        default="",
        help="Comma-separated device profiles for benchmark stage (default: selection_profile)",
    )
    p.add_argument(
        "--gate-required-profiles",
        type=str,
        default="",
        help="Comma-separated profiles required by release gate (default: benchmark_profiles)",
    )
    p.add_argument(
        "--score-profiles",
        type=str,
        default="",
        help="Comma-separated profiles used for champion/fallback scoring (default: gate_required_profiles)",
    )
    p.add_argument(
        "--score-profile-weights",
        type=str,
        default="",
        help="Optional '<profile>=<weight>' CSV for score-profiles (default: uniform)",
    )
    p.add_argument("--benchmark-iterations", type=int, default=20)
    p.add_argument("--benchmark-warmup", type=int, default=5)
    p.add_argument("--max-accuracy-degradation-pct", type=float, default=2.0)
    p.add_argument("--size-limit-mb", type=float, default=8.0)
    p.add_argument("--size-hard-limit-mb", type=float, default=15.0)
    p.add_argument("--allow-extended-size", action="store_true", default=False)
    p.add_argument("--memory-budget-mb", type=float, default=None)
    p.add_argument(
        "--gate-device-results-dir-template",
        type=str,
        default="",
        help="Optional template for release gate inline device ingest, e.g. artifacts/device_results/{run_id}",
    )
    p.add_argument("--skip-memory-check", action="store_true", default=False)
    p.add_argument("--min-stability-attempts", type=int, default=20)
    p.add_argument("--max-failures", type=int, default=0)
    p.add_argument("--horizon-buckets", type=str, default="1-24,25-72,73-168")
    p.add_argument("--bucket-weights", type=str, default="0.50,0.30,0.20")
    p.add_argument(
        "--teacher-provider",
        type=str,
        choices=["json", "tollama", "json+tollama"],
        default="json",
        help="Teacher reference source",
    )
    p.add_argument("--teacher-reference-json", action="append", default=[])
    p.add_argument(
        "--teacher-model",
        action="append",
        default=[],
        help="Teacher model id for tollama provider (repeatable). Default: chronos-2, timesfm-2.5",
    )
    p.add_argument("--tollama-base-url", type=str, default="http://127.0.0.1:11434")
    p.add_argument("--teacher-timeout-sec", type=float, default=20.0)
    p.add_argument("--teacher-context-topk", type=int, default=5)
    p.add_argument("--teacher-enable-forecast-fallback", action="store_true", default=True)
    p.add_argument("--no-teacher-enable-forecast-fallback", action="store_false", dest="teacher_enable_forecast_fallback")
    p.add_argument("--teacher-backtest-length", type=int, default=120)
    p.add_argument("--teacher-backtest-horizon", type=int, default=24)
    p.add_argument(
        "--teacher-prompt-template",
        type=str,
        default="",
        help="Optional format template for tollama prompt. Available placeholders: {model}, {candidate_summary_json}",
    )
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
