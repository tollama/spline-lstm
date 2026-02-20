"""Covariate spec loading and validation utilities.

Contract goals:
- Fail fast on malformed schema payloads.
- Enforce required covariates across preprocessing/runner boundaries.
- Keep backward compatibility when no spec is provided.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence


_ALLOWED_TYPES = {"numeric", "categorical", "boolean"}
_ALLOWED_SCHEMA_VERSION = "covariate_spec.v1"
_ALLOWED_IMPUTATION_POLICIES = {
    "dynamic_covariates": {"ffill_bfill_then_zero", "zero", "mean"},
    "static_covariates": {"unknown_token", "mode", "none"},
}


def _to_unique_str_list(values: Sequence[str], label: str) -> list[str]:
    out: list[str] = []
    for raw in values:
        if not isinstance(raw, str):
            raise ValueError(f"{label} names must be strings")
        name = raw.strip()
        if not name:
            continue
        if name not in out:
            out.append(name)
    return out


def load_covariate_spec(path: Optional[str]) -> Dict[str, Any]:
    if not path:
        return {}
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError("covariate spec must be a JSON object")
    return payload


def _normalize_covariate_entry(group_key: str, index: int, item: Dict[str, Any], seen: set[str]) -> Dict[str, Any]:
    name = item.get("name")
    ctype = item.get("type", "numeric")
    required = item.get("required", False)

    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"covariate spec field '{group_key}[{index}].name' must be non-empty string")
    name = name.strip()
    if name in seen:
        raise ValueError(f"duplicate covariate '{name}' in '{group_key}'")
    seen.add(name)

    if not isinstance(ctype, str) or ctype not in _ALLOWED_TYPES:
        raise ValueError(
            f"covariate spec field '{group_key}[{index}].type' must be one of {sorted(_ALLOWED_TYPES)}"
        )
    if not isinstance(required, bool):
        raise ValueError(f"covariate spec field '{group_key}[{index}].required' must be boolean")

    return {
        "name": name,
        "type": ctype,
        "required": required,
    }


def validate_covariate_spec_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not payload:
        return {}

    schema_version = payload.get("schema_version", _ALLOWED_SCHEMA_VERSION)
    if not isinstance(schema_version, str) or not schema_version.strip():
        raise ValueError("covariate spec field 'schema_version' must be non-empty string")
    if schema_version != _ALLOWED_SCHEMA_VERSION:
        raise ValueError(
            f"covariate spec field 'schema_version' must be '{_ALLOWED_SCHEMA_VERSION}', got '{schema_version}'"
        )

    normalized: Dict[str, Any] = {
        "schema_version": schema_version,
        "dynamic_covariates": [],
        "static_covariates": [],
        "imputation_policy": {},
    }

    for group_key in ("dynamic_covariates", "static_covariates"):
        group = payload.get(group_key, [])
        if group is None:
            group = []
        if not isinstance(group, list):
            raise ValueError(f"covariate spec field '{group_key}' must be a list")

        seen: set[str] = set()
        for i, item in enumerate(group):
            if not isinstance(item, dict):
                raise ValueError(f"covariate spec field '{group_key}[{i}]' must be an object")
            normalized[group_key].append(_normalize_covariate_entry(group_key, i, item, seen))

    imputation_policy = payload.get("imputation_policy", {})
    if imputation_policy is None:
        imputation_policy = {}
    if not isinstance(imputation_policy, dict):
        raise ValueError("covariate spec field 'imputation_policy' must be an object")

    normalized_policy: Dict[str, str] = {}
    for key, allowed in _ALLOWED_IMPUTATION_POLICIES.items():
        value = imputation_policy.get(key)
        if value is None:
            continue
        if not isinstance(value, str):
            raise ValueError(f"covariate spec field 'imputation_policy.{key}' must be string")
        if value not in allowed:
            raise ValueError(
                f"covariate spec field 'imputation_policy.{key}' must be one of {sorted(allowed)}"
            )
        normalized_policy[key] = value
    normalized["imputation_policy"] = normalized_policy

    dyn = {x["name"] for x in normalized["dynamic_covariates"]}
    sta = {x["name"] for x in normalized["static_covariates"]}
    overlap = sorted(dyn & sta)
    if overlap:
        raise ValueError(f"covariate spec dynamic/static names overlap: {overlap}")

    return normalized


def enforce_covariate_spec(
    *,
    declared_dynamic: Sequence[str],
    declared_static: Sequence[str],
    available_columns: Optional[Sequence[str]],
    spec_payload: Dict[str, Any],
    context: str,
) -> Dict[str, Any]:
    """Validate declared covariates against schema + available columns.

    Returns normalized schema snapshot with resolved lists and missing diagnostics.
    """

    dynamic = _to_unique_str_list(declared_dynamic, "dynamic covariate")
    static = _to_unique_str_list(declared_static, "static covariate")

    overlap = sorted(set(dynamic) & set(static))
    if overlap:
        raise ValueError(f"{context}: dynamic/static covariate names overlap: {overlap}")

    spec = validate_covariate_spec_payload(spec_payload)
    if not spec:
        return {
            "enabled": False,
            "schema_version": None,
            "dynamic_covariates": dynamic,
            "static_covariates": static,
            "required_missing": [],
            "declared_missing_in_columns": [],
            "spec": {},
        }

    spec_dynamic = [x["name"] for x in spec["dynamic_covariates"]]
    spec_static = [x["name"] for x in spec["static_covariates"]]
    required = [
        x["name"]
        for x in [*spec["dynamic_covariates"], *spec["static_covariates"]]
        if x.get("required", False)
    ]

    declared_all = set(dynamic) | set(static)
    required_missing = sorted([name for name in required if name not in declared_all])
    if required_missing:
        raise ValueError(
            f"{context}: required covariates missing from arguments/config: {required_missing}; "
            f"declared_dynamic={dynamic}, declared_static={static}"
        )

    # If spec exists, ensure declared names are covered by spec.
    spec_all = set(spec_dynamic) | set(spec_static)
    undeclared_in_spec = sorted([name for name in declared_all if name not in spec_all])
    if undeclared_in_spec:
        raise ValueError(
            f"{context}: covariates not defined in spec: {undeclared_in_spec}; "
            f"spec_dynamic={spec_dynamic}, spec_static={spec_static}"
        )

    missing_in_columns: list[str] = []
    if available_columns is not None:
        cols = set(available_columns)
        for name in dynamic:
            if name not in cols:
                missing_in_columns.append(name)
        if missing_in_columns:
            raise ValueError(
                f"{context}: dynamic covariates missing in dataset columns: {sorted(missing_in_columns)}; "
                f"available_columns={sorted(cols)}"
            )

    return {
        "enabled": True,
        "schema_version": spec.get("schema_version"),
        "dynamic_covariates": dynamic,
        "static_covariates": static,
        "required_missing": required_missing,
        "declared_missing_in_columns": sorted(missing_in_columns),
        "spec": spec,
    }
