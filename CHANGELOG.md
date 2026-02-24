# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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