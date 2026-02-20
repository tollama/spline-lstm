# Spline-LSTM Run Report

- run_id: `phase3_smoke`
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
- MAE: 0.189584
- MSE: 0.048764
- RMSE: 0.220825
- MAPE: 101.2860
- R2: 0.315216

## Baseline Comparison
- Naive(last) RMSE: 0.048759
- MA(3) RMSE: 0.072766
- LSTM RMSE improvement vs Naive(last): -352.89%
- LSTM RMSE improvement vs MA(3): -203.47%

## Inference (latest test window)
- y_true_last: [0.5375630855560303]
- y_pred_last: [0.2416229248046875]

## Reproducibility Artifacts
- split indices: `artifacts/splits/phase3_smoke.json`
- config snapshot: `artifacts/configs/phase3_smoke.json`
- metadata(commit+seed): `artifacts/metadata/phase3_smoke.json`

## Artifacts
- checkpoints/best: `artifacts/checkpoints/phase3_smoke/best.keras`
- checkpoints/last: `artifacts/checkpoints/phase3_smoke/last.keras`
- metrics: `artifacts/metrics/phase3_smoke.json`
- baselines: `artifacts/baselines/phase3_smoke.json`
- report: `artifacts/reports/phase3_smoke.md`
