"""
Example: Spline + LSTM Forecasting with Covariates
====================================================

This script demonstrates how to incorporate external variables into a
Spline-LSTM forecast.  We use two covariate types:

* **Future-known covariates** – values that are already known for the entire
  forecast horizon at prediction time (e.g. promotions, weather forecasts,
  calendar flags).  Shape: [batch, horizon, n_future_features].

* **Static covariates** – time-invariant metadata about each sample (e.g.
  store ID encoded as a numeric value, category embedding).
  Shape: [batch, n_static_features].

The example generates a synthetic S1 scenario (smooth trend + seasonality)
that includes a temperature signal and a binary promotion flag as future
covariates, trains an LSTMModel with those inputs, and shows how to run
inference on new data.

Run with:
    python3 examples/covariate_example.py
"""

from __future__ import annotations

import numpy as np

from src import LSTMModel, SplinePreprocessor, Trainer
from src.data.synthetic_generator import GeneratorConfig, generate_dataframe

# ---------------------------------------------------------------------------
# 1. Generate synthetic data with covariates
# ---------------------------------------------------------------------------
print("=" * 60)
print("Spline + LSTM – Covariate Example")
print("=" * 60)

print("\n[1] Generating synthetic data with covariates ...")
cfg = GeneratorConfig(
    scenario="S1",
    n_samples=720,       # 720 hourly observations = 30 days
    seed=42,
    covariates=("temp", "promo"),
)
df = generate_dataframe(cfg)

print(f"    Columns : {list(df.columns)}")
print(f"    Shape   : {df.shape}")
print(f"    Sample  :\n{df.head(3).to_string(index=False)}")

target_series = df["target"].to_numpy(dtype=np.float32)
temp_series   = df["temp"].to_numpy(dtype=np.float32)
promo_series  = df["promo"].to_numpy(dtype=np.float32)

# ---------------------------------------------------------------------------
# 2. Spline preprocessing (target only – covariates are already clean)
# ---------------------------------------------------------------------------
print("\n[2] Spline preprocessing of target series ...")
preprocessor = SplinePreprocessor(degree=3, smoothing_factor=0.3)
target_smooth = preprocessor.smooth(target_series, window=5)
print(f"    Original var: {np.var(target_series):.4f}  →  Smoothed var: {np.var(target_smooth):.4f}")

# ---------------------------------------------------------------------------
# 3. Build supervised windows
# ---------------------------------------------------------------------------
LOOKBACK = 24   # look back 24 hours
HORIZON  = 3    # predict next 3 hours

print(f"\n[3] Building windows  (lookback={LOOKBACK}, horizon={HORIZON}) ...")
n = len(target_smooth) - LOOKBACK - HORIZON + 1

X_past   = np.zeros((n, LOOKBACK, 1),  dtype=np.float32)  # [batch, lookback, 1]
X_future = np.zeros((n, HORIZON,  2),  dtype=np.float32)  # [batch, horizon, 2] = temp + promo
y        = np.zeros((n, HORIZON),      dtype=np.float32)

for i in range(n):
    X_past[i,   :, 0] = target_smooth[i : i + LOOKBACK]
    X_future[i, :, 0] = temp_series  [i + LOOKBACK : i + LOOKBACK + HORIZON]
    X_future[i, :, 1] = promo_series [i + LOOKBACK : i + LOOKBACK + HORIZON]
    y[i, :]            = target_smooth[i + LOOKBACK : i + LOOKBACK + HORIZON]

print(f"    X_past   : {X_past.shape}")
print(f"    X_future : {X_future.shape}")
print(f"    y        : {y.shape}")

# ---------------------------------------------------------------------------
# 4. Build and train the model
# ---------------------------------------------------------------------------
print("\n[4] Building LSTMModel with future covariates ...")
model = LSTMModel(
    sequence_length=LOOKBACK,
    output_units=HORIZON,
    input_features=1,          # one target feature in the past window
    future_features=2,         # temp + promo are known for the forecast horizon
    hidden_units=[64, 32],
    dropout=0.2,
    learning_rate=0.001,
)
model.build()
print(f"    Model inputs : {[inp.shape for inp in model.model.inputs]}")
print(f"    Model outputs: {model.model.output_shape}")

