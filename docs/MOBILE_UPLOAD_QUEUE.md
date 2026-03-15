# Mobile Upload Queue

Reference policy for delivering phone benchmark telemetry when the app is offline, backgrounded, or rate-limited.

Related references:

- [MOBILE_TELEMETRY_UPLOAD.md](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/docs/MOBILE_TELEMETRY_UPLOAD.md)
- [MobileBenchmarkQueueStore.kt](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/examples/mobile/android/MobileBenchmarkQueueStore.kt)
- [MobileBenchmarkReplayWorker.kt](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/examples/mobile/android/MobileBenchmarkReplayWorker.kt)
- [MobileBenchmarkQueueStore.swift](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/examples/mobile/ios/MobileBenchmarkQueueStore.swift)
- [MobileBenchmarkReplayWorker.swift](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/examples/mobile/ios/MobileBenchmarkReplayWorker.swift)

## Queue policy

- persist uploads locally before attempting network delivery
- include `X-Idempotency-Key` on every replayed request
- retry on `408`, `425`, `429`, and `5xx`
- drop permanently invalid uploads on other `4xx` responses
- use exponential backoff starting at 15 seconds and cap retries to a bounded window in the app

## Android reference

The Android references use a JSON queue file under `filesDir`:

- [MobileBenchmarkQueueStore.kt](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/examples/mobile/android/MobileBenchmarkQueueStore.kt)
- [MobileBenchmarkReplayWorker.kt](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/examples/mobile/android/MobileBenchmarkReplayWorker.kt)

Recommended integration points:

- enqueue after benchmark creation succeeds
- flush on app foreground, charger/Wi-Fi windows, or WorkManager background jobs
- attach the same `idempotencyKey` on every replay attempt

## iOS reference

The iOS references use a JSON queue file under `Application Support`:

- [MobileBenchmarkQueueStore.swift](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/examples/mobile/ios/MobileBenchmarkQueueStore.swift)
- [MobileBenchmarkReplayWorker.swift](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/examples/mobile/ios/MobileBenchmarkReplayWorker.swift)

Recommended integration points:

- enqueue after benchmark serialization completes
- flush on app foreground and background refresh opportunities
- keep uploads small and bounded so replay does not block app startup

## Operational notes

- sign replayed requests the same way as first-send requests when `SPLINE_MOBILE_UPLOAD_SIGNING_SECRET` is enabled
- treat persisted queue files as telemetry, not the source of truth for model promotion
- use the backend receipt endpoints to verify whether a replayed upload was accepted
