# Spline-LSTM Run Report

- run_id: `phase4-review-b`
- backend: `tensorflow`

## Config
- sequence_length: 24
- horizon: 1
- hidden_units: [64, 32]
- dropout: 0.2
- learning_rate: 0.003
- epochs: 5
- batch_size: 16
- normalize: True (minmax)
- seed: 123

## Evaluation Metrics (LSTM)
- MAE: 0.098795
- MSE: 0.013269
- RMSE: 0.115190
- MAPE: 83.1862
- R2: 0.814252

## Baseline Comparison
- Naive(last) RMSE: 0.083772
- MA(3) RMSE: 0.144873
- LSTM RMSE improvement vs Naive(last): -37.50%
- LSTM RMSE improvement vs MA(3): 20.49%

## Inference (latest test window)
- y_true_last: [0.5358427166938782]
- y_pred_last: [0.41161075234413147]

## Reproducibility Artifacts
- split indices: `artifacts/splits/phase4-review-b.json`
- config snapshot: `artifacts/configs/phase4-review-b.json`
- commit hash: `None` (source: `unavailable`)
- metadata(commit+seed): `artifacts/metadata/phase4-review-b.json`

## Artifacts
- checkpoints/best: `checkpoints/phase4-review-b/best.keras`
- checkpoints/last: `checkpoints/phase4-review-b/last.keras`
- metrics: `artifacts/metrics/phase4-review-b.json`
- baselines: `artifacts/baselines/phase4-review-b.json`
- report: `artifacts/reports/phase4-review-b.md`
