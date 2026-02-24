# LSTM/GRU models for time series forecasting
"""Model definitions for spline‑LSTM.

This module provides:
- `LSTMModel` – core univariate/multivariate LSTM model with optional static and future covariates.
- `BidirectionalLSTMModel` – same interface, bidirectional LSTM backbone.
- `GRUModel` – GRU‑based variant.
- `AttentionLSTMModel` – LSTM with a simple attention mechanism.

Key improvements over the previous version:
- Removed the unused PyTorch fallback – the project now requires TensorFlow.
- Added explicit validation helpers (`_validate_past`, `_validate_future`, `_validate_static`, `_validate_xy`).
- Centralised LSTM stack construction in `_build_lstm_stack` to avoid duplication across subclasses.
- Consistent logging and detailed docstrings for all public methods.
- Type‑annotated attributes and optional model typing.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Backend import – TensorFlow is mandatory for the current codebase.
# ---------------------------------------------------------------------------
try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import Model, layers
except ImportError as exc:  # pragma: no cover – CI ensures TF is installed.
    raise ImportError(
        "TensorFlow is required for spline‑LSTM models. Please install it via "
        "`pip install tensorflow`."
    ) from exc

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_DROPOUT = 0.2

# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------
def _ensure_3d(arr: np.ndarray, name: str) -> None:
    if arr.ndim != 3:
        raise ValueError(f"{name} must be a 3‑D array, got shape {arr.shape}")

def _ensure_2d(arr: np.ndarray, name: str) -> None:
    if arr.ndim != 2:
        raise ValueError(f"{name} must be a 2‑D array, got shape {arr.shape}")

# ---------------------------------------------------------------------------
class LSTMModel:
    """Base LSTM model supporting optional static and future covariates.

    Parameters
    ----------
    sequence_length: int
        Look‑back window size.
    hidden_units: List[int] | None
        Number of units per LSTM layer. ``None`` defaults to ``[128, 64]``.
    dropout: float
        Dropout probability applied after each LSTM layer.
    learning_rate: float
        Adam learning rate.
    output_units: int
        Horizon * number of target features.
    input_features: int
        Number of past (time‑varying) input features.
    static_features: int
        Number of static covariates (0 if none).
    future_features: int
        Number of future‑known covariates (0 if none).
    """

    def __init__(
        self,
        sequence_length: int = 24,
        hidden_units: Optional[List[int]] = None,
        dropout: float = DEFAULT_DROPOUT,
        learning_rate: float = 0.001,
        output_units: int = 1,
        input_features: int = 1,
        static_features: int = 0,
        future_features: int = 0,
    ) -> None:
        self.sequence_length = sequence_length
        self.hidden_units = hidden_units or [128, 64]
        self.dropout = dropout
        self.learning_rate = learning_rate
        self.output_units = output_units
        self.input_features = input_features
        self.static_features = static_features
        self.future_features = future_features
        self.model: Optional[Model] = None
        self.history: Optional[dict] = None

    # ---------------------------------------------------------------------
    # Validation helpers (private)
    # ---------------------------------------------------------------------
    def _validate_past(self, X_past: np.ndarray) -> None:
        _ensure_3d(X_past, "X_past")
        if X_past.shape[1] != self.sequence_length:
            raise ValueError(
                f"X_past lookback mismatch: expected {self.sequence_length}, got {X_past.shape[1]}"
            )
        if X_past.shape[2] != self.input_features:
            raise ValueError(
                f"X_past feature mismatch: expected {self.input_features}, got {X_past.shape[2]}"
            )

    def _validate_future(self, X_future: np.ndarray) -> None:
        _ensure_3d(X_future, "X_future")
        if X_future.shape[1] != self.output_units:
            raise ValueError(
                f"X_future horizon mismatch: expected {self.output_units}, got {X_future.shape[1]}"
            )
        if X_future.shape[2] != self.future_features:
            raise ValueError(
                f"X_future feature mismatch: expected {self.future_features}, got {X_future.shape[2]}"
            )

    def _validate_static(self, X_static: np.ndarray) -> None:
        _ensure_2d(X_static, "X_static")
        if X_static.shape[1] != self.static_features:
            raise ValueError(
                f"X_static feature mismatch: expected {self.static_features}, got {X_static.shape[1]}"
            )

    def _validate_xy(self, X: Any, y: Optional[np.ndarray] = None) -> None:
        """Validate input tensors ``X`` (list or array) and optional ``y``.

        ``X`` can be:
        - a single 3‑D ``np.ndarray`` when no covariates are used, or
        - a list ``[X_past, X_future?, X_static?]`` where the optional
          entries appear only if the corresponding feature count is > 0.
        """
        if isinstance(X, list):
            X_past = X[0]
            self._validate_past(X_past)
            if self.future_features > 0:
                if len(X) < 2:
                    raise ValueError(
                        "future_features declared but not provided in X list"
                    )
                self._validate_future(X[1])
            if self.static_features > 0:
                idx = 2 if self.future_features > 0 else 1
                if len(X) <= idx:
                    raise ValueError(
                        "static_features declared but not provided in X list"
                    )
                self._validate_static(X[idx])
        else:
            if self.static_features > 0 or self.future_features > 0:
                raise ValueError(
                    "static_features or future_features declared but X is not a list"
                )
            self._validate_past(X)
        if y is not None:
            _ensure_2d(y, "y")
            batch = X[0].shape[0] if isinstance(X, list) else X.shape[0]
            if y.shape[0] != batch:
                raise ValueError("X and y batch size mismatch")
            if y.shape[1] != self.output_units:
                raise ValueError(
                    f"y horizon mismatch: expected {self.output_units}, got {y.shape[1]}"
                )

    # ---------------------------------------------------------------------
    # Model construction helpers
    # ---------------------------------------------------------------------
    def _build_lstm_stack(self, inputs: List[tf.keras.layers.Layer]) -> tf.keras.layers.Layer:
        """Construct the shared LSTM backbone.

        Returns the final tensor after the LSTM stack (before any covariate
        concatenation). ``inputs`` is a list containing the past input layer.
        """
        x = inputs[0]
        for i, units in enumerate(self.hidden_units):
            return_seq = i < len(self.hidden_units) - 1
            x = layers.LSTM(units, return_sequences=return_seq, name=f"lstm_{i+1}")(x)
            if self.dropout > 0:
                x = layers.Dropout(self.dropout, name=f"dropout_{i+1}")(x)
        return x

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def build(self) -> None:
        """Build the Keras model according to the current configuration.

        The method creates input placeholders for past, future and static
        covariates (if their feature counts are > 0) and concatenates them
        before the final dense output layer.
        """
        past_input = layers.Input(
            shape=(self.sequence_length, self.input_features), name="past_input"
        )
        model_inputs: List[tf.keras.layers.Layer] = [past_input]
        concat_tensors: List[tf.keras.layers.Layer] = []
        lstm_out = self._build_lstm_stack([past_input])
        concat_tensors.append(lstm_out)
        if self.future_features > 0:
            future_input = layers.Input(
                shape=(self.output_units, self.future_features), name="future_input"
            )
            model_inputs.append(future_input)
            concat_tensors.append(layers.Flatten(name="future_flatten")(future_input))
        if self.static_features > 0:
            static_input = layers.Input(
                shape=(self.static_features,), name="static_input"
            )
            model_inputs.append(static_input)
            concat_tensors.append(
                layers.Dense(
                    min(16, self.static_features * 2), activation="relu", name="static_dense"
                )(static_input)
            )
        if len(concat_tensors) > 1:
            x = layers.Concatenate(name="feature_concat")(concat_tensors)
        else:
            x = concat_tensors[0]
        output = layers.Dense(self.output_units, name="output")(x)
        self.model = Model(inputs=model_inputs, outputs=output, name="lstm_forecaster")
        self.model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=self.learning_rate),
            loss="mse",
            metrics=["mae"],
        )
        logger.info(
            "Built LSTM model – past=%d, static=%d, future=%d",
            self.input_features,
            self.static_features,
            self.future_features,
        )

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
        """Train the model.

        Parameters are forwarded to ``tf.keras.Model.fit``. Early stopping is
        enabled by default.
        """
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
                    monitor="val_loss", patience=10, restore_best_weights=True
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
        return self.history.history  # type: ignore[return-value]

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Generate predictions for ``X``.

        Raises ``RuntimeError`` if the model has not been built/trained.
        """
        if self.model is None:
            raise RuntimeError(
                "Model is not built/trained. Call build() or fit_model() first."
            )
        self._validate_xy(X)
        pred = self.model.predict(X, verbose=0)
        if pred.ndim != 2 or pred.shape[1] != self.output_units:
            raise RuntimeError(
                f"Prediction contract violated: expected [batch, {self.output_units}], got {pred.shape}"
            )
        return pred

    def evaluate(self, X: np.ndarray, y: np.ndarray) -> dict:
        """Evaluate the model and return loss/MAE.
        """
        if self.model is None:
            raise RuntimeError(
                "Model is not built/trained. Call build() or fit_model() first."
            )
        self._validate_xy(X, y)
        loss, mae = self.model.evaluate(X, y, verbose=0)
        return {"loss": float(loss), "mae": float(mae)}

    def save(self, path: str) -> None:
        """Save the Keras model to ``path``.
        """
        if self.model is None:
            raise RuntimeError(
                "Model is not built/trained. Call build() or fit_model() first."
            )
        self.model.save(path)
        logger.info("Model saved to %s", path)

    def load(self, path: str) -> None:
        """Load a Keras model from ``path``.
        """
        self.model = keras.models.load_model(path)
        logger.info("Model loaded from %s", path)

