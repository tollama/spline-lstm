# Spline-LSTM Run Report

- run_id: `repro_b`
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
- MAE: 0.192905
- MSE: 0.053349
- RMSE: 0.230974
- MAPE: 139.8519
- R2: 0.250825

## Inference (latest test window)
- y_true_last: [0.5375630855560303]
- y_pred_last: [0.31935787200927734]

## Artifacts
- checkpoints/best: `artifacts/checkpoints/repro_b/best.keras`
- checkpoints/last: `artifacts/checkpoints/repro_b/last.keras`
- metrics: `artifacts/metrics/repro_b.json`
- report: `artifacts/reports/repro_b.md`
