# Spline-LSTM Run Report

- run_id: `gui-prod-hardening-gate-20260220-034431-smoke`
- backend: `tensorflow`
- model_type: `lstm`
- feature_mode: `univariate`

## Command
- `/Users/ychoi/spline-lstm/src/training/runner.py --run-id gui-prod-hardening-gate-20260220-034431-smoke --processed-npz artifacts/processed/gui-prod-hardening-gate-20260220-034431-smoke/processed.npz --preprocessor-pkl artifacts/models/gui-prod-hardening-gate-20260220-034431-smoke/preprocessor.pkl --epochs 1 --artifacts-dir artifacts`

## Config
- sequence_length: 24
- horizon: 1
- hidden_units: [64, 32]
- dropout: 0.2
- learning_rate: 0.001
- epochs: 1
- batch_size: 32
- normalize: True (minmax)
- seed: 42

## Evaluation Metrics
- MAE: 0.727795
- MSE: 0.651944
- RMSE: 0.807431
- MAPE: 96.1305
- MASE: 6.666136
- R2: -0.019966

## Baseline Comparison
- Naive(last) RMSE: 0.1349221169948578
- MA(24) RMSE: 1.0606614351272583

## Inference (latest test window)
- y_true_last: [-1.0761159658432007]
- y_pred_last: [-0.4631340205669403]

## Reproducibility Artifacts
- split indices: `artifacts/splits/gui-prod-hardening-gate-20260220-034431-smoke.json`
- config snapshot: `artifacts/configs/gui-prod-hardening-gate-20260220-034431-smoke.json`
- commit hash: `None` (source: `unavailable`)
- metadata(commit+seed): `artifacts/metadata/gui-prod-hardening-gate-20260220-034431-smoke.json`
- run metadata(v1): `artifacts/runs/gui-prod-hardening-gate-20260220-034431-smoke.meta.json`

## Artifacts
- checkpoints/best: `artifacts/checkpoints/gui-prod-hardening-gate-20260220-034431-smoke/best.keras`
- checkpoints/last: `artifacts/checkpoints/gui-prod-hardening-gate-20260220-034431-smoke/last.keras`
- predictions: `artifacts/predictions/gui-prod-hardening-gate-20260220-034431-smoke.csv`
- metrics: `artifacts/metrics/gui-prod-hardening-gate-20260220-034431-smoke.json`
- baselines: `artifacts/baselines/gui-prod-hardening-gate-20260220-034431-smoke.json`
- report: `artifacts/reports/gui-prod-hardening-gate-20260220-034431-smoke.md`