# ---------------------------------------------------------------------------
# Sub‑classes with specialised backbones
# ---------------------------------------------------------------------------
class BidirectionalLSTMModel(LSTMModel):
    """Bidirectional LSTM variant – shares the same public API as ``LSTMModel``."""

    def _build_lstm_stack(self, inputs: List[tf.keras.layers.Layer]) -> tf.keras.layers.Layer:
        x = inputs[0]
        for i, units in enumerate(self.hidden_units):
            return_seq = i < len(self.hidden_units) - 1
            x = layers.Bidirectional(
                layers.LSTM(units, return_sequences=return_seq), name=f"bilstm_{i+1}"
            )(x)
            if self.dropout > 0:
                x = layers.Dropout(self.dropout, name=f"dropout_{i+1}")(x)
        return x

    def build(self) -> None:
        past_input = layers.Input(
            shape=(self.sequence_length, self.input_features), name="past_input"
        )
        model_inputs: List[tf.keras.layers.Layer] = [past_input]
        concat_tensors: List[tf.keras.layers.Layer] = []
        lstm_out = self._build_lstm_stack([past_input])
        concat_tensors.append(lstm_out)
        if self.future_features > 0:
            future_input = layers.Input(
                shape=(self.output_units, self.future_features), name="future_input"
            )
            model_inputs.append(future_input)
            concat_tensors.append(layers.Flatten(name="future_flatten")(future_input))
        if self.static_features > 0:
            static_input = layers.Input(
                shape=(self.static_features,), name="static_input"
            )
            model_inputs.append(static_input)
            concat_tensors.append(
                layers.Dense(
                    min(16, self.static_features * 2), activation="relu", name="static_dense"
                )(static_input)
            )
        if len(concat_tensors) > 1:
            x = layers.Concatenate(name="feature_concat")(concat_tensors)
        else:
            x = concat_tensors[0]
        output = layers.Dense(self.output_units, name="output")(x)
        self.model = Model(inputs=model_inputs, outputs=output, name="bilstm_forecaster")
        self.model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=self.learning_rate),
            loss="mse",
            metrics=["mae"],
        )
        logger.info("Built Bidirectional LSTM model with %s", self.hidden_units)

