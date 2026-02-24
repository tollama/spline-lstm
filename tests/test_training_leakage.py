"""Tests for leakage-safe training behavior."""

import os
import sys

import numpy as np

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from training.trainer import Trainer


class DummyModel:
    def __init__(self):
        self.last_fit = None

    def fit_model(self, X, y, **kwargs):
        self.last_fit = {"X": X, "y": y, "kwargs": kwargs}
        return {"loss": [0.1], "val_loss": [0.2]}

    def predict(self, X):
        return np.zeros((len(X), 1), dtype=float)

    def save(self, path):
        return None

    def load(self, path):
        return None


def test_trainer_normalizes_after_split_with_train_fit_only():
    """Normalization must be fit on train split only, not full series."""
    model = DummyModel()
    trainer = Trainer(model=model, sequence_length=2, prediction_horizon=1)

    # Outlier in test zone; if leakage exists (fit on full data), train max << 1.
    data = np.array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 1000], dtype=float)

    trainer.train(
        data,
        epochs=1,
        batch_size=2,
        test_size=0.25,
        val_size=0.25,
        normalize=True,
        verbose=0,
    )

    # Train normalization should be based on train-only max(=5), not full-series max(=1000).
    assert np.isclose(trainer.norm_params["max"], 5.0, atol=1e-6)


def test_trainer_uses_explicit_validation_data_and_no_shuffle():
    """Time-series fit must use explicit validation_data and shuffle=False."""
    model = DummyModel()
    trainer = Trainer(model=model, sequence_length=2, prediction_horizon=1)

    data = np.linspace(0, 1, 40)
    trainer.train(data, epochs=1, batch_size=4, test_size=0.2, val_size=0.2, verbose=0)

    kwargs = model.last_fit["kwargs"]
    assert "validation_data" in kwargs
    assert kwargs["validation_data"] is not None
    assert kwargs.get("shuffle") is False
