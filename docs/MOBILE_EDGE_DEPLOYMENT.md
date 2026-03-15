# Mobile Edge Deployment

Guide for deploying exported `spline-lstm` models into smartphone apps on Android and iOS.

Related docs:

- [MOBILE_BUNDLE_SCHEMA.md](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/docs/MOBILE_BUNDLE_SCHEMA.md)
- [EDGE_DEVICE_RESULT_SCHEMA.md](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/docs/EDGE_DEVICE_RESULT_SCHEMA.md)
- [EDGE_AIRGAPPED_RUNBOOK.md](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/docs/EDGE_AIRGAPPED_RUNBOOK.md)

## 1. Deployment flow

1. Train and export the model with [src/training/runner.py](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/src/training/runner.py).
2. Generate a mobile bundle manifest from `artifacts/exports/<run_id>/manifest.json`.
3. Package the runtime artifact into the Android asset pack or iOS app bundle.
4. Run native-device benchmark collection and emit a device-result JSON.
5. Ingest the device-result JSON with [scripts/ingest_edge_device_bench.py](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/scripts/ingest_edge_device_bench.py).
6. Run [scripts/edge_release_gate.py](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/scripts/edge_release_gate.py) for promotion.

## 2. Runtime policy

Recommended defaults:

- Android: prefer `tflite`, fallback to `onnx`, then `keras`
- iOS: prefer `onnx`, fallback to `tflite`, then `keras`

Those are defaults, not hard rules. If the mobile app already standardizes on a single runtime, set that explicitly in the generated bundle manifest.

## 3. Generate the app-side bundle manifest

Android:

```bash
python3 scripts/make_mobile_bundle_manifest.py \
  --platform android \
  --export-manifest artifacts/exports/<run_id>/manifest.json \
  --output /tmp/android_bundle.json \
  --bundle-id ai.tollama.splineforecast \
  --build-number 12034
```

Equivalent Makefile wrapper:

```bash
make edge-make-mobile-bundle \
  PLATFORM=android \
  EXPORT_MANIFEST=artifacts/exports/<run_id>/manifest.json \
  OUTPUT=/tmp/android_bundle.json \
  BUNDLE_ID=ai.tollama.splineforecast \
  BUILD_NUMBER=12034
```

iOS:

```bash
python3 scripts/make_mobile_bundle_manifest.py \
  --platform ios \
  --export-manifest artifacts/exports/<run_id>/manifest.json \
  --output /tmp/ios_bundle.json \
  --bundle-id ai.tollama.splineforecast \
  --build-number 12034
```

Reference examples:

- [mobile_bundle_android_tflite.json](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/examples/mobile_bundle_android_tflite.json)
- [mobile_bundle_ios_onnx.json](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/examples/mobile_bundle_ios_onnx.json)

## 4. Native benchmark result contract

The phone-side benchmark emitter should produce the same ingest JSON schema already used by edge devices, with an additional optional `metadata` block.

Recommended metadata:

```json
{
  "metadata": {
    "platform": "android",
    "device_model": "Pixel 8",
    "os_version": "Android 15",
    "app_version": "1.12.0",
    "build_number": "12034",
    "bundle_id": "ai.tollama.splineforecast"
  }
}
```

Reference examples:

- [mobile_benchmark_result_android_pixel8.json](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/examples/mobile_benchmark_result_android_pixel8.json)
- [mobile_benchmark_result_ios_iphone15pro.json](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/examples/mobile_benchmark_result_ios_iphone15pro.json)

Those payloads can be ingested directly:

```bash
python3 scripts/ingest_edge_device_bench.py \
  --run-id <run_id> \
  --artifacts-dir artifacts \
  --device-result android_high_end=examples/mobile_benchmark_result_android_pixel8.json \
  --device-result ios_high_end=examples/mobile_benchmark_result_ios_iphone15pro.json
```

## 5. What the native app should measure

Minimum:

- runtime selected
- latency `p50` and `p95`
- memory peak
- model size
- attempts and failures

Preferred:

- holdout RMSE on the device
- baseline RMSE on the same slice
- per-horizon RMSE
- app/device metadata

## 6. Native integration checklist

### Android

- package the selected artifact under `assets/` or Play Asset Delivery
- lock ABI expectations, normally `arm64-v8a`
- verify model load on cold start and after process recreation
- measure latency on the same path used in production inference

### iOS

- package the selected artifact under the app bundle or a managed download directory
- verify model load after app relaunch and low-memory restoration
- measure latency on the same path used in production inference
- confirm deployment target and runtime library match the bundle manifest

## 7. Remaining external validation

This repository now defines the contract and generation flow, but the following still require the actual mobile app and devices:

- native Android benchmark emitter implementation
- native iOS benchmark emitter implementation
- app-side model checksum verification
- app OTA/update rollback behavior
- device-farm or real-device validation on the supported phone matrix
