# OPERATIONS QUICKSTART

Minimal day-2 command map for operators.

## Command map

- **quick gate (fast confidence check)**
  - `make quick-gate`
  - Runs smoke gate + targeted runner/health pytest checks.
- **smoke gate (artifact contract check)**
  - `make smoke-gate`
  - Runs `scripts/smoke_test.sh` only.
- **full regression**
  - `make full-regression`
  - Runs full `pytest` suite.
- **pre-release verification**
  - `make pre-release-verify`
  - Runs regression + smoke + compare with one summary log.

## Typical usage

```bash
# default quick gate
make quick-gate

# explicit run id / faster epochs
RUN_ID=ops-quick-001 EPOCHS=1 make smoke-gate

# covariates and cross-validation (Phase 6 Core)
python3 src/training/runner.py --synthetic --future-covariates temp,promo --cv-splits 3 --epochs 1
```

## Edge benchmark flow

```bash
# 1) train/export with real edge holdout bundle
python3 -m src.training.runner \
  --run-id edge-ops-001 \
  --synthetic \
  --epochs 1 \
  --export-formats onnx,tflite \
  --edge-eval-samples 64

# 2) benchmark exported runtimes
python3 scripts/benchmark_edge.py \
  --run-id edge-ops-001 \
  --artifacts-dir artifacts

# 3) ingest real-device JSON if available
python3 scripts/ingest_edge_device_bench.py \
  --run-id edge-ops-001 \
  --artifacts-dir artifacts \
  --device-result android_high_end=/tmp/android_edge.json

# 3a) or generate a device JSON template from measured values
python3 scripts/make_edge_device_result.py \
  --output /tmp/android_edge.json \
  --runtime-stack tflite \
  --fallback-chain tflite,keras \
  --latency-p50-ms 18.4 \
  --latency-p95-ms 24.7 \
  --memory-peak-mb 212.0 \
  --size-mb 4.2 \
  --attempts 200 \
  --failures 0 \
  --accuracy-rmse 0.94 \
  --accuracy-baseline-rmse 1.00

# 3b) same flow via Makefile
make edge-make-device-result \
  OUTPUT=/tmp/android_edge.json \
  RUNTIME_STACK=tflite \
  FALLBACK_CHAIN=tflite,keras \
  LATENCY_P50_MS=18.4 \
  LATENCY_P95_MS=24.7 \
  MEMORY_PEAK_MB=212.0 \
  SIZE_MB=4.2 \
  ATTEMPTS=200 \
  FAILURES=0 \
  ACCURACY_RMSE=0.94 \
  ACCURACY_BASELINE_RMSE=1.00
```

Benchmark reports now surface:

- `accuracy.rmse`
- `accuracy.baseline_rmse`
- `accuracy.rmse_degradation_pct`
- `accuracy.wape`
- `accuracy.per_horizon_rmse`

Preferred real-device JSON also includes an `accuracy` block. See `docs/EDGE_DEVICE_RESULT_SCHEMA.md`.
You can start from `examples/edge_device_result_android_high_end.json` or `examples/edge_device_result_ios_high_end.json`.
If you only have measured numbers, `scripts/make_edge_device_result.py` will generate a valid payload for ingest.

## Troubleshooting pointers

- **Smoke failed with missing artifacts**
  - Check `logs/` and `artifacts/logs/<run_id>.*.log`
  - Re-run with explicit run id:
    - `RUN_ID=debug-<ts> make smoke-gate`
- **run_id mismatch / contract failure**
  - Ensure same run id is used across `processed.npz`, `meta.json`, `preprocessor.pkl`, and runner args.
  - See: `docs/RUNBOOK.md` section on run_id mismatch guard.
- **Training/runtime import errors**
  - Reinstall deps: `python3 -m pip install -r requirements.txt`
  - Confirm Python version is 3.10–3.11.
- **Pre-release verify reports NO-GO**
  - Open latest `logs/pre-release-verify-*.log`
  - Fix failed step(s), then re-run `make pre-release-verify`.

## Artifact map (run_id scoped)

- Preprocess arrays: `artifacts/processed/<run_id>/processed.npz`
- Preprocess metadata: `artifacts/processed/<run_id>/meta.json`
- Preprocessor object: `artifacts/models/<run_id>/preprocessor.pkl`
- Model checkpoints: `artifacts/checkpoints/<run_id>/best.keras`, `last.keras`
- Metrics: `artifacts/metrics/<run_id>.json`
- Edge evaluation bundle: `artifacts/exports/<run_id>/edge_eval.npz`
- Edge export manifest: `artifacts/exports/<run_id>/manifest.json`
- Edge benchmark reports: `artifacts/edge_bench/<run_id>/*.json`
- Report: `artifacts/reports/<run_id>.md`
- Smoke validation: `artifacts/reports/<run_id>_smoke_validation.md`
- Compare outputs: `artifacts/comparisons/<run_id>.json`, `.md`
- Verify summary log: `logs/pre-release-verify-<timestamp>.log`

## Related docs

- Project entry: `README.md`
- Detailed operations: `docs/RUNBOOK.md`
- Edge device schema: `docs/EDGE_DEVICE_RESULT_SCHEMA.md`
- Release gate checklist: `RELEASE_CHECKLIST.md`
