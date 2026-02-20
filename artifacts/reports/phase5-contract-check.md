# Spline-LSTM Run Report

- run_id: `phase5-contract-check`
- backend: `tensorflow`
- model_type: `lstm`
- feature_mode: `multivariate`

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

## Evaluation Metrics
- MAE: 0.189584
- MSE: 0.048764
- RMSE: 0.220825
- MAPE: 101.2860
- R2: 0.315216

## Baseline Comparison
- Naive(last) RMSE: 0.04875864461064339
- MA(3) RMSE: 0.07276590168476105

## Inference (latest test window)
- y_true_last: [0.5375630855560303]
- y_pred_last: [0.2416229099035263]

## Reproducibility Artifacts
- split indices: `artifacts/splits/phase5-contract-check.json`
- config snapshot: `artifacts/configs/phase5-contract-check.json`
- commit hash: `None` (source: `unavailable`)
- metadata(commit+seed): `artifacts/metadata/phase5-contract-check.json`

## Artifacts
- checkpoints/best: `artifacts/checkpoints/phase5-contract-check/best.keras`
- checkpoints/last: `artifacts/checkpoints/phase5-contract-check/last.keras`
- metrics: `artifacts/metrics/phase5-contract-check.json`
- baselines: `artifacts/baselines/phase5-contract-check.json`
- report: `artifacts/reports/phase5-contract-check.md`
