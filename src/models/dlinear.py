"""Lightweight DLinear-like model for edge forecasting."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from .lstm import DEFAULT_DROPOUT, _build_optimizer, _resolve_loss

logger = logging.getLogger(__name__)

try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import Model, layers
except ImportError as exc:  # pragma: no cover
    raise ImportError("TensorFlow is required for DLinearLikeModel. Install via `pip install tensorflow`.") from exc


class DLinearLikeModel:
    """Simple decomposition + linear projection model.

    This keeps a compatible training/predict/save interface while remaining
    lightweight for edge deployments.
    """

    _model_name: str = "dlinear_like_forecaster"

    def __init__(
        self,
        sequence_length: int = 24,
        output_units: int = 1,
        input_features: int = 1,
        hidden_units: list[int] | None = None,
        dropout: float = DEFAULT_DROPOUT,
        learning_rate: float = 0.001,
        loss: str = "mse",
        lr_schedule: str = "none",
        l2_reg: float = 0.0,
        static_features: int = 0,
        future_features: int = 0,
        recurrent_dropout: float = 0.0,
        use_residual: bool = False,
        use_layer_norm: bool = False,
    ) -> None:
        self.sequence_length = sequence_length
        self.output_units = output_units
        self.input_features = input_features
        self.hidden_units = hidden_units or [32]
        self.dropout = dropout
        self.learning_rate = learning_rate
        self.loss = loss
        self.lr_schedule = lr_schedule
        self.l2_reg = l2_reg
        self.static_features = static_features
        self.future_features = future_features
        self.model: Model | None = None
        self.history: dict[str, Any] | None = None

    def _validate_xy(self, X: Any, y: np.ndarray | None = None) -> None:
        past = X[0] if isinstance(X, list) else X
        if past.ndim != 3:
            raise ValueError(f"X_past must be 3D, got shape {past.shape}")
        if past.shape[1] != self.sequence_length:
            raise ValueError(f"lookback mismatch: expected {self.sequence_length}, got {past.shape[1]}")
        if y is not None:
            if y.ndim != 2:
                raise ValueError(f"y must be 2D, got shape {y.shape}")
            if y.shape[1] != self.output_units:
                raise ValueError(f"output width mismatch: expected {self.output_units}, got {y.shape[1]}")

    def _compile_model(self, total_steps: int | None = None) -> None:
        assert self.model is not None
        optimizer = _build_optimizer(self.learning_rate, self.lr_schedule, total_steps=total_steps)
        loss = _resolve_loss(self.loss)
        self.model.compile(optimizer=optimizer, loss=loss, metrics=["mae"])

    def build(self) -> None:
        reg = keras.regularizers.l2(self.l2_reg) if self.l2_reg > 0 else None

        past_input = layers.Input(shape=(self.sequence_length, self.input_features), name="past_input")
        model_inputs: list[tf.keras.layers.Layer] = [past_input]

        # DLinear-style split: smooth trend via average pooling and seasonal residual.
        trend = layers.AveragePooling1D(pool_size=3, strides=1, padding="same", name="trend_pool")(past_input)
        seasonal = layers.Subtract(name="seasonal_residual")([past_input, trend])

        trend_flat = layers.Flatten(name="trend_flat")(trend)
        seasonal_flat = layers.Flatten(name="seasonal_flat")(seasonal)
        x = layers.Concatenate(name="decomp_concat")([trend_flat, seasonal_flat])

        if self.future_features > 0:
            future_input = layers.Input(shape=(self.output_units, self.future_features), name="future_input")
            model_inputs.append(future_input)
            x = layers.Concatenate(name="feature_concat_future")(
                [x, layers.Flatten(name="future_flatten")(future_input)]
            )

        if self.static_features > 0:
            static_input = layers.Input(shape=(self.static_features,), name="static_input")
            model_inputs.append(static_input)
            x = layers.Concatenate(name="feature_concat_static")([x, static_input])

        for i, units in enumerate(self.hidden_units):
            x = layers.Dense(units, activation="relu", kernel_regularizer=reg, name=f"dlinear_dense_{i + 1}")(x)
            if self.dropout > 0:
                x = layers.Dropout(self.dropout, name=f"dlinear_dropout_{i + 1}")(x)

        output = layers.Dense(self.output_units, name="output")(x)
        self.model = Model(inputs=model_inputs, outputs=output, name=self._model_name)
        self._compile_model()
        logger.info(
            "Built DLinear-like model - lookback=%d, features=%d, output=%d",
            self.sequence_length,
            self.input_features,
            self.output_units,
        )

    def fit_model(
        self,
        X: np.ndarray,
        y: np.ndarray,
        epochs: int = 100,
        batch_size: int = 32,
        validation_data: tuple[np.ndarray, np.ndarray] | None = None,
        early_stopping: bool = True,
        shuffle: bool = False,
        verbose: int = 1,
        extra_callbacks: list[Any] | None = None,
    ) -> dict[str, Any]:
        self._validate_xy(X, y)
        if validation_data is not None:
            X_val, y_val = validation_data
            self._validate_xy(X_val, y_val)

        n_samples = X[0].shape[0] if isinstance(X, list) else X.shape[0]
        total_steps = (n_samples // max(batch_size, 1)) * epochs
        if self.model is None:
            self.build()
        assert self.model is not None
        if self.lr_schedule in ("cosine", "exponential"):
            self._compile_model(total_steps=total_steps)

        callbacks = []
        if early_stopping:
            callbacks.append(keras.callbacks.EarlyStopping(monitor="val_loss", patience=10, restore_best_weights=True))
        if self.lr_schedule == "reduce_on_plateau":
            callbacks.append(
                keras.callbacks.ReduceLROnPlateau(
                    monitor="val_loss",
                    factor=0.5,
                    patience=5,
                    min_lr=self.learning_rate * 0.01,
                )
            )
        if extra_callbacks:
            callbacks.extend(extra_callbacks)

        fit_history = self.model.fit(
            X,
            y,
            epochs=epochs,
            batch_size=batch_size,
            validation_data=validation_data,
            callbacks=callbacks,
            shuffle=shuffle,
            verbose=verbose,
        )
        self.history = dict(fit_history.history)
        return self.history

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("Model is not built/trained.")
        self._validate_xy(X)
        return np.asarray(self.model.predict(X, verbose=0), dtype=np.float32)

    def evaluate(self, X: np.ndarray, y: np.ndarray) -> dict[str, float]:
        if self.model is None:
            raise RuntimeError("Model is not built/trained.")
        self._validate_xy(X, y)
        loss, mae = self.model.evaluate(X, y, verbose=0)
        return {"loss": float(loss), "mae": float(mae)}

    def save(self, path: str) -> None:
        if self.model is None:
            raise RuntimeError("Model is not built/trained.")
        if path.lower().endswith(".keras"):
            path = path[:-6] + ".h5"
        self.model.save(path)
        logger.info("DLinear-like model saved to %s", path)

    def load(self, path: str) -> None:
        import os

        resolved = path
        if not os.path.exists(resolved) and resolved.lower().endswith(".keras"):
            h5_candidate = resolved[:-6] + ".h5"
            if os.path.exists(h5_candidate):
                resolved = h5_candidate
        self.model = keras.models.load_model(resolved, compile=False)
        self._compile_model()
        logger.info("DLinear-like model loaded from %s", resolved)
