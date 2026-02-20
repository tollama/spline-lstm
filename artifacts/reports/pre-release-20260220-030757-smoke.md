# Spline-LSTM Run Report

- run_id: `pre-release-20260220-030757-smoke`
- backend: `tensorflow`
- model_type: `lstm`
- feature_mode: `univariate`

## Command
- `/Users/ychoi/spline-lstm/src/training/runner.py --run-id pre-release-20260220-030757-smoke --processed-npz artifacts/processed/pre-release-20260220-030757-smoke/processed.npz --preprocessor-pkl artifacts/models/pre-release-20260220-030757-smoke/preprocessor.pkl --epochs 1 --artifacts-dir artifacts`

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
- MAE: 0.749054
- MSE: 0.682680
- RMSE: 0.826244
- MAPE: 307.6292
- MASE: 6.274662
- R2: -0.028938

## Baseline Comparison
- Naive(last) RMSE: 0.14431889355182648
- MA(24) RMSE: 1.0728263854980469

## Inference (latest test window)
- y_true_last: [-1.1701762676239014]
- y_pred_last: [-0.45804035663604736]

## Reproducibility Artifacts
- split indices: `artifacts/splits/pre-release-20260220-030757-smoke.json`
- config snapshot: `artifacts/configs/pre-release-20260220-030757-smoke.json`
- commit hash: `None` (source: `unavailable`)
- metadata(commit+seed): `artifacts/metadata/pre-release-20260220-030757-smoke.json`
- run metadata(v1): `artifacts/runs/pre-release-20260220-030757-smoke.meta.json`

## Artifacts
- checkpoints/best: `artifacts/checkpoints/pre-release-20260220-030757-smoke/best.keras`
- checkpoints/last: `artifacts/checkpoints/pre-release-20260220-030757-smoke/last.keras`
- predictions: `artifacts/predictions/pre-release-20260220-030757-smoke.csv`
- metrics: `artifacts/metrics/pre-release-20260220-030757-smoke.json`
- baselines: `artifacts/baselines/pre-release-20260220-030757-smoke.json`
- report: `artifacts/reports/pre-release-20260220-030757-smoke.md`
