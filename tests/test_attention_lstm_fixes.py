"""Regression tests for bugs fixed in the post-0.1.0 patch cycle.

Covers:
- AttentionLSTMModel with static and future covariates (previously ignored)
- _ReduceSum Keras layer: model save → reload round-trip (Lambda bug regression)
- Trainer.denormalize_metrics=True: metrics in original-scale units (minmax & standard)
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.models.lstm import AttentionLSTMModel
from src.training.trainer import Trainer

RUN_ML = os.environ.get("RUN_ML_TESTS", "1")  # enabled by default in CI


# ---------------------------------------------------------------------------
# AttentionLSTMModel – covariate support
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not RUN_ML, reason="ML tests require TensorFlow")
def test_attention_lstm_build_with_static_and_future_covariates():
    """AttentionLSTMModel must wire static/future covariates into the graph.

    Before the fix, build() created only a past_input, silently ignoring
    static_features and future_features.
    """
    seq_len = 8
    horizon = 2
    n_past = 1
    n_static = 3
    n_future = 2
    batch = 16

    model = AttentionLSTMModel(
        sequence_length=seq_len,
        output_units=horizon,
        input_features=n_past,
        static_features=n_static,
        future_features=n_future,
        hidden_units=[32, 16],
        attention_units=16,
    )
    model.build()
    assert model.model is not None

    # Keras model must have three inputs: past, future, static
    assert len(model.model.inputs) == 3, (
        f"Expected 3 model inputs (past, future, static), got {len(model.model.inputs)}"
    )

    X_past = np.random.rand(batch, seq_len, n_past).astype(np.float32)
    X_fut = np.random.rand(batch, horizon, n_future).astype(np.float32)
    X_stat = np.random.rand(batch, n_static).astype(np.float32)
    y = np.random.rand(batch, horizon).astype(np.float32)

    # fit_model must accept and use all three inputs without error
    model.fit_model([X_past, X_fut, X_stat], y, epochs=1, verbose=0, early_stopping=False)

    preds = model.predict([X_past, X_fut, X_stat])
    assert preds.shape == (batch, horizon), f"Unexpected prediction shape: {preds.shape}"


@pytest.mark.skipif(not RUN_ML, reason="ML tests require TensorFlow")
def test_attention_lstm_no_covariates_baseline():
    """AttentionLSTMModel without covariates (past input only) must still work."""
    seq_len = 8
    horizon = 1
    batch = 10

    model = AttentionLSTMModel(
        sequence_length=seq_len,
        output_units=horizon,
        input_features=1,
        hidden_units=[16],
        attention_units=8,
    )
    model.build()
    assert len(model.model.inputs) == 1

    X = np.random.rand(batch, seq_len, 1).astype(np.float32)
    y = np.random.rand(batch, horizon).astype(np.float32)
    model.fit_model(X, y, epochs=1, verbose=0, early_stopping=False)

    preds = model.predict(X)
    assert preds.shape == (batch, horizon)


# ---------------------------------------------------------------------------
# _ReduceSum Keras layer: save / reload round-trip
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not RUN_ML, reason="ML tests require TensorFlow")
def test_attention_lstm_save_reload_round_trip(tmp_path):
    """Model saved with model.save() must reload correctly and produce the
    same predictions.

    Before the fix, the Lambda layer used for attention context summation
    prevented correct serialisation when the model used model.save().
    """
    seq_len = 6
    horizon = 1
    batch = 8

    model = AttentionLSTMModel(
        sequence_length=seq_len,
        output_units=horizon,
        input_features=1,
        hidden_units=[16],
        attention_units=8,
    )
    model.build()

    X = np.random.rand(batch, seq_len, 1).astype(np.float32)
    y = np.random.rand(batch, horizon).astype(np.float32)
    model.fit_model(X, y, epochs=2, verbose=0, early_stopping=False)

    preds_before = model.predict(X)

    # Save using Trainer.save() which normalises .keras → .h5
    ckpt_path = str(tmp_path / "attention_model.keras")
    model.save(ckpt_path)

    # Reload into a fresh instance
    model2 = AttentionLSTMModel(
        sequence_length=seq_len,
        output_units=horizon,
        input_features=1,
        hidden_units=[16],
        attention_units=8,
    )
    # Resolve the actual path saved (may have been renamed .h5 by save())
    h5_path = str(tmp_path / "attention_model.h5")
    actual_path = h5_path if os.path.exists(h5_path) else ckpt_path
    model2.load(actual_path)

    preds_after = model2.predict(X)

    np.testing.assert_allclose(
        preds_before,
        preds_after,
        rtol=1e-5,
        err_msg="Predictions differ after save/reload – _ReduceSum serialisation regression",
    )


# ---------------------------------------------------------------------------
# Trainer.denormalize_metrics
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not RUN_ML, reason="ML tests require TensorFlow")
@pytest.mark.parametrize("method", ["minmax", "standard"])
def test_trainer_denormalize_metrics(method: str):
    """When denormalize_metrics=True the reported RMSE must be in the original
    data scale, not the normalised [0,1] / z-score scale.

    Strategy: generate data with a known range, train with normalisation, then
    assert that the RMSE returned with denormalize_metrics=True is larger than
    the normalised RMSE (since the original scale has higher amplitude).
    """
    rng = np.random.default_rng(42)
    # Synthetic series with mean=100, std≈10 (well above the [0,1] normalised range)
    n = 300
    data = 100.0 + 10.0 * np.sin(np.linspace(0, 6 * np.pi, n)) + rng.normal(0, 0.5, n)

    model = AttentionLSTMModel(
        sequence_length=12,
        output_units=1,
        input_features=1,
        hidden_units=[16],
        attention_units=8,
    )

    trainer = Trainer(model=model, sequence_length=12, prediction_horizon=1)

    results_norm = trainer.train(
        data=data,
        epochs=2,
        batch_size=32,
        normalize=True,
        normalize_method=method,
        denormalize_metrics=False,
        early_stopping=False,
        verbose=0,
    )
    rmse_normalised = results_norm["metrics"]["rmse"]

    # Re-build to reset weights for a fair comparison
    model2 = AttentionLSTMModel(
        sequence_length=12,
        output_units=1,
        input_features=1,
        hidden_units=[16],
        attention_units=8,
    )
    trainer2 = Trainer(model=model2, sequence_length=12, prediction_horizon=1)
    results_denorm = trainer2.train(
        data=data,
        epochs=2,
        batch_size=32,
        normalize=True,
        normalize_method=method,
        denormalize_metrics=True,
        early_stopping=False,
        verbose=0,
    )
    rmse_original = results_denorm["metrics"]["rmse"]

    # Original-scale RMSE must be substantially larger than normalised RMSE
    # (data has mean=100, so even a 1% error is ~1.0 in original scale but ~0.01 normalised)
    assert rmse_original > rmse_normalised, (
        f"[{method}] denormalize_metrics=True should yield larger RMSE than normalised. "
        f"Got original={rmse_original:.6f}, normalised={rmse_normalised:.6f}"
    )

    # y_test_original_scale must be in the results dict
    assert "y_test_original_scale" in results_denorm
    assert "y_pred_original_scale" in results_denorm

    y_test_orig = results_denorm["y_test_original_scale"]
    # Original scale values should be in the neighbourhood of 100
    assert float(np.mean(y_test_orig)) > 10.0, (
        f"[{method}] y_test_original_scale does not appear to be in original scale: mean={np.mean(y_test_orig):.4f}"
    )
