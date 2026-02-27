from __future__ import annotations

import copy
import hashlib
import json
import time
import uuid
from typing import Any

from backend.app.config import API_PREFIX, ARTIFACTS_DIR, PHASE6_FLAGS, ROOT_DIR
from backend.app.models import (
    CovariateContractValidateRequest,
    CovariateFieldSpec,
    ForecastExecuteAdjustedRequest,
    ForecastInputRequest,
    InputPatchOperation,
)
from backend.app.runtime import resolve_runtime_for_run
from backend.app.store import JobRecord
from backend.app.utils import atomic_write_text, corr, ensure_parent, utc_now_iso
from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter()

_ADJUSTABLE_TOP_LEVEL_FIELDS = {
    "horizon",
    "target_history",
    "known_future_covariates",
    "static_covariates",
}


def _payload_hash(payload: dict[str, Any]) -> str:
    normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _set_nested_value(target: dict[str, Any], path: str, value: Any) -> None:
    if not path.startswith("/"):
        raise ValueError("path must start with '/'")
    parts = [p for p in path.strip("/").split("/") if p]
    if not parts:
        raise ValueError("path must not be empty")
    if parts[0] not in _ADJUSTABLE_TOP_LEVEL_FIELDS:
        raise ValueError(f"path root '{parts[0]}' is not adjustable")

    cur: Any = target
    for idx, key in enumerate(parts[:-1]):
        next_key = parts[idx + 1]
        if isinstance(cur, list):
            i = int(key)
            if i < 0 or i >= len(cur):
                raise ValueError("list index out of range")
            cur = cur[i]
        elif isinstance(cur, dict):
            if key not in cur:
                cur[key] = [] if next_key.isdigit() else {}
            cur = cur[key]
        else:
            raise ValueError("invalid patch path")

    leaf = parts[-1]
    if isinstance(cur, list):
        i = int(leaf)
        if i < 0 or i >= len(cur):
            raise ValueError("list index out of range")
        cur[i] = value
    elif isinstance(cur, dict):
        cur[leaf] = value
    else:
        raise ValueError("invalid patch target")


def _validate_forecast_inputs(inputs: dict[str, Any]) -> None:
    horizon = inputs.get("horizon", 1)
    if not isinstance(horizon, int) or horizon < 1 or horizon > 168:
        raise ValueError("horizon must be an int between 1 and 168")

    history = inputs.get("target_history", [])
    if not isinstance(history, list) or len(history) < 2:
        raise ValueError("target_history must contain at least 2 points")
    if any(not isinstance(x, (int, float)) for x in history):
        raise ValueError("target_history must be numeric list")

    for key in ("known_future_covariates", "static_covariates"):
        raw = inputs.get(key, {})
        if raw is None:
            continue
        if not isinstance(raw, dict):
            raise ValueError(f"{key} must be an object")


def _naive_preview(inputs: dict[str, Any]) -> list[float]:
    history = inputs.get("target_history", [])
    horizon = inputs.get("horizon", 1)
    last = float(history[-1]) if history else 0.0

    cov = inputs.get("known_future_covariates", {})
    cov_effect = 0.0
    if isinstance(cov, dict):
        vals: list[float] = []
        for v in cov.values():
            if isinstance(v, (int, float)):
                vals.append(float(v))
            elif isinstance(v, list):
                vals.extend(float(x) for x in v if isinstance(x, (int, float)))
        if vals:
            cov_effect = sum(vals) / len(vals) * 0.01

    return [round(last + cov_effect, 6) for _ in range(horizon)]


def _append_adjustment_audit(event: dict[str, Any]) -> None:
    audit_path = ARTIFACTS_DIR / "audit" / "input_adjustments.jsonl"
    ensure_parent(audit_path)
    with open(audit_path, "a", encoding="utf-8") as fp:
        fp.write(json.dumps(event, ensure_ascii=False) + "\n")


def _apply_input_patches(base_inputs: dict[str, Any], patches: list[InputPatchOperation]) -> dict[str, Any]:
    candidate = copy.deepcopy(base_inputs)
    for patch in patches:
        if patch.path.startswith("/target_history") and not patch.reason:
            raise ValueError("target_history patch requires reason")
        _set_nested_value(candidate, patch.path, patch.value)
    _validate_forecast_inputs(candidate)
    return candidate


def _validate_covariate_contract(
    schema: list[CovariateFieldSpec], payload: dict[str, Any], strict_order: bool = True
) -> dict[str, Any]:
    if "covariates" not in payload or not isinstance(payload.get("covariates"), dict):
        raise ValueError("payload.covariates must be an object")
    covariates: dict[str, Any] = payload["covariates"]

    expected = [item.name for item in schema]
    required = {item.name for item in schema if item.required}

    missing = sorted([name for name in required if name not in covariates])
    extras = sorted([name for name in covariates if name not in expected])

    order_ok = True
    if strict_order:
        order_ok = list(covariates.keys()) == expected

    type_violations: list[str] = []
    type_map = {item.name: item.type for item in schema}
    for name, value in covariates.items():
        dtype = type_map.get(name)
        if dtype is None:
            continue
        if dtype == "numeric" and not isinstance(value, (int, float)):
            type_violations.append(name)
        if dtype == "boolean" and not isinstance(value, bool):
            type_violations.append(name)
        if dtype == "categorical" and not isinstance(value, str):
            type_violations.append(name)

    return {
        "valid": not missing and not extras and order_ok and not type_violations,
        "missing": missing,
        "extras": extras,
        "order_ok": order_ok,
        "type_violations": sorted(type_violations),
        "schema_hash": _payload_hash({"schema": [item.model_dump() for item in schema]}),
    }


