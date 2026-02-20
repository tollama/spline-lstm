# Spline-LSTM Run Report

- run_id: `phase4-smoke-proof`
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
- seed: 42

## Evaluation Metrics (LSTM)
- MAE: 0.077517
- MSE: 0.007896
- RMSE: 0.088860
- MAPE: 114.8244
- R2: -6.619345

## Baseline Comparison
- Naive(last) RMSE: 0.033773
- MA(3) RMSE: 0.038222
- LSTM RMSE improvement vs Naive(last): -163.11%
- LSTM RMSE improvement vs MA(3): -132.48%

## Inference (latest test window)
- y_true_last: [0.13222353160381317]
- y_pred_last: [0.10204919427633286]

## Reproducibility Artifacts
- split indices: `artifacts/splits/phase4-smoke-proof.json`
- config snapshot: `artifacts/configs/phase4-smoke-proof.json`
- commit hash: `None` (source: `unavailable`)
- metadata(commit+seed): `artifacts/metadata/phase4-smoke-proof.json`

## Artifacts
- checkpoints/best: `artifacts/checkpoints/phase4-smoke-proof/best.keras`
- checkpoints/last: `artifacts/checkpoints/phase4-smoke-proof/last.keras`
- metrics: `artifacts/metrics/phase4-smoke-proof.json`
- baselines: `artifacts/baselines/phase4-smoke-proof.json`
- report: `artifacts/reports/phase4-smoke-proof.md`
