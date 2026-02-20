# Spline-LSTM Run Report

- run_id: `gui-complete-closeout-20260220-20260220-033720-smoke`
- backend: `tensorflow`
- model_type: `lstm`
- feature_mode: `univariate`

## Command
- `/Users/ychoi/spline-lstm/src/training/runner.py --run-id gui-complete-closeout-20260220-20260220-033720-smoke --processed-npz artifacts/processed/gui-complete-closeout-20260220-20260220-033720-smoke/processed.npz --preprocessor-pkl artifacts/models/gui-complete-closeout-20260220-20260220-033720-smoke/preprocessor.pkl --epochs 1 --artifacts-dir artifacts`

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
- MAE: 0.694983
- MSE: 0.611969
- RMSE: 0.782284
- MAPE: 108.1844
- MASE: 6.446465
- R2: 0.001902

## Baseline Comparison
- Naive(last) RMSE: 0.1282995194196701
- MA(24) RMSE: 1.0132609605789185

## Inference (latest test window)
- y_true_last: [-1.0202330350875854]
- y_pred_last: [-0.45640841126441956]

## Reproducibility Artifacts
- split indices: `artifacts/splits/gui-complete-closeout-20260220-20260220-033720-smoke.json`
- config snapshot: `artifacts/configs/gui-complete-closeout-20260220-20260220-033720-smoke.json`
- commit hash: `None` (source: `unavailable`)
- metadata(commit+seed): `artifacts/metadata/gui-complete-closeout-20260220-20260220-033720-smoke.json`
- run metadata(v1): `artifacts/runs/gui-complete-closeout-20260220-20260220-033720-smoke.meta.json`

## Artifacts
- checkpoints/best: `artifacts/checkpoints/gui-complete-closeout-20260220-20260220-033720-smoke/best.keras`
- checkpoints/last: `artifacts/checkpoints/gui-complete-closeout-20260220-20260220-033720-smoke/last.keras`
- predictions: `artifacts/predictions/gui-complete-closeout-20260220-20260220-033720-smoke.csv`
- metrics: `artifacts/metrics/gui-complete-closeout-20260220-20260220-033720-smoke.json`
- baselines: `artifacts/baselines/gui-complete-closeout-20260220-20260220-033720-smoke.json`
- report: `artifacts/reports/gui-complete-closeout-20260220-20260220-033720-smoke.md`
