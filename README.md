# Spline + LSTM Time Series Forecasting

**Focus:** ML technology validation with reproducible preprocessing → train/eval/infer runs.

## Overview

This project combines spline-based preprocessing with LSTM-family models for time-series forecasting.  
Current implementation supports univariate baseline flow (Phase 1–4) and Phase 5 PoC extensions (GRU compare + multivariate preprocessing path).

## Features

- **Spline preprocessing**: schema validation, missing interpolation, smoothing, train-fit scaling, windowing
- **Training runner**: one-command train/eval/infer with run-scoped artifacts
- **Model variants**: LSTM, GRU, Attention-LSTM
- **Evaluation metrics**: MAE, MSE, RMSE, robust MAPE, R2
- **PoC multivariate path**: covariate-enabled preprocessing arrays (`X_mv`, `y_mv`)

## Current Status (Phase Mapping)

| Phase | Status | Implemented scope |
|---|---|---|
| Phase 1 | ✅ | Preprocessing MVP (`src.preprocessing.pipeline`, `src.preprocessing.smoke`) |
| Phase 2 | ✅ | Trainer/core model flow and artifact persistence (`src.training.trainer`) |
| Phase 3 | ✅ | Unified CLI runner (`src.training.runner`) for train/eval/infer |
| Phase 4 | ✅ | E2E/ops scripts + smoke gate + run_id mismatch blocking (`scripts/run_e2e.sh`, `scripts/smoke_test.sh`) |
| Phase 5 (PoC) | ✅ (PoC 범위) | GRU comparison (`scripts/run_compare.sh`) + covariate/multivariate preprocessing contract |

## Project Structure

```text
spline-lstm/
├── src/
│   ├── data/                  # synthetic generator
│   ├── preprocessing/         # schema/spline/scale/window pipeline
│   ├── models/                # LSTM/GRU/Attention-LSTM
│   ├── training/              # trainer + unified runner + compare runner
│   └── utils/
├── scripts/                   # run_e2e / smoke_test / run_compare
├── docs/                      # phase docs + runbook + quickstart
├── runbook/                   # minimal operation README
└── requirements.txt
```

## Environment Notes

- Recommended Python: **3.10 ~ 3.11**
- TensorFlow dependency is constrained to `>=2.14,<2.17` in `requirements.txt` for runtime stability.
- If you run on Python builds linked with LibreSSL (often older macOS system Python), you may see `urllib3` `NotOpenSSLWarning`. In that case:
  - use `urllib3<2` (already constrained for older Python in `requirements.txt`), or
  - switch to an OpenSSL-backed Python runtime.

## Quick Start

For day-2 operator commands, see [`OPERATIONS_QUICKSTART.md`](OPERATIONS_QUICKSTART.md).
For detailed failure handling, run_id policy, and backend security defaults, see [`docs/RUNBOOK.md`](docs/RUNBOOK.md).
For the Phase 6 expansion roadmap (covariates, user-adjustable inputs, MCP/Skill, Tollama-compatible API, pilot stability), see [`docs/PHASE6_AGENT_ECOSYSTEM_PLAN.md`](docs/PHASE6_AGENT_ECOSYSTEM_PLAN.md).

### Phase 6 Backend Preview Endpoints (MVP)

- User-adjusted forecast input validation: `POST /api/v1/forecast/validate-inputs`
- User-adjusted forecast preview: `POST /api/v1/forecast/preview`
- User-adjusted forecast execute: `POST /api/v1/forecast/execute-adjusted`
- Covariate contract validator: `POST /api/v1/covariates/validate`
- Agent tool registry/invoke: `GET /api/v1/agent/tools`, `POST /api/v1/agent/tools:invoke`
- MCP capability descriptor: `GET /api/v1/mcp/capabilities`
- Pilot readiness endpoint (rollout + kill-switch view): `GET /api/v1/pilot/readiness`
- Agent tool registry/invoke: `GET /api/v1/agent/tools`, `POST /api/v1/agent/tools:invoke`
- MCP capability descriptor: `GET /api/v1/mcp/capabilities`
- Tollama-compatible adapter endpoints: `GET /api/tags`, `POST /api/generate`, `POST /api/chat`
- Reusable local skill package for agents: `skills/forecast-ops/SKILL.md`

```bash
# install deps
python3 -m pip install -r requirements.txt

# one-click E2E (preprocess -> train/eval/infer)
bash scripts/run_e2e.sh

# smoke gate
bash scripts/smoke_test.sh

# backend API skeleton for GUI (/api/v1)
# local dev (auth optional)
SPLINE_DEV_MODE=1 uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000

# production-like local run (auth required)
SPLINE_DEV_MODE=0 SPLINE_API_TOKEN=change-me \
  uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

# tests
python3 -m pytest tests/ -v
```

### Test warning policy (noise management)

To keep CI/local output readable without hiding real regressions, this repository applies **conservative warning filters** in `pytest.ini`:

- filtered only for known third-party noise from environment/library stack:
  - `pyparsing.exceptions.PyparsingDeprecationWarning` from `matplotlib` internals (filtered in `pytest.ini`)
- no global suppression for runtime SSL stack warnings (e.g., `urllib3` LibreSSL/OpenSSL notice), so environment-level signals remain visible
- no blanket ignore for `DeprecationWarning`/`UserWarning`
- project-origin warnings are still visible

