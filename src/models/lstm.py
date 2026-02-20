"""LSTM/GRU models for time series forecasting."""

from __future__ import annotations

import logging
from typing import Any, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Try TensorFlow first, fall back to PyTorch
try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import Model, layers

    BACKEND = "tensorflow"
except ImportError:
    try:
        import torch  # noqa: F401
        import torch.nn as nn  # noqa: F401

        BACKEND = "pytorch"
    except ImportError:
        BACKEND = None
        logger.warning("No ML backend available. Install tensorflow or torch.")


class LSTMModel:
    """LSTM model for univariate time series forecasting."""

    def __init__(
        self,
        sequence_length: int = 24,
        hidden_units: Optional[List[int]] = None,
        dropout: float = 0.2,
        learning_rate: float = 0.001,
        output_units: int = 1,
        input_features: int = 1,
    ):
        self.sequence_length = sequence_length
        self.hidden_units = hidden_units or [128, 64]
        self.dropout = dropout
        self.learning_rate = learning_rate
        self.output_units = output_units
        self.input_features = input_features
        self.model = None
        self.history = None

    def _validate_xy(self, X: np.ndarray, y: Optional[np.ndarray] = None) -> None:
        if X.ndim != 3:
            raise ValueError(f"X must be 3D [batch, lookback, features], got {X.shape}")
        if X.shape[1] != self.sequence_length:
            raise ValueError(
                f"X lookback mismatch: expected {self.sequence_length}, got {X.shape[1]}"
            )
        if X.shape[2] != self.input_features:
            raise ValueError(
                f"input feature mismatch: expected {self.input_features}, got {X.shape[2]}"
            )

        if y is not None:
            if y.ndim != 2:
                raise ValueError(f"y must be 2D [batch, output_units], got {y.shape}")
            if y.shape[0] != X.shape[0]:
                raise ValueError("X and y batch size mismatch")
            if y.shape[1] != self.output_units:
                raise ValueError(
                    f"y output width mismatch: expected {self.output_units}, got {y.shape[1]}"
                )

    def build(self) -> None:
        """Build the LSTM model."""
        if BACKEND != "tensorflow":
            raise NotImplementedError("Only TensorFlow backend is currently supported")

        inputs = layers.Input(shape=(self.sequence_length, self.input_features))
        x = inputs
        for i, units in enumerate(self.hidden_units):
            return_sequences = i < len(self.hidden_units) - 1
            x = layers.LSTM(units, return_sequences=return_sequences, name=f"lstm_{i+1}")(x)
            x = layers.Dropout(self.dropout, name=f"dropout_{i+1}")(x)

        outputs = layers.Dense(self.output_units, name="output")(x)

        self.model = Model(inputs, outputs, name="lstm_forecaster")
        self.model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=self.learning_rate),
            loss="mse",
            metrics=["mae"],
        )

        logger.info("Built LSTM model: %s", self.hidden_units)

    def fit_model(
        self,
        X: np.ndarray,
        y: np.ndarray,
        epochs: int = 100,
        batch_size: int = 32,
        validation_data: Optional[Tuple[np.ndarray, np.ndarray]] = None,
        early_stopping: bool = True,
        shuffle: bool = False,
        verbose: int = 1,
        extra_callbacks: Optional[List[Any]] = None,
    ) -> dict:
        """Train the model with explicit validation split for time series."""
        self._validate_xy(X, y)
        if validation_data is not None:
            X_val, y_val = validation_data
            self._validate_xy(X_val, y_val)
        if self.model is None:
            self.build()

        callbacks = []
        if early_stopping:
            callbacks.append(
                keras.callbacks.EarlyStopping(
                    monitor="val_loss",
                    patience=10,
                    restore_best_weights=True,
                )
            )
        if extra_callbacks:
            callbacks.extend(extra_callbacks)

        self.history = self.model.fit(
            X,
            y,
            epochs=epochs,
            batch_size=batch_size,
            validation_data=validation_data,
            callbacks=callbacks,
            shuffle=shuffle,
            verbose=verbose,
        )

        return self.history.history

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Make predictions."""
        if self.model is None:
            raise RuntimeError("Model is not built/trained. Call build() or fit_model() first.")
        self._validate_xy(X)
        pred = self.model.predict(X, verbose=0)
        if pred.ndim != 2 or pred.shape[1] != self.output_units:
            raise RuntimeError(
                f"Prediction contract violated: expected [batch, {self.output_units}], got {pred.shape}"
            )
        return pred

    def evaluate(self, X: np.ndarray, y: np.ndarray) -> dict:
        """Evaluate the model."""
        if self.model is None:
            raise RuntimeError("Model is not built/trained. Call build() or fit_model() first.")
        self._validate_xy(X, y)
        loss, mae = self.model.evaluate(X, y, verbose=0)
        return {"loss": float(loss), "mae": float(mae)}

    def save(self, path: str) -> None:
        """Save model to file."""
        if self.model is None:
            raise RuntimeError("Model is not built/trained. Call build() or fit_model() first.")
        self.model.save(path)
        logger.info("Model saved to %s", path)

    def load(self, path: str) -> None:
        """Load model from file."""
        self.model = keras.models.load_model(path)
        logger.info("Model loaded from %s", path)


class BidirectionalLSTMModel(LSTMModel):
    """Bidirectional LSTM model."""

    def build(self) -> None:
        if BACKEND != "tensorflow":
            raise NotImplementedError("Only TensorFlow backend is currently supported")

        inputs = layers.Input(shape=(self.sequence_length, self.input_features))
        x = inputs
        for i, units in enumerate(self.hidden_units):
            return_sequences = i < len(self.hidden_units) - 1
            x = layers.Bidirectional(
                layers.LSTM(units, return_sequences=return_sequences), name=f"bilstm_{i+1}"
            )(x)
            x = layers.Dropout(self.dropout, name=f"dropout_{i+1}")(x)

        outputs = layers.Dense(self.output_units, name="output")(x)

        self.model = Model(inputs, outputs, name="bilstm_forecaster")
        self.model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=self.learning_rate),
            loss="mse",
            metrics=["mae"],
        )

        logger.info("Built Bidirectional LSTM model: %s", self.hidden_units)


class GRUModel(LSTMModel):
    """GRU model prototype for Phase 5 comparison PoC."""

    def build(self) -> None:
        if BACKEND != "tensorflow":
            raise NotImplementedError("Only TensorFlow backend is currently supported")

        inputs = layers.Input(shape=(self.sequence_length, self.input_features))
        x = inputs
        for i, units in enumerate(self.hidden_units):
            return_sequences = i < len(self.hidden_units) - 1
            x = layers.GRU(units, return_sequences=return_sequences, name=f"gru_{i+1}")(x)
            x = layers.Dropout(self.dropout, name=f"dropout_{i+1}")(x)

        outputs = layers.Dense(self.output_units, name="output")(x)
        self.model = Model(inputs, outputs, name="gru_forecaster")
        self.model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=self.learning_rate),
            loss="mse",
            metrics=["mae"],
        )

        logger.info("Built GRU model: %s", self.hidden_units)


class AttentionLSTMModel(LSTMModel):
    """LSTM with Attention mechanism."""

    def __init__(self, attention_units: int = 64, **kwargs):
        super().__init__(**kwargs)
        self.attention_units = attention_units

    def build(self) -> None:
        if BACKEND != "tensorflow":
            raise NotImplementedError("Only TensorFlow backend is currently supported")

        inputs = layers.Input(shape=(self.sequence_length, self.input_features))

        x = inputs
        for i, units in enumerate(self.hidden_units[:-1]):
            x = layers.LSTM(units, return_sequences=True, name=f"lstm_{i+1}")(x)
            x = layers.Dropout(self.dropout)(x)

        x = layers.LSTM(self.hidden_units[-1], return_sequences=True, name="lstm_last")(x)

        attention = layers.Dense(self.attention_units, activation="tanh", name="attention_hidden")(x)
        attention = layers.Dense(1, name="attention_scores")(attention)
        attention_weights = layers.Softmax(axis=1, name="attention_weights")(attention)

        context = layers.Multiply()([x, attention_weights])
        context = layers.Lambda(lambda v: tf.reduce_sum(v, axis=1))(context)

        outputs = layers.Dense(self.output_units, name="output")(context)

        self.model = Model(inputs, outputs, name="attention_lstm_forecaster")
        self.model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=self.learning_rate),
            loss="mse",
            metrics=["mae"],
        )

        logger.info("Built Attention LSTM model: %s", self.hidden_units)
