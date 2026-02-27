"""Temporal Convolutional Network (TCN) for time-series forecasting.

Provides a dilated causal convolution model with the same public API as
``LSTMModel``, enabling drop-in substitution and ensemble diversity.
"""

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
    raise ImportError(
        "TensorFlow is required for TCN models. Install via `pip install tensorflow`."
    ) from exc


class TCNModel:
    """Temporal Convolutional Network with dilated causal convolutions.

    Each residual block contains two causal Conv1D layers with exponentially
    increasing dilation rates, weight normalization via BatchNormalization,
    and residual skip connections.

    Parameters
    ----------
    sequence_length : int
        Look-back window size.
    output_units : int
        Forecast horizon.
    input_features : int
        Number of input channels (past covariates).
    num_filters : int
        Number of filters per convolutional layer.
    kernel_size : int
        Kernel size for causal convolutions.
    num_blocks : int
        Number of residual blocks (dilation doubles each block: 1, 2, 4, ...).
    dropout : float
        Spatial dropout rate applied after each conv layer.
    learning_rate : float
        Adam learning rate.
    loss : str
        Loss function name (same options as LSTMModel).
    lr_schedule : str
        Learning rate schedule strategy.
    l2_reg : float
        L2 regularization weight for conv kernels.
    static_features : int
        Number of static covariates (0 if none).
    future_features : int
        Number of future-known covariates (0 if none).
    """

    _model_name: str = "tcn_forecaster"

    def __init__(
        self,
        sequence_length: int = 24,
        output_units: int = 1,
        input_features: int = 1,
        num_filters: int = 64,
        kernel_size: int = 3,
        num_blocks: int = 3,
        dropout: float = DEFAULT_DROPOUT,
        learning_rate: float = 0.001,
        loss: str = "mse",
        lr_schedule: str = "none",
        l2_reg: float = 0.0,
        static_features: int = 0,
        future_features: int = 0,
        # Unused kwargs for API compat with LSTMModel construction
        hidden_units: list[int] | None = None,
        recurrent_dropout: float = 0.0,
        use_residual: bool = False,
        use_layer_norm: bool = False,
    ) -> None:
        self.sequence_length = sequence_length
        self.output_units = output_units
        self.input_features = input_features
        self.num_filters = num_filters
        self.kernel_size = kernel_size
        self.num_blocks = num_blocks
        self.dropout = dropout
        self.learning_rate = learning_rate
        self.loss = loss
        self.lr_schedule = lr_schedule
        self.l2_reg = l2_reg
        self.static_features = static_features
        self.future_features = future_features
        self.model: Model | None = None
        self.history: dict[str, Any] | None = None

    def _get_regularizer(self) -> keras.regularizers.Regularizer | None:
        if self.l2_reg > 0:
            return keras.regularizers.l2(self.l2_reg)
        return None

    def _residual_block(self, x: tf.Tensor, dilation_rate: int, block_idx: int) -> tf.Tensor:
        """Single TCN residual block with two causal conv layers."""
        reg = self._get_regularizer()
        skip = x

        for j in range(2):
            x = layers.Conv1D(
                filters=self.num_filters,
                kernel_size=self.kernel_size,
                dilation_rate=dilation_rate,
                padding="causal",
                activation="relu",
                kernel_regularizer=reg,
                name=f"tcn_conv_{block_idx}_{j}",
            )(x)
            x = layers.BatchNormalization(name=f"tcn_bn_{block_idx}_{j}")(x)
            if self.dropout > 0:
                x = layers.SpatialDropout1D(self.dropout, name=f"tcn_drop_{block_idx}_{j}")(x)

        # Residual: project skip if channel dims differ
        if skip.shape[-1] != self.num_filters:
            skip = layers.Conv1D(self.num_filters, 1, name=f"tcn_skip_proj_{block_idx}")(skip)

        return layers.Add(name=f"tcn_residual_{block_idx}")([x, skip])

    def _compile_model(self, total_steps: int | None = None) -> None:
        assert self.model is not None
        optimizer = _build_optimizer(self.learning_rate, self.lr_schedule, total_steps=total_steps)
        loss = _resolve_loss(self.loss)
        self.model.compile(optimizer=optimizer, loss=loss, metrics=["mae"])

    def build(self) -> None:
        """Build the TCN Keras model."""
        past_input = layers.Input(
            shape=(self.sequence_length, self.input_features), name="past_input"
        )
        model_inputs: list[tf.keras.layers.Layer] = [past_input]

        x = past_input
        for i in range(self.num_blocks):
            x = self._residual_block(x, dilation_rate=2**i, block_idx=i)

        # Global pooling over the temporal axis
        x = layers.GlobalAveragePooling1D(name="tcn_gap")(x)
        concat_tensors = [x]

        if self.future_features > 0:
            future_input = layers.Input(
                shape=(self.output_units, self.future_features), name="future_input"
            )
            model_inputs.append(future_input)
            concat_tensors.append(layers.Flatten(name="future_flatten")(future_input))

        if self.static_features > 0:
            static_input = layers.Input(shape=(self.static_features,), name="static_input")
            model_inputs.append(static_input)
            concat_tensors.append(
                layers.Dense(
                    min(16, self.static_features * 2),
                    activation="relu",
                    name="static_dense",
                )(static_input)
            )

        x = layers.Concatenate(name="feature_concat")(concat_tensors) if len(concat_tensors) > 1 else concat_tensors[0]

        output = layers.Dense(self.output_units, name="output")(x)
        self.model = Model(inputs=model_inputs, outputs=output, name=self._model_name)
        self._compile_model()
        logger.info(
            "Built TCN – filters=%d, blocks=%d, kernel=%d, loss=%s",
            self.num_filters,
            self.num_blocks,
            self.kernel_size,
            self.loss,
        )

    def _validate_xy(self, X: Any, y: np.ndarray | None = None) -> None:
        """Basic input validation (mirrors LSTMModel contract)."""
        past = X[0] if isinstance(X, list) else X
        if past.ndim != 3:
            raise ValueError(f"X_past must be 3D, got shape {past.shape}")
        if past.shape[1] != self.sequence_length:
            raise ValueError(f"lookback mismatch: expected {self.sequence_length}, got {past.shape[1]}")

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
        """Train the model (same interface as LSTMModel)."""
        self._validate_xy(X, y)
        n_samples = X[0].shape[0] if isinstance(X, list) else X.shape[0]
        total_steps = (n_samples // max(batch_size, 1)) * epochs

        if self.model is None:
            self.build()
        assert self.model is not None
        if self.lr_schedule in ("cosine", "exponential"):
            self._compile_model(total_steps=total_steps)

        callbacks = []
        if early_stopping:
            callbacks.append(
                keras.callbacks.EarlyStopping(
                    monitor="val_loss", patience=10, restore_best_weights=True
                )
            )
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
            X, y,
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
            raise RuntimeError("Model not built/trained.")
        self._validate_xy(X)
        pred = np.asarray(self.model.predict(X, verbose=0), dtype=float)
        return pred

    def evaluate(self, X: np.ndarray, y: np.ndarray) -> dict:
        if self.model is None:
            raise RuntimeError("Model not built/trained.")
        loss, mae = self.model.evaluate(X, y, verbose=0)
        return {"loss": float(loss), "mae": float(mae)}

    def save(self, path: str) -> None:
        if self.model is None:
            raise RuntimeError("Model not built/trained.")
        if path.lower().endswith(".keras"):
            path = path[:-6] + ".h5"
        self.model.save(path)
        logger.info("TCN model saved to %s", path)

    def load(self, path: str) -> None:
        import os

        resolved = path
        if not os.path.exists(resolved) and resolved.lower().endswith(".keras"):
            h5_candidate = resolved[:-6] + ".h5"
            if os.path.exists(h5_candidate):
                resolved = h5_candidate
        self.model = keras.models.load_model(resolved, compile=False)
        self._compile_model()
        logger.info("TCN model loaded from %s", resolved)
