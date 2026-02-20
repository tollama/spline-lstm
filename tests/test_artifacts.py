"""Artifact save/load and run_id rule tests for MVP Phase 1."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from training.trainer import Trainer


class DummyModel:
    """Backend-free model stub for artifact IO tests."""

    def __init__(self):
        self.loaded_from = None
        self.saved_to = []

    def save(self, path: str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("dummy-model")
        self.saved_to.append(str(p))

    def load(self, path: str) -> None:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(path)
        self.loaded_from = str(p)


class TestArtifactRules:
    def test_save_run_artifacts_and_validate_run_id_match(self, tmp_path: Path):
        model = DummyModel()
        trainer = Trainer(model=model, save_dir=str(tmp_path / "ckpt"))
        trainer.metrics = {"rmse": 0.123, "mae": 0.100}

        run_id = "run_20260218_1723"
        out = trainer.save_run_artifacts(
            run_id=run_id,
            base_dir=str(tmp_path / "artifacts"),
            config={"sequence_length": 24, "horizon": 1},
            report="# synthetic smoke report\n",
            preprocessor_blob=b"pickle-bytes",
        )

        # path existence checks
        for key in ("model", "preprocessor", "metrics", "config", "report"):
            assert Path(out[key]).exists(), f"missing artifact file: {key}"

        # run_id layout checks
        assert f"/models/{run_id}/" in out["model"]
        assert f"/models/{run_id}/" in out["preprocessor"]
        assert out["metrics"].endswith(f"/{run_id}.json")

        # content sanity checks
        metrics = json.loads(Path(out["metrics"]).read_text())
        assert metrics["rmse"] == pytest.approx(0.123)

        assert trainer.validate_artifact_run_id_match(out["model"], out["preprocessor"]) is True

    def test_validate_artifact_run_id_mismatch_raises(self):
        with pytest.raises(ValueError, match="run_id mismatch"):
            Trainer.validate_artifact_run_id_match(
                "artifacts/models/run_a/model.keras",
                "artifacts/models/run_b/preprocessor.pkl",
            )

    @pytest.mark.parametrize("bad_run_id", ["", "   ", "a/b", "a\\b"])
    def test_save_run_artifacts_rejects_invalid_run_id(self, tmp_path: Path, bad_run_id: str):
        trainer = Trainer(model=DummyModel(), save_dir=str(tmp_path / "ckpt"))
        with pytest.raises(ValueError):
            trainer.save_run_artifacts(run_id=bad_run_id, base_dir=str(tmp_path / "artifacts"))

    def test_save_checkpoint_appends_keras_extension_and_keeps_metrics_stem(self, tmp_path: Path):
        model = DummyModel()
        trainer = Trainer(model=model, save_dir=str(tmp_path / "ckpt"))
        trainer.metrics = {"rmse": 0.5}

        ckpt_path = Path(trainer.save_checkpoint("best"))
        assert ckpt_path.name == "best.keras"
        assert (tmp_path / "ckpt" / "best_metrics.json").exists()

    def test_load_checkpoint_calls_model_load(self, tmp_path: Path):
        model = DummyModel()
        trainer = Trainer(model=model, save_dir=str(tmp_path / "ckpt"))

        model_path = tmp_path / "ckpt" / "dummy.keras"
        model.save(str(model_path))

        trainer.load_checkpoint(str(model_path))
        assert model.loaded_from == str(model_path)
