# Spline-LSTM Run Report

- run_id: `phase4-e2e-smoke`
- backend: `tensorflow`

## Config
- sequence_length: 24
- horizon: 1
- hidden_units: [64, 32]
- dropout: 0.2
- learning_rate: 0.001
- epochs: 5
- batch_size: 16
- normalize: True (minmax)
- seed: 123

## Evaluation Metrics (LSTM)
- MAE: 0.175183
- MSE: 0.042394
- RMSE: 0.205897
- MAPE: 156.7600
- R2: 0.406536

## Baseline Comparison
- Naive(last) RMSE: 0.083772
- MA(3) RMSE: 0.144873
- LSTM RMSE improvement vs Naive(last): -145.78%
- LSTM RMSE improvement vs MA(3): -42.12%

## Inference (latest test window)
- y_true_last: [0.5358427166938782]
- y_pred_last: [0.31548982858657837]

## Reproducibility Artifacts
- split indices: `artifacts/splits/phase4-e2e-smoke.json`
- config snapshot: `artifacts/configs/phase4-e2e-smoke.json`
- commit hash: `None` (source: `unavailable`)
- metadata(commit+seed): `artifacts/metadata/phase4-e2e-smoke.json`

## Artifacts
- checkpoints/best: `checkpoints/phase4-e2e-smoke/best.keras`
- checkpoints/last: `checkpoints/phase4-e2e-smoke/last.keras`
- metrics: `artifacts/metrics/phase4-e2e-smoke.json`
- baselines: `artifacts/baselines/phase4-e2e-smoke.json`
- report: `artifacts/reports/phase4-e2e-smoke.md`
