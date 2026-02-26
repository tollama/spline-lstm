# Spline-LSTM Time Series Forecasting

[![CI](https://github.com/ychoi-atop/spline-lstm/actions/workflows/ci.yml/badge.svg)](https://github.com/ychoi-atop/spline-lstm/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Spline-LSTM** is a comprehensive, production-ready machine learning project designed for advanced time-series forecasting. By combining robust spline-based preprocessing with modern LSTM-family neural networks, this project aims to provide highly accurate, scalable, and reproducible forecasting models.

## Introduction & Motivation

Time-series forecasting often struggles with noisy data, missing values, and the integration of complex external covariates. Spline-LSTM addresses these challenges by offering a unified pipeline that handles end-to-end forecasting:
*   **Spline Preprocessing:** Automatically handles missing data interpolation and noise smoothing before the model sees the data.
*   **Deep Learning Architecture:** Utilizes TensorFlow-backed LSTMs and GRUs to capture long-term temporal dependencies.
*   **Covariate Support:** Integrates static (e.g., store type) and future-known covariates (e.g., promotions, holidays) directly into the forecasting architecture.

This project was built to validate ML technologies in a reproducible manner, offering a complete flow from data preprocessing down to model training, evaluation, and inference.

---

## Core Features

- **Advanced Preprocessing Pipeline**: Built-in schema validation, spline interpolation, smoothing, train-fit scaling, and windowing.
- **Multi-Input Modeling**: First-class support for `X_past`, `X_future`, and `X_static` covariates, enabling rich multivariate forecasting.
- **Robust Training Runner**: A single unified CLI command (`src.training.runner`) to execute train, evaluate, and infer jobs with strict run-scoped artifact management.
- **Time-Series Cross-Validation**: Comprehensive rolling-window CV support to validate model stability across different time periods.
- **Production-Ready Gates**: Pre-configured E2E operational scripts, smoke test gates, and built-in run-ID mismatch guards.
- **Agent/LLM Ecosystem (Preview)**: Includes backend endpoints tailored for Tollama compatibility and MCP capabilities.

---

## Quick Start

### Installation

Spline-LSTM requires **Python 3.10 ~ 3.11** and **TensorFlow >= 2.14, < 2.17**.

We recommend installing the project in a virtual environment. Use the new standard `pyproject.toml` installation flow:

```bash
# Clone the repository
git clone https://github.com/ychoi-atop/spline-lstm.git
cd spline-lstm

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install the package with backend and dev dependencies
pip install -e ".[backend,dev]"
```

### Basic Usage

You can run the end-to-end pipeline (Preprocessing → Training → Evaluation) out of the box using our provided synthetic data generator and smoke test scripts:

```bash
# 1. Generate synthetic benchmarking data
python3 -m src.data.synthetic_generator --scenario S2 --n-samples 720 --seed 123 --covariates temp,promo,event

# 2. Run the One-Click End-to-End full pipeline with the generated CSV
INPUT_PATH=data/raw/synthetic/synthetic_S2_n720_seed123.csv bash scripts/run_e2e.sh

# 3. Fast Smoke Gate Validation
bash scripts/smoke_test.sh
```

If `INPUT_PATH` is omitted, `scripts/run_e2e.sh` automatically creates and uses a built-in smoke input dataset.

### Running the Backend API

To launch the FastAPI backend (with endpoints for forecasting and agent interactions):

```bash
# Local development mode (auth optional)
SPLINE_DEV_MODE=1 uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

---

## Project Architecture

```text
spline-lstm/
├── src/
│   ├── data/                  # Synthetic time-series generation
│   ├── preprocessing/         # Core spline, scaling, and windowing logic
│   ├── models/                # TensorFlow LSTM/GRU implementations
│   ├── training/              # Model compilation, training, and artifact persistence
│   └── utils/                 # Reproducibility and run ID utilities
├── backend/                   # FastAPI service for model inference and agent tools
├── scripts/                   # Operational bash scripts (e2e, smoke tests, compare)
├── docs/                      # Detailed operator runbooks and phase documentation
└── ui/                        # React-based graphical interface for forecasting preview
```

---

## Current Development Status

The project focuses on iterative phase-based delivery. Currently, **Phases 1 through 6** are fully integrated.

| Phase | Status | Scope |
|---|---|---|
| **Phase 1-3** | ✅ | Spline Preprocessing MVP, Core Trainer Logic, Unified CLI Runner |
| **Phase 4** | ✅ | E2E/Ops scripts, Smoke testing gates, Run-ID mismatch blocking |
| **Phase 5** | ✅ | GRU comparison runners + Multivariate Preprocessing (`X_mv`, `y_mv`) |
| **Phase 6** | ✅ | Static/Future Covariates, Cross-Validation, Strict TF Backend |

---

## Advanced Documentation & Operations

For production deployments, day-2 operations, and specific feature details, please refer to the following documentation:

- **Quick Operator Commands:** [`OPERATIONS_QUICKSTART.md`](OPERATIONS_QUICKSTART.md)
- **Architecture & Technology Overview:** [`docs/architecture.md`](docs/architecture.md)
- **Detailed Runbook (Failure Handling, Security):** [`docs/RUNBOOK.md`](docs/RUNBOOK.md)
- **GUI Production Cutover:** [`docs/internal/GUI_PROD_CUTOVER_CHECKLIST.md`](docs/internal/GUI_PROD_CUTOVER_CHECKLIST.md)
- **Phase 6 Details & Agent Ecosystem:** [`docs/internal/PHASE6_AGENT_ECOSYSTEM_PLAN.md`](docs/internal/PHASE6_AGENT_ECOSYSTEM_PLAN.md)

### Test Warning Policy
To keep CI/local output readable, conservative warning filters are applied in `pytest.ini`. If you need to see deep environment warnings (like SSL or Matplotlib internals), temporarily disable the filters:
```bash
python3 -m pytest tests/ -v -o filterwarnings=default
```

---

## License

This project is licensed under the [MIT License](LICENSE).
