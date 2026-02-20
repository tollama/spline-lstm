# Spline-LSTM Run Report

- run_id: `alias-quick-001`
- backend: `tensorflow`
- model_type: `lstm`
- feature_mode: `univariate`

## Command
- `/Users/ychoi/spline-lstm/src/training/runner.py --run-id alias-quick-001 --processed-npz artifacts/processed/alias-quick-001/processed.npz --preprocessor-pkl artifacts/models/alias-quick-001/preprocessor.pkl --epochs 1 --artifacts-dir artifacts`

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
- MAE: 0.705438
- MSE: 0.604837
- RMSE: 0.777713
- MAPE: 148.7897
- MASE: 6.949030
- R2: 0.007690

## Baseline Comparison
- Naive(last) RMSE: 0.1294897049665451
- MA(24) RMSE: 1.019654393196106

## Inference (latest test window)
- y_true_last: [-1.0907435417175293]
- y_pred_last: [-0.4497118592262268]

## Reproducibility Artifacts
- split indices: `artifacts/splits/alias-quick-001.json`
- config snapshot: `artifacts/configs/alias-quick-001.json`
- commit hash: `None` (source: `unavailable`)
- metadata(commit+seed): `artifacts/metadata/alias-quick-001.json`
- run metadata(v1): `artifacts/runs/alias-quick-001.meta.json`

## Artifacts
- checkpoints/best: `artifacts/checkpoints/alias-quick-001/best.keras`
- checkpoints/last: `artifacts/checkpoints/alias-quick-001/last.keras`
- predictions: `artifacts/predictions/alias-quick-001.csv`
- metrics: `artifacts/metrics/alias-quick-001.json`
- baselines: `artifacts/baselines/alias-quick-001.json`
- report: `artifacts/reports/alias-quick-001.md`
