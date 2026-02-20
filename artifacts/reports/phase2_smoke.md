# Spline-LSTM Run Report

- run_id: `phase2_smoke`
- backend: `tensorflow`

## Config
- sequence_length: 24
- horizon: 1
- hidden_units: [64, 32]
- dropout: 0.2
- learning_rate: 0.001
- epochs: 2
- batch_size: 32
- normalize: True (minmax)

## Evaluation Metrics
- MAE: 0.158294
- MSE: 0.036780
- RMSE: 0.191782
- MAPE: 113.1259
- R2: 0.483498

## Inference (latest test window)
- y_true_last: [0.5375630855560303]
- y_pred_last: [0.3277146518230438]

## Artifacts
- checkpoints/best: `artifacts/checkpoints/phase2_smoke/best.keras`
- checkpoints/last: `artifacts/checkpoints/phase2_smoke/last.keras`
- metrics: `artifacts/metrics/phase2_smoke.json`
- report: `artifacts/reports/phase2_smoke.md`
