# Mobile Release Checklist

Checklist for promoting a `spline-lstm` mobile model bundle into Android or iOS app releases.

## Bundle contract

- [ ] mobile bundle manifest validates with [validate_mobile_bundle.py](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/scripts/validate_mobile_bundle.py)
- [ ] `model.runtime_stack` matches the intended platform runtime policy
- [ ] `model.sha256` and `model.size_bytes` are present
- [ ] referenced export manifest and OTA manifest exist
- [ ] `app.min_version` matches the app version floor intended for rollout

## App integration

- [ ] native app loads the bundled/downloaded file from `model.relative_path`
- [ ] native app verifies `model.sha256` before runtime load
- [ ] app-side runtime library matches `platform_config.runtime_library`
- [ ] runtime fallback behavior follows `model.fallback_chain`

## Runtime behavior

- [ ] cold-start model load succeeds
- [ ] warm inference path succeeds
- [ ] app relaunch or process recreation reloads the model successfully
- [ ] low-memory or background/foreground transitions do not corrupt model state

## Benchmarking

- [ ] device benchmark payload emitted from Android reference path
- [ ] device benchmark payload emitted from iOS reference path
- [ ] payload includes latency, memory, size, attempts, failures
- [ ] payload includes device/app metadata
- [ ] payload includes device-side holdout accuracy when available

## Promotion gate

- [ ] device results ingest successfully via [ingest_edge_device_bench.py](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/scripts/ingest_edge_device_bench.py)
- [ ] release gate passes via [edge_release_gate.py](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/scripts/edge_release_gate.py)
- [ ] rollback target is known for the currently deployed mobile bundle

## Device coverage

- [ ] at least one reference Android device validated
- [ ] at least one reference iPhone validated
- [ ] target OS versions covered by the rollout are represented
- [ ] latency and memory are within per-profile budgets
