# Spline-LSTM Run Report

- run_id: `phase3-smoke-fixpass`
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
- split indices: `artifacts/splits/phase3-smoke-fixpass.json`
- config snapshot: `artifacts/configs/phase3-smoke-fixpass.json`
- commit hash: `None` (source: `unavailable`)
- metadata(commit+seed): `artifacts/metadata/phase3-smoke-fixpass.json`

## Artifacts
- checkpoints/best: `checkpoints/phase3-smoke-fixpass/best.keras`
- checkpoints/last: `checkpoints/phase3-smoke-fixpass/last.keras`
- metrics: `artifacts/metrics/phase3-smoke-fixpass.json`
- baselines: `artifacts/baselines/phase3-smoke-fixpass.json`
- report: `artifacts/reports/phase3-smoke-fixpass.md`
