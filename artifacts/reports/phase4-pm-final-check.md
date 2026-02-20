# Spline-LSTM Run Report

- run_id: `phase4-pm-final-check`
- backend: `tensorflow`

## Config
- sequence_length: 24
- horizon: 1
- hidden_units: [64, 32]
- dropout: 0.2
- learning_rate: 0.001
- epochs: 3
- batch_size: 16
- normalize: True (minmax)
- seed: 123

## Evaluation Metrics (LSTM)
- MAE: 0.216438
- MSE: 0.062894
- RMSE: 0.250787
- MAPE: 198.1788
- R2: 0.119550

## Baseline Comparison
- Naive(last) RMSE: 0.083772
- MA(3) RMSE: 0.144873
- LSTM RMSE improvement vs Naive(last): -199.37%
- LSTM RMSE improvement vs MA(3): -73.11%

## Inference (latest test window)
- y_true_last: [0.5358427166938782]
- y_pred_last: [0.32184919714927673]

## Reproducibility Artifacts
- split indices: `artifacts/splits/phase4-pm-final-check.json`
- config snapshot: `artifacts/configs/phase4-pm-final-check.json`
- commit hash: `None` (source: `unavailable`)
- metadata(commit+seed): `artifacts/metadata/phase4-pm-final-check.json`

## Artifacts
- checkpoints/best: `checkpoints/phase4-pm-final-check/best.keras`
- checkpoints/last: `checkpoints/phase4-pm-final-check/last.keras`
- metrics: `artifacts/metrics/phase4-pm-final-check.json`
- baselines: `artifacts/baselines/phase4-pm-final-check.json`
- report: `artifacts/reports/phase4-pm-final-check.md`