class GRUModel(LSTMModel):
    """GRU variant – retains the same external interface as ``LSTMModel``."""

    def _build_lstm_stack(self, inputs: List[tf.keras.layers.Layer]) -> tf.keras.layers.Layer:
        x = inputs[0]
        for i, units in enumerate(self.hidden_units):
            return_seq = i < len(self.hidden_units) - 1
            x = layers.GRU(units, return_sequences=return_seq, name=f"gru_{i+1}")(x)
            if self.dropout > 0:
                x = layers.Dropout(self.dropout, name=f"dropout_{i+1}")(x)
        return x

    def build(self) -> None:
        past_input = layers.Input(
            shape=(self.sequence_length, self.input_features), name="past_input"
        )
        model_inputs: List[tf.keras.layers.Layer] = [past_input]
        concat_tensors: List[tf.keras.layers.Layer] = []
        gru_out = self._build_lstm_stack([past_input])
        concat_tensors.append(gru_out)
        if self.future_features > 0:
            future_input = layers.Input(
                shape=(self.output_units, self.future_features), name="future_input"
            )
            model_inputs.append(future_input)
            concat_tensors.append(layers.Flatten(name="future_flatten")(future_input))
        if self.static_features > 0:
            static_input = layers.Input(
                shape=(self.static_features,), name="static_input"
            )
            model_inputs.append(static_input)
            concat_tensors.append(
                layers.Dense(
                    min(16, self.static_features * 2), activation="relu", name="static_dense"
                )(static_input)
            )
        if len(concat_tensors) > 1:
            x = layers.Concatenate(name="feature_concat")(concat_tensors)
        else:
            x = concat_tensors[0]
        output = layers.Dense(self.output_units, name="output")(x)
        self.model = Model(inputs=model_inputs, outputs=output, name="gru_forecaster")
        self.model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=self.learning_rate),
            loss="mse",
            metrics=["mae"],
        )
        logger.info("Built GRU model with %s", self.hidden_units)

class AttentionLSTMModel(LSTMModel):
    """LSTM with a simple attention mechanism.

    The attention block is applied after the final LSTM layer and before the
    dense output.
    """

    def __init__(self, attention_units: int = 64, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.attention_units = attention_units

    def build(self) -> None:
        past_input = layers.Input(
            shape=(self.sequence_length, self.input_features), name="past_input"
        )
        x = past_input
        for i, units in enumerate(self.hidden_units[:-1]):
            x = layers.LSTM(units, return_sequences=True, name=f"lstm_{i+1}")(x)
            x = layers.Dropout(self.dropout)(x)
        x = layers.LSTM(self.hidden_units[-1], return_sequences=True, name="lstm_last")(x)
        # Attention
        att_hidden = layers.Dense(self.attention_units, activation="tanh", name="attention_hidden")(x)
        att_scores = layers.Dense(1, name="attention_scores")(att_hidden)
        att_weights = layers.Softmax(axis=1, name="attention_weights")(att_scores)
        context = layers.Multiply()([x, att_weights])
        context = layers.Lambda(lambda v: tf.reduce_sum(v, axis=1), name="attention_context")(context)
        output = layers.Dense(self.output_units, name="output")(context)
        self.model = Model(inputs=past_input, outputs=output, name="attention_lstm_forecaster")
        self.model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=self.learning_rate),
            loss="mse",
            metrics=["mae"],
        )
        logger.info("Built Attention LSTM model with %s", self.hidden_units)
