# Mobile App Integration Handoff

Concrete handoff for wiring the signed benchmark upload and replay flow into the real Android and iOS application codebases.

This repository does not contain the production mobile app projects, so the steps below are the exact integration work to perform in those repos.

Related references:

- [MOBILE_EDGE_DEPLOYMENT.md](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/docs/MOBILE_EDGE_DEPLOYMENT.md)
- [MOBILE_TELEMETRY_UPLOAD.md](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/docs/MOBILE_TELEMETRY_UPLOAD.md)
- [MOBILE_UPLOAD_QUEUE.md](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/docs/MOBILE_UPLOAD_QUEUE.md)
- [examples/mobile/android/MobileBenchmarkUploader.kt](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/examples/mobile/android/MobileBenchmarkUploader.kt)
- [examples/mobile/android/MobileBenchmarkQueueStore.kt](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/examples/mobile/android/MobileBenchmarkQueueStore.kt)
- [examples/mobile/android/MobileBenchmarkReplayWorker.kt](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/examples/mobile/android/MobileBenchmarkReplayWorker.kt)
- [examples/mobile/ios/MobileBenchmarkUploader.swift](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/examples/mobile/ios/MobileBenchmarkUploader.swift)
- [examples/mobile/ios/MobileBenchmarkQueueStore.swift](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/examples/mobile/ios/MobileBenchmarkQueueStore.swift)
- [examples/mobile/ios/MobileBenchmarkReplayWorker.swift](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/examples/mobile/ios/MobileBenchmarkReplayWorker.swift)

## 1. Android app integration

Copy or adapt these references into the Android app:

- `MobileBenchmarkEmitter.kt`
- `MobileBenchmarkUploader.kt`
- `MobileBenchmarkQueueStore.kt`
- `MobileBenchmarkReplayWorker.kt`

Wire them at these points:

1. After on-device benchmark measurement completes, serialize the benchmark payload.
2. Enqueue the payload immediately with a stable `idempotencyKey`.
3. Start `MobileBenchmarkReplayWorker.flushReadyUploads()` from:
   - app foreground
   - WorkManager background jobs
   - charger or Wi-Fi constrained windows if the app already uses them
4. Pass the backend endpoint, optional API token, and optional mobile signing secret into the replay worker.

Recommended Android ownership points:

- inference/benchmark module: payload creation
- app startup or foreground observer: queue replay trigger
- background work module: periodic retry trigger
- secure config source: endpoint URL and signing secret

## 2. iOS app integration

Copy or adapt these references into the iOS app:

- `MobileBenchmarkEmitter.swift`
- `MobileBenchmarkUploader.swift`
- `MobileBenchmarkQueueStore.swift`
- `MobileBenchmarkReplayWorker.swift`

Wire them at these points:

1. After benchmark serialization, enqueue a `PendingMobileBenchmarkUpload`.
2. Trigger replay from:
   - app foreground
   - background refresh windows
   - any existing maintenance task path
3. Pass endpoint URL, optional API token, and optional signing secret into the replay worker.

Recommended iOS ownership points:

- inference/benchmark service: payload creation
- app lifecycle observer: replay trigger
- background task scheduler: bounded retry trigger
- secure config source: endpoint URL and signing secret

## 3. Required runtime configuration

The app repos need these settings:

- backend mobile ingest endpoint
- optional API token if backend auth is enabled
- mobile upload signing secret if `SPLINE_MOBILE_UPLOAD_SIGNING_SECRET` is enabled server-side
- stable app metadata fields:
  - `platform`
  - `device_model`
  - `os_version`
  - `app_version`
  - `build_number`
  - `bundle_id`

Do not hardcode the signing secret in source control. Load it from the app’s secure configuration path.

## 4. Signed replay contract

Every replayed request should include:

- `X-Idempotency-Key`
- `X-Mobile-Timestamp`
- `X-Mobile-Signature`

Signature input:

`<timestamp>\n<raw_request_body>`

The request body must match the bytes actually sent over the network.

## 5. Real-device execution checklist

Run this on at least one Android reference device and one iPhone reference device:

1. install an app build with the integrated queue/replay path
2. load a valid mobile model bundle
3. execute on-device inference benchmark
4. confirm the payload is queued locally
5. disable network and trigger replay to confirm the item stays queued
6. restore network and trigger replay again
7. confirm backend receipt creation via:
   - `GET /api/v1/mobile/benchmarks/receipts/{receipt_id}`
   - `GET /api/v1/mobile/benchmarks/summary?run_id=<run_id>`
   - `GET /api/v1/dashboard/summary`
8. verify the upload shows `status: succeeded`
9. repeat once with an intentionally invalid payload and confirm `validation_failed`

## 6. Device-farm execution checklist

If the mobile apps already run on a device farm, add a job that:

1. installs the test build
2. injects endpoint and signing config
3. runs an in-app benchmark flow
4. triggers upload replay
5. exports the resulting `run_id` and `receipt_id`
6. calls the backend receipt and summary endpoints as post-checks

Expected pass criteria:

- at least one successful receipt per platform
- zero unsigned-upload rejections when signing is enabled
- dashboard `mobileBenchmarks` reflects the uploaded run

## 7. Acceptance criteria for handoff completion

The mobile repos should not consider this done until they can produce:

- one Android receipt from a signed replayed upload
- one iOS receipt from a signed replayed upload
- one screenshot or export showing the dashboard mobile telemetry block updated for that run
- one failing-path receipt showing `validation_failed`
