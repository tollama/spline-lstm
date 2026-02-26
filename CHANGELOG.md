# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-02-27

### Changed
- **Backend decomposed into modules**: `backend/app/main.py` (1,283 lines) split into
  `config.py`, `models.py`, `store.py`, `executor.py`, `utils.py`, and `routes/` package
  for better maintainability and contributor onboarding.
- **Documentation reorganized**: 118 internal development notes moved to `docs/internal/`;
  `docs/` now shows only user-facing guides.
- **CI matrix expanded**: Tests now run on Python 3.10 and 3.11 (previously only 3.10).
- **Test coverage reporting**: Added `pytest-cov` with coverage thresholds and CI reporting.
- **Repository hygiene**: Removed stray `tmp.keras`, untracked regenerable synthetic data,
  added `*.keras`/`*.h5` to `.gitignore`.
- **PyPI publish workflow**: Added GitHub Actions workflow for automated PyPI publishing on
  tag push using trusted publishing (OIDC).

### Fixed
- **`cross_validate()`**: Model weights were not reset between folds, causing each fold to
  inherit accumulated training from all previous folds.  The model is now rebuilt from
  scratch via `model.build()` at the start of every fold, making CV metrics statistically
  meaningful.
- **`AttentionLSTMModel`**: `static_features` and `future_features` covariates were silently
  ignored in `build()`.  The model now wires all three input branches (past, future, static)
  identically to `LSTMModel`.
- **`AttentionLSTMModel` serialisation**: The `Lambda` layer used for attention context
  summation prevented `model.save()` / `model.load()` from working correctly.  Replaced
  with a serialisable `_ReduceSum` Keras layer decorated with
  `@register_keras_serializable`.
- **`LSTMModel.load()`**: Loading with `compile=False` and re-compiling avoids
  optimizer / metric deserialization errors across TensorFlow versions (≥ 2.14).
- **`extract_features()`**: Calling this method on a fitted `SplinePreprocessor` overwrote
  the internally stored spline.  A temporary instance is now used so the original fitted
  state is preserved.
- **`BidirectionalLSTMModel` / `GRUModel`**: Removed copy-pasted `build()` bodies;
  subclasses now inherit the single `build()` implementation from `LSTMModel` and only
  override `_build_lstm_stack`.

### Added
- **`Trainer.train(denormalize_metrics=False)`**: New opt-in parameter.  When `True` and
  `normalize=True`, evaluation metrics (MAE, RMSE, etc.) are computed in the original data
  units rather than the normalised space.  Results dict gains `y_test_original_scale` and
  `y_pred_original_scale` keys.
- **`SplinePreprocessor` docstring**: `smoothing_factor` now has a full parameter guide
  explaining the `s = factor × n` mapping and data-size dependency.
- **`GRUModel` and `AttentionLSTMModel` exported** from the top-level `src` package
  (`from src import GRUModel, AttentionLSTMModel`).
- **Regression test suite** `tests/test_attention_lstm_fixes.py` covering: covariate
  wiring, save/reload round-trip, and denormalised metric correctness.
- **`mape_zero_safe`** metric added to `Trainer.compute_metrics()` output.

## [0.1.0] - 2025-02-25

### Added
- Initial public release
- Spline-based preprocessing for time-series data
- LSTM neural network forecasting model
- Support for multiple input features and covariates
- Cross-validation support for model evaluation
- FastAPI backend for serving predictions
- React-based UI for interactive forecasting
- Comprehensive test suite (106 tests)
- Smoke test gate for end-to-end validation
- Configurable training pipelines via YAML
- Model checkpointing and artifact management

### Features
- **Spline Preprocessing**: Smooth time-series interpolation and noise reduction
- **LSTM Architecture**: Flexible recurrent neural network for sequence modeling
- **Multi-horizon Forecasting**: Configurable prediction horizons
- **Covariate Support**: Include external variables in forecasts
- **Backend API**: RESTful endpoints for training and inference
- **Web UI**: Interactive dashboard for model management

[0.1.0]: https://github.com/ychoi-atop/spline-lstm/releases/tag/v0.1.0