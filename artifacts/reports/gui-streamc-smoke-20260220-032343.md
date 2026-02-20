# Spline-LSTM Run Report

- run_id: `gui-streamc-smoke-20260220-032343`
- backend: `tensorflow`
- model_type: `lstm`
- feature_mode: `univariate`

## Command
- `/Users/ychoi/spline-lstm/src/training/runner.py --run-id gui-streamc-smoke-20260220-032343 --processed-npz artifacts/processed/gui-streamc-smoke-20260220-032343/processed.npz --preprocessor-pkl artifacts/models/gui-streamc-smoke-20260220-032343/preprocessor.pkl --epochs 1 --artifacts-dir artifacts`

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
- MAE: 0.796165
- MSE: 0.771652
- RMSE: 0.878437
- MAPE: 118.7328
- MASE: 5.912414
- R2: -0.011380

## Baseline Comparison
- Naive(last) RMSE: 0.15767835080623627
- MA(24) RMSE: 1.1151552200317383

## Inference (latest test window)
- y_true_last: [-1.1108009815216064]
- y_pred_last: [-0.48716479539871216]

## Reproducibility Artifacts
- split indices: `artifacts/splits/gui-streamc-smoke-20260220-032343.json`
- config snapshot: `artifacts/configs/gui-streamc-smoke-20260220-032343.json`
- commit hash: `None` (source: `unavailable`)
- metadata(commit+seed): `artifacts/metadata/gui-streamc-smoke-20260220-032343.json`
- run metadata(v1): `artifacts/runs/gui-streamc-smoke-20260220-032343.meta.json`

## Artifacts
- checkpoints/best: `artifacts/checkpoints/gui-streamc-smoke-20260220-032343/best.keras`
- checkpoints/last: `artifacts/checkpoints/gui-streamc-smoke-20260220-032343/last.keras`
- predictions: `artifacts/predictions/gui-streamc-smoke-20260220-032343.csv`
- metrics: `artifacts/metrics/gui-streamc-smoke-20260220-032343.json`
- baselines: `artifacts/baselines/gui-streamc-smoke-20260220-032343.json`
- report: `artifacts/reports/gui-streamc-smoke-20260220-032343.md`
