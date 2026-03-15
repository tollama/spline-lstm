# Mobile Telemetry Upload

Contract for uploading Android/iOS benchmark payloads into the backend.

## Endpoint

`POST /api/v1/mobile/benchmarks:ingest`

Batch variant:

`POST /api/v1/mobile/benchmarks:ingest-batch`

Receipt endpoints:

- `GET /api/v1/mobile/benchmarks/receipts/{receipt_id}`
- `GET /api/v1/mobile/benchmarks/receipts?run_id=<run_id>&device_profile=<profile>`

## Request body

```json
{
  "run_id": "edge-demo-001",
  "device_profile": "android_high_end",
  "expected_platform": "android",
  "strict_runtime_policy": false,
  "require_accuracy": true,
  "require_metadata": true,
  "benchmark_result": {
    "runtime_stack": "tflite",
    "fallback_chain": ["tflite", "keras"],
    "latency_ms": {"p50": 15.8, "p95": 22.1},
    "memory_peak_mb": 198.4,
    "size_mb": 4.2,
    "attempts": 250,
    "failures": 0,
    "metadata": {
      "platform": "android",
      "device_model": "Pixel 8",
      "os_version": "Android 15",
      "app_version": "1.12.0",
      "build_number": "12034",
      "bundle_id": "ai.tollama.splineforecast"
    },
    "accuracy": {
      "rmse": 0.92,
      "baseline_rmse": 1.0,
      "per_horizon_rmse": [0.79, 0.9, 1.02]
    }
  }
}
```

## Response body

```json
{
  "ok": true,
  "data": {
    "run_id": "edge-demo-001",
    "device_profile": "android_high_end",
    "source_path": "artifacts/mobile_uploads/edge-demo-001/android_high_end-req-123.json",
    "validation": {"ok": true, "errors": [], "warnings": []},
    "record": {},
    "leaderboard": {"champion": "android_high_end", "fallback": null},
    "correlation": {"request_id": "req-123", "run_id": "edge-demo-001"}
  }
}
```

## Curl example

```bash
curl -X POST http://127.0.0.1:8000/api/v1/mobile/benchmarks:ingest \
  -H "Content-Type: application/json" \
  -H "X-Idempotency-Key: mobile-upload-001" \
  -d @examples/mobile_upload_request_android.json
```

Batch example:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/mobile/benchmarks:ingest-batch \
  -H "Content-Type: application/json" \
  -H "X-Idempotency-Key: mobile-batch-001" \
  -d @examples/mobile_upload_request_batch.json
```

## Native client references

- [MobileBenchmarkUploader.kt](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/examples/mobile/android/MobileBenchmarkUploader.kt)
- [MobileBenchmarkUploader.swift](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/examples/mobile/ios/MobileBenchmarkUploader.swift)

These references show how to wrap the benchmark payload produced by:

- [MobileBenchmarkEmitter.kt](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/examples/mobile/android/MobileBenchmarkEmitter.kt)
- [MobileBenchmarkEmitter.swift](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/examples/mobile/ios/MobileBenchmarkEmitter.swift)

## Failure behavior

If validation fails, the endpoint returns `400` with a structured error payload under `error`.

If auth is enabled in the backend, include `X-API-Token`.

For retry-safe uploads from mobile queues, include `X-Idempotency-Key`. Repeated requests with the same key return the cached response.

## Optional signed upload mode

If the backend is started with `SPLINE_MOBILE_UPLOAD_SIGNING_SECRET`, mobile upload endpoints require:

- `X-Mobile-Timestamp`
- `X-Mobile-Signature`

Signature format:

`hex(hmac_sha256(secret, "<timestamp>\\n<raw_request_body>"))`

The backend also enforces timestamp freshness with `SPLINE_MOBILE_UPLOAD_TIMESTAMP_SKEW_SEC` (default `300` seconds).

## Receipts

Successful uploads return a receipt block:

```json
{
  "receipt": {
    "receipt_id": "mobile-receipt-1234abcd",
    "receipt_path": "artifacts/mobile_receipts/mobile-receipt-1234abcd.json"
  }
}
```

Use the receipt endpoints to audit whether a phone upload was accepted and which stored benchmark record it produced.
