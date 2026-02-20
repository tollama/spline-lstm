# Spline-LSTM Run Report

- run_id: `gatec-final2-check`
- backend: `tensorflow`

## Config
- sequence_length: 24
- horizon: 1
- hidden_units: [64, 32]
- dropout: 0.2
- learning_rate: 0.003
- epochs: 20
- batch_size: 16
- normalize: True (minmax)
- seed: 123

## Evaluation Metrics (LSTM)
- MAE: 0.076566
- MSE: 0.008163
- RMSE: 0.090352
- MAPE: 61.2138
- R2: 0.885720

## Baseline Comparison
- Naive(last) RMSE: 0.083772
- MA(3) RMSE: 0.144873
- LSTM RMSE improvement vs Naive(last): -7.85%
- LSTM RMSE improvement vs MA(3): 37.63%

## Inference (latest test window)
- y_true_last: [0.5358427166938782]
- y_pred_last: [0.44696611166000366]

## Reproducibility Artifacts
- split indices: `artifacts/splits/gatec-final2-check.json`
- config snapshot: `artifacts/configs/gatec-final2-check.json`
- commit hash: `None` (source: `unavailable`)
- metadata(commit+seed): `artifacts/metadata/gatec-final2-check.json`

## Artifacts
- checkpoints/best: `checkpoints/gatec-final2-check/best.keras`
- checkpoints/last: `checkpoints/gatec-final2-check/last.keras`
- metrics: `artifacts/metrics/gatec-final2-check.json`
- baselines: `artifacts/baselines/gatec-final2-check.json`
- report: `artifacts/reports/gatec-final2-check.md`
