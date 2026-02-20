# Spline-LSTM Run Report

- run_id: `repro_a`
- backend: `tensorflow`

## Config
- sequence_length: 24
- horizon: 1
- hidden_units: [64, 32]
- dropout: 0.2
- learning_rate: 0.001
- epochs: 1
- batch_size: 32
- normalize: True (minmax)

## Evaluation Metrics
- MAE: 0.180970
- MSE: 0.047514
- RMSE: 0.217977
- MAPE: 131.9968
- R2: 0.332764

## Inference (latest test window)
- y_true_last: [0.5375630855560303]
- y_pred_last: [0.32236504554748535]

## Artifacts
- checkpoints/best: `artifacts/checkpoints/repro_a/best.keras`
- checkpoints/last: `artifacts/checkpoints/repro_a/last.keras`
- metrics: `artifacts/metrics/repro_a.json`
- report: `artifacts/reports/repro_a.md`
