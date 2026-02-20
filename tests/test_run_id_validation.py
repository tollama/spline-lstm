from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.utils.run_id import validate_run_id


def test_validate_run_id_legacy_accepts_human_readable():
    assert validate_run_id("phase4-smoke-001", mode="legacy") == "phase4-smoke-001"


def test_validate_run_id_strict_accepts_required_format():
    rid = "20260220_010203_ab12cd3"
    assert validate_run_id(rid, mode="strict") == rid


@pytest.mark.parametrize("bad", ["phase4-smoke-001", "2026-02-20_010203_ab12cd3", "20260220_010203_ZZ12cd3"])
def test_validate_run_id_strict_rejects_non_matching_values(bad: str):
    with pytest.raises(ValueError, match="strict format"):
        validate_run_id(bad, mode="strict")
