from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np
import pytest
from scripts.health_check import HealthCheckError, run_health_check


def _prepare_ok_artifacts(base: Path, run_id: str) -> None:
    (base / "processed" / run_id).mkdir(parents=True, exist_ok=True)
    (base / "models" / run_id).mkdir(parents=True, exist_ok=True)
    (base / "checkpoints" / run_id).mkdir(parents=True, exist_ok=True)
    (base / "metrics").mkdir(parents=True, exist_ok=True)
    (base / "reports").mkdir(parents=True, exist_ok=True)
    (base / "metadata").mkdir(parents=True, exist_ok=True)

    np.savez_compressed(base / "processed" / run_id / "processed.npz", scaled=np.arange(32, dtype=float))
    (base / "processed" / run_id / "meta.json").write_text(json.dumps({"run_id": run_id}), encoding="utf-8")

    with open(base / "models" / run_id / "preprocessor.pkl", "wb") as f:
        pickle.dump({"run_id": run_id, "scaler": {}}, f)

    (base / "checkpoints" / run_id / "best.keras").write_text("ok", encoding="utf-8")
    (base / "checkpoints" / run_id / "last.keras").write_text("ok", encoding="utf-8")

    metrics_payload = {
        "run_id": run_id,
        "metrics": {"rmse": 1.23},
        "checkpoints": {
            "best": str(base / "checkpoints" / run_id / "best.keras"),
            "last": str(base / "checkpoints" / run_id / "last.keras"),
        },
    }
    (base / "metrics" / f"{run_id}.json").write_text(json.dumps(metrics_payload), encoding="utf-8")
    (base / "reports" / f"{run_id}.md").write_text("# report", encoding="utf-8")
    (base / "metadata" / f"{run_id}.json").write_text(json.dumps({"run_id": run_id}), encoding="utf-8")


def test_health_check_pass(tmp_path: Path):
    run_id = "phase4-ok"
    _prepare_ok_artifacts(tmp_path, run_id)

    out = run_health_check(run_id=run_id, artifacts_dir=str(tmp_path))
    assert out["status"] == "PASS"
    assert out["code"] == 0


def test_health_check_detects_run_id_mismatch(tmp_path: Path):
    run_id = "phase4-a"
    _prepare_ok_artifacts(tmp_path, run_id)

    with open(tmp_path / "models" / run_id / "preprocessor.pkl", "wb") as f:
        pickle.dump({"run_id": "phase4-b"}, f)

    with pytest.raises(HealthCheckError) as e:
        run_health_check(run_id=run_id, artifacts_dir=str(tmp_path))
    assert e.value.code == 27


def test_health_check_detects_missing_artifact(tmp_path: Path):
    run_id = "phase4-missing"
    _prepare_ok_artifacts(tmp_path, run_id)
    (tmp_path / "reports" / f"{run_id}.md").unlink()

    with pytest.raises(HealthCheckError) as e:
        run_health_check(run_id=run_id, artifacts_dir=str(tmp_path))
    assert e.value.code == 30
