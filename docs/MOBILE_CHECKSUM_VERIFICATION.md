# Mobile Checksum Verification

Reference guidance for verifying smartphone model artifacts before native runtime load.

## Expected source of truth

Use the SHA-256 in the mobile bundle manifest:

- [MOBILE_BUNDLE_SCHEMA.md](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/docs/MOBILE_BUNDLE_SCHEMA.md)
- field: `model.sha256`

The app should verify the downloaded or bundled artifact before loading it into TFLite or ONNX Runtime.

## Android reference helper

Reference file:

- [ModelChecksumVerifier.kt](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/examples/mobile/android/ModelChecksumVerifier.kt)

Recommended flow:

1. read the file from app storage or asset extraction path
2. compute SHA-256
3. compare against `model.sha256`
4. abort model load and fall back if the checksum mismatches

## iOS reference helper

Reference file:

- [ModelChecksumVerifier.swift](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/examples/mobile/ios/ModelChecksumVerifier.swift)

Recommended flow:

1. read the file from the app bundle or downloaded model directory
2. compute SHA-256
3. compare against `model.sha256`
4. abort model load and fall back if the checksum mismatches

## Failure policy

If checksum verification fails:

- do not load the artifact
- record the failure in app telemetry
- fall back to the next runtime in `fallback_chain` if available
- if no runtime remains, block promotion for that bundle and keep the prior model
