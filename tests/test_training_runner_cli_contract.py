"""CLI contract tests for src.training.runner argument compatibility."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.training.runner import build_parser


def test_runner_parser_accepts_legacy_smoke_flags():
    parser = build_parser()
    args = parser.parse_args(
        [
            "--run-id",
            "phase2-runner-smoke",
            "--epochs",
            "1",
            "--synthetic",
            "--artifacts-dir",
            "artifacts",
            "--checkpoints-dir",
            "checkpoints",
        ]
    )

    assert args.synthetic is True
    assert args.checkpoints_dir == "checkpoints"
    assert args.preprocessor_pkl is None


def test_runner_parser_defaults_still_valid_without_legacy_flags():
    parser = build_parser()
    args = parser.parse_args([])

    assert args.synthetic is False
    assert args.checkpoints_dir is None
    assert args.artifacts_dir == "artifacts"
    assert args.model_type == "lstm"
    assert args.feature_mode == "univariate"
    assert args.target_cols == "target"
    assert args.run_id_validation == "legacy"


def test_runner_parser_accepts_strict_run_id_validation_mode():
    parser = build_parser()
    args = parser.parse_args(["--run-id-validation", "strict", "--run-id", "20260220_010203_abcdef0"])
    assert args.run_id_validation == "strict"


def test_runner_parser_accepts_phase5_extension_flags():
    parser = build_parser()
    args = parser.parse_args(
        [
            "--model-type",
            "gru",
            "--feature-mode",
            "multivariate",
            "--target-cols",
            "target_a,target_b",
            "--dynamic-covariates",
            "temp,promo",
            "--static-covariates",
            "store_id",
            "--covariate-spec",
            "configs/covariates/default.schema.json",
            "--export-formats",
            "onnx,tflite",
        ]
    )

    assert args.model_type == "gru"
    assert args.feature_mode == "multivariate"
    assert args.target_cols == "target_a,target_b"
    assert args.dynamic_covariates == "temp,promo"
    assert args.static_covariates == "store_id"
    assert args.covariate_spec.endswith("default.schema.json")
    assert args.export_formats == "onnx,tflite"
