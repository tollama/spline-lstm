from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.data.synthetic_generator import GeneratorConfig, generate_dataframe, main, parse_args, save_outputs


def test_generate_dataframe_s1_with_covariates() -> None:
    cfg = GeneratorConfig(
        scenario="S1",
        n_samples=72,
        seed=11,
        noise_scale=0.1,
        covariates=("temp", "promo", "dow", "hour", "custom_signal"),
    )
    df = generate_dataframe(cfg)

    assert len(df) == 72
    assert list(df.columns) == ["timestamp", "target", "temp", "promo", "dow", "hour", "custom_signal"]
    assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])
    assert pd.api.types.is_float_dtype(df["target"])
    assert set(np.unique(df["promo"])) <= {0.0, 1.0}
    assert df["dow"].between(0, 6).all()
    assert df["hour"].between(0, 23).all()


@pytest.mark.parametrize("scenario", ["S2", "S3"])
def test_generate_dataframe_other_scenarios(scenario: str) -> None:
    cfg = GeneratorConfig(scenario=scenario, n_samples=96, seed=7, noise_scale=0.2)
    df = generate_dataframe(cfg)

    assert len(df) == 96
    assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])
    assert pd.api.types.is_float_dtype(df["target"])
    assert np.isfinite(df["target"]).all()


def test_generate_dataframe_rejects_unknown_scenario() -> None:
    cfg = GeneratorConfig(scenario="S9")
    with pytest.raises(ValueError, match="Unsupported scenario"):
        generate_dataframe(cfg)


def test_save_outputs_writes_csv_and_meta(tmp_path: Path) -> None:
    cfg = GeneratorConfig(
        scenario="S2",
        n_samples=48,
        seed=123,
        covariates=("temp", "promo"),
        out_dir=str(tmp_path),
        file_stem="unit_case",
    )
    df = generate_dataframe(cfg)
    csv_path, meta_path = save_outputs(df, cfg)

    assert csv_path == tmp_path / "unit_case.csv"
    assert meta_path == tmp_path / "unit_case.meta.json"
    assert csv_path.exists()
    assert meta_path.exists()

    loaded = pd.read_csv(csv_path)
    assert len(loaded) == len(df)
    assert list(loaded.columns) == list(df.columns)

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["generator"] == "src.data.synthetic_generator"
    assert meta["config"]["scenario"] == "S2"
    assert meta["stats"]["rows"] == len(df)
    assert meta["outputs"]["csv"] == str(csv_path)


def test_parse_args_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["synthetic_generator"])
    args = parse_args()
    assert args.scenario == "S1"
    assert args.n_samples == 720
    assert args.freq == "h"


def test_main_generates_cli_outputs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys) -> None:
    out_dir = tmp_path / "out"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "synthetic_generator",
            "--scenario",
            "S3",
            "--n-samples",
            "36",
            "--seed",
            "999",
            "--covariates",
            "temp,promo,event",
            "--out-dir",
            str(out_dir),
            "--file-stem",
            "cli_case",
        ],
    )
    main()

    stdout = capsys.readouterr().out
    assert "[OK] synthetic data generated" in stdout
    assert "- scenario: S3" in stdout
    assert (out_dir / "cli_case.csv").exists()
    assert (out_dir / "cli_case.meta.json").exists()
