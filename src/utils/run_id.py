from __future__ import annotations

import re

STRICT_RUN_ID_RE = re.compile(r"^\d{8}_\d{6}_[0-9a-f]{7,12}$")


def validate_run_id(run_id: str, mode: str = "legacy") -> str:
    """Validate run_id.

    Modes:
    - legacy (default): non-empty, no path separators (backward compatible)
    - strict: YYYYMMDD_HHMMSS_<shortsha>
    """
    if mode not in {"legacy", "strict"}:
        raise ValueError("run_id validation mode must be one of: legacy, strict")

    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("run_id must be a non-empty string")

    run_id = run_id.strip()

    if re.search(r"[\\/]", run_id):
        raise ValueError("run_id must not contain path separators")

    if mode == "strict" and not STRICT_RUN_ID_RE.match(run_id):
        raise ValueError("run_id must match strict format YYYYMMDD_HHMMSS_<shortsha> (hex sha length 7-12)")

    return run_id