# Chronological train / test split (no Trainer normalisation here since we
# manually control the window data)
split = int(0.8 * n)
X_past_train,   X_past_test   = X_past[:split],   X_past[split:]
X_future_train, X_future_test = X_future[:split],  X_future[split:]
y_train, y_test                = y[:split],          y[split:]

print(f"\n[5] Training (train={split} samples, test={n - split} samples) ...")
model.fit_model(
    X=[X_past_train, X_future_train],
    y=y_train,
    epochs=30,
    batch_size=32,
    validation_data=([X_past_test, X_future_test], y_test),
    early_stopping=True,
    verbose=0,
)

# ---------------------------------------------------------------------------
# 5. Evaluate
# ---------------------------------------------------------------------------
eval_metrics = model.evaluate([X_past_test, X_future_test], y_test)
preds = model.predict([X_past_test, X_future_test])

mae  = float(np.mean(np.abs(y_test - preds)))
rmse = float(np.sqrt(np.mean((y_test - preds) ** 2)))

print("\n[6] Evaluation (test set):")
print(f"    Keras loss (MSE) : {eval_metrics['loss']:.6f}")
print(f"    Keras MAE        : {eval_metrics['mae']:.6f}")
print(f"    MAE  (manual)    : {mae:.6f}")
print(f"    RMSE (manual)    : {rmse:.6f}")

# ---------------------------------------------------------------------------
# 6. Inference: predict next HORIZON steps from the last window
# ---------------------------------------------------------------------------
print("\n[7] Inference – predicting the final window ...")

last_past   = X_past[-1:]    # shape [1, LOOKBACK, 1]
last_future = X_future[-1:]  # shape [1, HORIZON,  2]

next_pred = model.predict([last_past, last_future])
print(f"    Input  last {LOOKBACK} target values : {X_past[-1, :, 0].round(4)}")
print(f"    Future temp/promo (next {HORIZON}h)  : {X_future[-1].round(4)}")
print(f"    Predicted next {HORIZON} steps        : {next_pred.flatten().round(4)}")
print(f"    Actual  next {HORIZON} steps           : {y[-1].round(4)}")

# ---------------------------------------------------------------------------
# 7. Static covariates – brief illustration
# ---------------------------------------------------------------------------
print("\n[8] Static covariate example (store-type embedding) ...")

STORE_TYPE_DIM = 4  # pretend store type is encoded as 4 integers

model_static = LSTMModel(
    sequence_length=LOOKBACK,
    output_units=HORIZON,
    input_features=1,
    future_features=2,
    static_features=STORE_TYPE_DIM,
    hidden_units=[64, 32],
    dropout=0.2,
    learning_rate=0.001,
)
model_static.build()
print(f"    Model inputs: {[inp.shape for inp in model_static.model.inputs]}")
# [batch, LOOKBACK, 1], [batch, HORIZON, 2], [batch, STORE_TYPE_DIM]

# Create dummy static features (e.g., store category one-hot or embedding)
X_static_train = np.random.rand(split, STORE_TYPE_DIM).astype(np.float32)
X_static_test  = np.random.rand(n - split, STORE_TYPE_DIM).astype(np.float32)

model_static.fit_model(
    X=[X_past_train, X_future_train, X_static_train],
    y=y_train,
    epochs=5,
    batch_size=32,
    early_stopping=False,
    verbose=0,
)
preds_static = model_static.predict([X_past_test, X_future_test, X_static_test])
print(f"    Prediction shape with static covariates: {preds_static.shape}")

print("\n" + "=" * 60)
print("Covariate example complete!")
print("  - future_features (temp, promo) demonstrated")
print("  - static_features (store type)  demonstrated")
print("=" * 60)