For deep debugging (show everything), temporarily disable repo filters:

```bash
python3 -m pytest tests/ -v -o filterwarnings=default
```

For stricter investigation (fail on new warnings):

```bash
python3 -m pytest tests/ -v -W error
```

## Synthetic Data Generator

Generate synthetic CSV + metadata JSON:

```bash
# scenario S1
python3 -m src.data.synthetic_generator --scenario S1 --seed 42

# scenario S2 with covariates
python3 -m src.data.synthetic_generator \
  --scenario S2 \
  --n-samples 720 \
  --seed 123 \
  --covariates temp,promo,event

# helper script
bash scripts/gen_synthetic.sh S3 720 42 "temp,promo,event"
```

Scenarios:
- `S1`: smooth trend + seasonality
- `S2`: structural break (regime shift)
- `S3`: spikes + heteroskedastic noise

Outputs:
- `data/raw/synthetic/*.csv`
- `data/raw/synthetic/*.meta.json`

## Preprocessing (Phase 1 MVP)

```bash
# synthetic smoke input auto-generated
python3 -m src.preprocessing.smoke --run-id smoke-001

# user dataset (CSV/Parquet)
python3 -m src.preprocessing.smoke \
  --input data/raw/your_series.csv \
  --run-id exp-20260218-01 \
  --lookback 24 \
  --horizon 1 \
  --scaling standard
```

Saved artifacts:
- `artifacts/processed/{run_id}/processed.npz`
- `artifacts/processed/{run_id}/meta.json`
- `artifacts/processed/{run_id}/split_contract.json`
- `artifacts/models/{run_id}/preprocessor.pkl` (`schema_version: phase1.v2`)

## Phase 4 Operations

### One-click E2E

```bash
bash scripts/run_e2e.sh
# optional: RUN_ID=phase4-e2e-001 EPOCHS=2 bash scripts/run_e2e.sh
```

### Smoke gate

```bash
bash scripts/smoke_test.sh
```

Smoke pass checks:
- `artifacts/metrics/{run_id}.json` exists and contains `metrics.mae/mse/rmse/mape/mase/r2`
- `artifacts/reports/{run_id}.md` exists
- `artifacts/checkpoints/{run_id}/best.keras` exists
- `artifacts/models/{run_id}/preprocessor.pkl` exists
- validation report: `artifacts/reports/{run_id}_smoke_validation.md`

### run_id mismatch guard

`src.training.runner` blocks execution when run identifiers are inconsistent across:
- CLI `--run-id`
- `--processed-npz` path and sibling `meta.json`
- `--preprocessor-pkl` payload (`run_id`)

Run-id validation modes:
- default (backward-compatible): `--run-id-validation legacy`
- strict format enforcement: `--run-id-validation strict` (`YYYYMMDD_HHMMSS_<shortsha>`)

## Phase 5 PoC

### 1) GRU prototype + comparison runner

```bash
RUN_ID=phase5-poc-001 EPOCHS=3 bash scripts/run_compare.sh
```

Outputs:
- `artifacts/comparisons/<run_id>.json`
- `artifacts/comparisons/<run_id>.md`

### 2) Multivariate/covariate preprocessing path

`run_preprocessing_pipeline` supports `covariate_cols` in `PreprocessingConfig`.

When enabled, `processed.npz` additionally includes:
- `covariates_raw`
- `covariates_scaled` (fit on train split only; leakage-safe)
- `features_scaled`
- `X_mv`, `y_mv`
- `feature_names`, `target_indices` (artifact contract keys for multivariate path)

Python example:

```python
from src.preprocessing.pipeline import PreprocessingConfig, run_preprocessing_pipeline

run_preprocessing_pipeline(
    input_path="data/raw/phase5_covariate_input.csv",
    config=PreprocessingConfig(
        run_id="phase5-mv-001",
        lookback=24,
        horizon=1,
        covariate_cols=("temp", "event"),
        covariate_spec="configs/covariates/default.schema.json",  # optional but recommended
    ),
)
```

Covariate schema contract (`--covariate-spec` / `covariate_spec`) behavior:
- malformed schema (wrong field type/shape) fails fast before training
- `required=true` covariates missing from config/CLI fail fast
- declared dynamic covariates missing in dataset columns fail fast
- validated schema snapshot is persisted in artifacts (`preprocessor.pkl` `feature_schema`, runner metrics `covariate_schema`)

## Metric Notes

- **robust MAPE**: computed only on non-zero targets (`y_true != 0`); all-zero target case returns `inf`
- **R2**: coefficient of determination used in runner/trainer outputs
- **MASE**: emitted by `src.training.runner` metrics payload (computed via naive-difference MAE denominator; degenerate denominator returns `inf`)

## Operator Docs

- GUI/backend production cutover checklist: [`docs/GUI_PROD_CUTOVER_CHECKLIST.md`](docs/GUI_PROD_CUTOVER_CHECKLIST.md)
- Quick command map: [`OPERATIONS_QUICKSTART.md`](OPERATIONS_QUICKSTART.md)
- Detailed runbook: [`docs/RUNBOOK.md`](docs/RUNBOOK.md)
- GUI production hardening closeout: [`docs/GUI_PROD_HARDENING_CLOSEOUT.md`](docs/GUI_PROD_HARDENING_CLOSEOUT.md)
- Cutover/release checklist: [`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md)

## License

MIT
