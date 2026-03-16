# Mobile Device Farm Runbook

Runbook for executing the signed queue-replay telemetry flow on a real device farm.

This repository does not contain device-farm project files or credentials, so this document defines the exact sequence the mobile app repositories should automate.

## Preconditions

- Android and iOS apps have integrated:
  - benchmark emitter
  - queue store
  - replay worker
  - signed uploader
- backend is reachable from the farm
- backend mobile signing secret configuration is aligned with the app test build
- test build has a valid mobile model bundle embedded or downloadable

## Farm job stages

1. Provision test build
2. Inject runtime config
3. Execute benchmark scenario
4. Force replay
5. Query backend receipts
6. Query backend summaries
7. Fail or pass the job based on receipt state

## Injected config

The farm job needs:

- `MOBILE_BENCHMARK_ENDPOINT`
- `MOBILE_API_TOKEN` if auth is enabled
- `MOBILE_UPLOAD_SIGNING_SECRET` if signed uploads are enabled
- `MOBILE_TEST_RUN_ID`

## Backend verification commands

Replace placeholders with the farm-generated values.

```bash
curl -sS "$BACKEND/api/v1/mobile/benchmarks/summary?run_id=$RUN_ID"
curl -sS "$BACKEND/api/v1/dashboard/summary"
curl -sS "$BACKEND/api/v1/mobile/benchmarks/receipts/$RECEIPT_ID"
```

## Pass criteria

- Android upload returns a successful receipt
- iOS upload returns a successful receipt
- summary for the run shows non-zero receipts
- dashboard `mobileBenchmarks` reflects the uploaded platform/runtime mix

## Fail criteria

- upload rejected due to missing or invalid signature
- replay worker never drains the queue
- receipt status missing after benchmark completion
- dashboard summary fails to reflect the run after upload succeeds