def _store_adjusted_inputs(run_id: str, payload: dict[str, Any]) -> str:
    target = ARTIFACTS_DIR / "inputs" / f"{run_id}.adjusted.json"
    atomic_write_text(target, json.dumps(payload, ensure_ascii=False, indent=2))
    try:
        return str(target.relative_to(ROOT_DIR))
    except ValueError:
        return str(target)


@router.post(f"{API_PREFIX}/forecast/validate-inputs")
def validate_forecast_inputs(payload: ForecastInputRequest, request: Request) -> dict[str, Any]:
    candidate = json.loads(json.dumps(payload.base_inputs, ensure_ascii=False))
    original_hash = _payload_hash(candidate)
    try:
        candidate = _apply_input_patches(candidate, payload.patches)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "ok": True,
        "data": {
            "run_id": payload.run_id,
            "valid": True,
            "input_hash_before": original_hash,
            "input_hash_after": _payload_hash(candidate),
            "correlation": corr(request, run_id=payload.run_id),
        },
    }


@router.post(f"{API_PREFIX}/forecast/preview")
def preview_forecast(payload: ForecastInputRequest, request: Request) -> dict[str, Any]:
    candidate = json.loads(json.dumps(payload.base_inputs, ensure_ascii=False))
    before_hash = _payload_hash(candidate)
    try:
        candidate = _apply_input_patches(candidate, payload.patches)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    preview = _naive_preview(candidate)
    after_hash = _payload_hash(candidate)
    _append_adjustment_audit(
        {
            "ts": utc_now_iso(),
            "run_id": payload.run_id,
            "actor": payload.actor,
            "patches": [p.model_dump() for p in payload.patches],
            "input_hash_before": before_hash,
            "input_hash_after": after_hash,
        }
    )
    return {
        "ok": True,
        "data": {
            "run_id": payload.run_id,
            "preview": preview,
            "input_hash_before": before_hash,
            "input_hash_after": after_hash,
            "correlation": corr(request, run_id=payload.run_id),
        },
    }


@router.post(f"{API_PREFIX}/forecast/execute-adjusted")
def execute_adjusted_forecast(payload: ForecastExecuteAdjustedRequest, request: Request) -> dict[str, Any]:
    from backend.app.main import executor, store

    if not PHASE6_FLAGS["enable_adjusted_execute"]:
        raise HTTPException(status_code=503, detail="adjusted execution disabled")

    base = json.loads(json.dumps(payload.base_inputs, ensure_ascii=False))
    before_hash = _payload_hash(base)
    try:
        adjusted = _apply_input_patches(base, payload.patches)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    after_hash = _payload_hash(adjusted)
    run_id = payload.run_id
    stored_ref = _store_adjusted_inputs(run_id, adjusted)

    rec = JobRecord(
        job_id=f"job-{uuid.uuid4().hex[:12]}",
        run_id=run_id,
        model_type=payload.model_type or "lstm",
        feature_mode=payload.feature_mode or "multivariate",
        created_at=time.time(),
    )
    store.upsert(rec)
    executor.submit(rec)

    _append_adjustment_audit(
        {
            "ts": utc_now_iso(),
            "run_id": run_id,
            "job_id": rec.job_id,
            "actor": payload.actor,
            "patches": [p.model_dump() for p in payload.patches],
            "input_hash_before": before_hash,
            "input_hash_after": after_hash,
            "input_ref": stored_ref,
            "action": "execute_adjusted",
        }
    )

    return {
        "ok": True,
        "data": {
            "run_id": run_id,
            "job_id": rec.job_id,
            "status": "queued",
            "input_hash_before": before_hash,
            "input_hash_after": after_hash,
            "adjusted_input_ref": stored_ref,
            "correlation": corr(request, run_id=run_id, job_id=rec.job_id),
        },
    }


@router.post(f"{API_PREFIX}/covariates/validate")
def validate_covariate_contract(payload: CovariateContractValidateRequest, request: Request) -> dict[str, Any]:
    try:
        result = _validate_covariate_contract(
            payload.covariate_schema, payload.payload, strict_order=payload.strict_order
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "data": {**result, "correlation": corr(request)}}


@router.get(f"{API_PREFIX}/forecast/runtime/{{run_id}}")
def forecast_runtime_selection(
    run_id: str,
    request: Request,
    preferred: str | None = Query(default=None, description="Optional runtime preference order, e.g. tflite,onnx"),
) -> dict[str, Any]:
    preferred_order = [x.strip() for x in preferred.split(",") if x.strip()] if preferred else None
    resolved = resolve_runtime_for_run(run_id=run_id, preferred_order=preferred_order)
    return {
        "ok": True,
        "data": {
            "run_id": run_id,
            "runtime_stack": resolved["runtime_stack"],
            "fallback_chain": resolved["fallback_chain"],
            "manifest_path": resolved["manifest_path"],
            "runtime_compatibility": resolved["runtime_compatibility"],
            "correlation": corr(request, run_id=run_id),
        },
    }
