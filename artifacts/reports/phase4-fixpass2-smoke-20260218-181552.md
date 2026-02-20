# Spline-LSTM Run Report

- run_id: `phase4-fixpass2-smoke-20260218-181552`
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
- MAE: 0.090546
- MSE: 0.009762
- RMSE: 0.098805
- MAPE: 141.9953
- R2: -7.093660

## Baseline Comparison
- Naive(last) RMSE: 0.026253
- MA(3) RMSE: 0.034267
- LSTM RMSE improvement vs Naive(last): -276.36%
- LSTM RMSE improvement vs MA(3): -188.34%

## Inference (latest test window)
- y_true_last: [0.13949176669120789]
- y_pred_last: [0.10099268704652786]

## Reproducibility Artifacts
- split indices: `artifacts/splits/phase4-fixpass2-smoke-20260218-181552.json`
- config snapshot: `artifacts/configs/phase4-fixpass2-smoke-20260218-181552.json`
- commit hash: `None` (source: `unavailable`)
- metadata(commit+seed): `artifacts/metadata/phase4-fixpass2-smoke-20260218-181552.json`

## Artifacts
- checkpoints/best: `artifacts/checkpoints/phase4-fixpass2-smoke-20260218-181552/best.keras`
- checkpoints/last: `artifacts/checkpoints/phase4-fixpass2-smoke-20260218-181552/last.keras`
- metrics: `artifacts/metrics/phase4-fixpass2-smoke-20260218-181552.json`
- baselines: `artifacts/baselines/phase4-fixpass2-smoke-20260218-181552.json`
- report: `artifacts/reports/phase4-fixpass2-smoke-20260218-181552.md`
