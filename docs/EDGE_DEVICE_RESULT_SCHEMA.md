# Edge Device Result Schema

Operator-facing schema for JSON files passed to `scripts/ingest_edge_device_bench.py`.

Reference example:

- `examples/edge_device_result_android_high_end.json`

## Purpose

Each device JSON should describe one real runtime measurement for one exported model on one device profile.

The ingest path now supports two classes of signals:

- Runtime signals: latency, memory, size, attempts, failures, runtime stack
- Forecast-quality signals: device-side holdout accuracy, preferred for release gating

## Minimum required fields

One of the following latency forms must be present:

- `latency_p95_ms`
- `latency_ms: {"p50": ..., "p95": ...}`
- `latency_ms_samples: [...]`

Recommended minimum payload:

```json
{
  "runtime_stack": "tflite",
  "latency_ms": {
    "p50": 18.4,
    "p95": 24.7
  },
  "memory_peak_mb": 212.0,
  "size_mb": 4.2,
  "attempts": 200,
  "failures": 0
}
```

## Preferred payload with forecast-quality fields

This is the preferred schema for production use because release gating can use real device-side accuracy instead of offline aggregate metrics.

```json
{
  "runtime_stack": "tflite",
  "fallback_chain": ["tflite", "keras"],
  "latency_ms": {
    "p50": 18.4,
    "p95": 24.7
  },
  "memory_peak_mb": 212.0,
  "size_mb": 4.2,
  "attempts": 200,
  "failures": 0,
  "accuracy": {
    "rmse": 0.94,
    "baseline_rmse": 1.00,
    "rmse_degradation_pct": -6.0,
    "mae": 0.71,
    "wape": 8.9,
    "per_horizon_rmse": [0.81, 0.93, 1.05]
  }
}
```

## Field reference

### Runtime fields

- `runtime_stack` or `runtime`: runtime used on device, usually `tflite`, `onnx`, or `keras`
- `fallback_chain`: optional runtime resolution order observed on device
- `latency_p50_ms`, `latency_p95_ms`: direct latency fields
- `latency_ms`: object form with `p50` and `p95`
- `latency_ms_samples` or `latency_samples_ms`: raw samples; ingest computes `p50` and `p95`
- `size_mb` or `model_size_mb`: exported model size in MB
- `size_bytes` or `model_size_bytes`: model size in bytes
- `ram_peak_mb` or `memory_peak_mb`: peak RAM in MB
- `ram_peak_bytes` or `memory_peak_bytes`: peak RAM in bytes
- `attempts` or `runs`: number of inference attempts
- `failures` or `failure_count`: failed attempts
- `status`: optional explicit status; otherwise ingest infers it from attempts and failures

### Accuracy fields

- `accuracy.rmse`: device-side RMSE on the same holdout slice used on device
- `accuracy.baseline_rmse`: RMSE of the baseline used for comparison, usually naive-last
- `accuracy.rmse_degradation_pct`: optional explicit degradation percentage
- `accuracy.mae`: optional device-side MAE
- `accuracy.wape`: optional device-side WAPE
- `accuracy.per_horizon_rmse`: optional per-step RMSE list for multi-horizon forecasts

If `accuracy.rmse_degradation_pct` is omitted but `rmse` and `baseline_rmse` are present, ingest computes it automatically.

## Release-gate behavior

- If device JSON includes `accuracy`, the release gate prefers that device-side `rmse_degradation_pct`.
- If device JSON does not include `accuracy`, the gate falls back to offline `artifacts/metrics/<run_id>.json`.
- Missing both sources causes the accuracy gate to block promotion.

## Related commands

```bash
python3 scripts/benchmark_edge.py --run-id <run_id> --artifacts-dir artifacts
python3 scripts/ingest_edge_device_bench.py --run-id <run_id> --artifacts-dir artifacts --device-result android_high_end=/tmp/android.json
python3 scripts/edge_release_gate.py --run-id <run_id> --artifacts-dir artifacts --required-profiles android_high_end
```

Using the repo example directly:

```bash
python3 scripts/ingest_edge_device_bench.py \
  --run-id <run_id> \
  --artifacts-dir artifacts \
  --device-result android_high_end=examples/edge_device_result_android_high_end.json
```
