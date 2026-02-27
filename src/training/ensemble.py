"""Ensemble forecaster combining multiple model predictions.

Supports mean, median, and optimised-weight combination strategies.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from scipy.optimize import minimize

logger = logging.getLogger(__name__)


class EnsembleForecaster:
    """Wraps N model instances and combines their predictions.

    Parameters
    ----------
    models : list
        Pre-built model instances (LSTMModel, GRUModel, TCNModel, etc.)
        that implement ``fit_model()``, ``predict()``, and ``evaluate()``.
    """

    def __init__(self, models: list[Any]) -> None:
        if len(models) < 2:
            raise ValueError("Ensemble requires at least 2 models")
        self.models = models
        self.weights: np.ndarray | None = None

    def fit_all(
        self,
        X: np.ndarray,
        y: np.ndarray,
        epochs: int = 100,
        batch_size: int = 32,
        validation_data: tuple[np.ndarray, np.ndarray] | None = None,
        early_stopping: bool = True,
        verbose: int = 0,
    ) -> list[dict[str, Any]]:
        """Train all member models sequentially.

        Returns a list of training histories, one per model.
        """
        histories = []
        for i, model in enumerate(self.models):
            logger.info("Training ensemble member %d/%d", i + 1, len(self.models))
            if model.model is None:
                model.build()
            h = model.fit_model(
                X,
                y,
                epochs=epochs,
                batch_size=batch_size,
                validation_data=validation_data,
                early_stopping=early_stopping,
                verbose=verbose,
            )
            histories.append(h)
        return histories

    def _collect_predictions(self, X: np.ndarray) -> np.ndarray:
        """Gather predictions from all members. Shape: [n_models, batch, horizon]."""
        preds = []
        for model in self.models:
            p = model.predict(X)
            preds.append(p)
        return np.stack(preds, axis=0)

    def predict_mean(self, X: np.ndarray) -> np.ndarray:
        """Ensemble prediction via simple average."""
        return np.mean(self._collect_predictions(X), axis=0)  # type: ignore[no-any-return]

    def predict_median(self, X: np.ndarray) -> np.ndarray:
        """Ensemble prediction via median (robust to outlier models)."""
        return np.median(self._collect_predictions(X), axis=0)  # type: ignore[no-any-return]

    def predict_weighted(self, X: np.ndarray) -> np.ndarray:
        """Ensemble prediction using optimised weights.

        Requires ``optimize_weights()`` to be called first.
        Falls back to ``predict_mean()`` if weights are not set.
        """
        if self.weights is None:
            logger.warning("Weights not optimised; falling back to mean")
            return self.predict_mean(X)

        preds = self._collect_predictions(X)  # [n_models, batch, horizon]
        # Weighted average: weights sum to 1
        weighted = np.tensordot(self.weights, preds, axes=([0], [0]))
        return weighted

    def optimize_weights(
        self,
        X_val: np.ndarray,
        y_val: np.ndarray,
    ) -> np.ndarray:
        """Find RMSE-minimising combination weights on validation data.

        Uses constrained optimisation (weights >= 0, sum to 1).
        Returns the optimised weight vector.
        """
        preds = self._collect_predictions(X_val)  # [n_models, batch, horizon]
        n_models = len(self.models)
        y_val_flat = y_val.reshape(-1)

        def objective(w: np.ndarray) -> float:
            combined = np.tensordot(w, preds, axes=([0], [0]))
            return float(np.sqrt(np.mean((y_val_flat - combined.reshape(-1)) ** 2)))

        # Initial: equal weights
        w0 = np.ones(n_models) / n_models
        constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}
        bounds = [(0.0, 1.0)] * n_models

        result = minimize(
            objective,
            w0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
        )

        self.weights = result.x
        assert self.weights is not None
        logger.info(
            "Optimised ensemble weights: %s (RMSE=%.6f)",
            np.round(self.weights, 4).tolist(),
            result.fun,
        )
        return self.weights
