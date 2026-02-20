# Spline-LSTM Run Report

- run_id: `alias-smoke-001`
- backend: `tensorflow`
- model_type: `lstm`
- feature_mode: `univariate`

## Command
- `/Users/ychoi/spline-lstm/src/training/runner.py --run-id alias-smoke-001 --processed-npz artifacts/processed/alias-smoke-001/processed.npz --preprocessor-pkl artifacts/models/alias-smoke-001/preprocessor.pkl --epochs 1 --artifacts-dir artifacts`

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
- MAE: 0.737027
- MSE: 0.663548
- RMSE: 0.814584
- MAPE: 413.4229
- MASE: 7.188196
- R2: 0.008547

## Baseline Comparison
- Naive(last) RMSE: 0.12397434562444687
- MA(24) RMSE: 1.060731053352356

## Inference (latest test window)
- y_true_last: [-1.1874074935913086]
- y_pred_last: [-0.45536521077156067]

## Reproducibility Artifacts
- split indices: `artifacts/splits/alias-smoke-001.json`
- config snapshot: `artifacts/configs/alias-smoke-001.json`
- commit hash: `None` (source: `unavailable`)
- metadata(commit+seed): `artifacts/metadata/alias-smoke-001.json`
- run metadata(v1): `artifacts/runs/alias-smoke-001.meta.json`

## Artifacts
- checkpoints/best: `artifacts/checkpoints/alias-smoke-001/best.keras`
- checkpoints/last: `artifacts/checkpoints/alias-smoke-001/last.keras`
- predictions: `artifacts/predictions/alias-smoke-001.csv`
- metrics: `artifacts/metrics/alias-smoke-001.json`
- baselines: `artifacts/baselines/alias-smoke-001.json`
- report: `artifacts/reports/alias-smoke-001.md`
