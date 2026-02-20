# Spline-LSTM Run Report

- run_id: `pre-release-20260220-031236-smoke`
- backend: `tensorflow`
- model_type: `lstm`
- feature_mode: `univariate`

## Command
- `/Users/ychoi/spline-lstm/src/training/runner.py --run-id pre-release-20260220-031236-smoke --processed-npz artifacts/processed/pre-release-20260220-031236-smoke/processed.npz --preprocessor-pkl artifacts/models/pre-release-20260220-031236-smoke/preprocessor.pkl --epochs 1 --artifacts-dir artifacts`

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
- MAE: 0.727364
- MSE: 0.648125
- RMSE: 0.805062
- MAPE: 209.5735
- MASE: 5.867459
- R2: 0.057472

## Baseline Comparison
- Naive(last) RMSE: 0.13810580968856812
- MA(24) RMSE: 1.0785589218139648

## Inference (latest test window)
- y_true_last: [-1.1240622997283936]
- y_pred_last: [-0.45105066895484924]

## Reproducibility Artifacts
- split indices: `artifacts/splits/pre-release-20260220-031236-smoke.json`
- config snapshot: `artifacts/configs/pre-release-20260220-031236-smoke.json`
- commit hash: `None` (source: `unavailable`)
- metadata(commit+seed): `artifacts/metadata/pre-release-20260220-031236-smoke.json`
- run metadata(v1): `artifacts/runs/pre-release-20260220-031236-smoke.meta.json`

## Artifacts
- checkpoints/best: `artifacts/checkpoints/pre-release-20260220-031236-smoke/best.keras`
- checkpoints/last: `artifacts/checkpoints/pre-release-20260220-031236-smoke/last.keras`
- predictions: `artifacts/predictions/pre-release-20260220-031236-smoke.csv`
- metrics: `artifacts/metrics/pre-release-20260220-031236-smoke.json`
- baselines: `artifacts/baselines/pre-release-20260220-031236-smoke.json`
- report: `artifacts/reports/pre-release-20260220-031236-smoke.md`
