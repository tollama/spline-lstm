# Spline-LSTM Run Report

- run_id: `phase2_e2e_from_prep`
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
- MAE: 0.061128
- MSE: 0.004377
- RMSE: 0.066157
- MAPE: 79.2539
- R2: -1.531891

## Inference (latest test window)
- y_true_last: [0.16439537703990936]
- y_pred_last: [0.09077096730470657]

## Artifacts
- checkpoints/best: `artifacts/checkpoints/phase2_e2e_from_prep/best.keras`
- checkpoints/last: `artifacts/checkpoints/phase2_e2e_from_prep/last.keras`
- metrics: `artifacts/metrics/phase2_e2e_from_prep.json`
- report: `artifacts/reports/phase2_e2e_from_prep.md`
