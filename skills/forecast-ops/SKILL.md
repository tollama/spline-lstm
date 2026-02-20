---
name: forecast-ops
description: Use this skill when another agent needs to run spline-lstm forecasting workflows (validate/preview adjusted inputs, execute forecast jobs, and use Tollama-compatible endpoints).
---

# Forecast Ops Skill

Use this skill when an agent needs to orchestrate Phase 6 forecast operations through API calls.

## Workflow

1. Health check: `GET /api/v1/health`
2. Validate adjusted inputs: `POST /api/v1/forecast/validate-inputs`
3. Preview adjusted forecast: `POST /api/v1/forecast/preview`
4. Execute adjusted run: `POST /api/v1/forecast/execute-adjusted`
5. Validate covariate schema/payload: `POST /api/v1/covariates/validate`
6. Poll job status: `GET /api/v1/jobs/{job_id}`
7. Retrieve artifacts/metrics as needed.
5. Poll job status: `GET /api/v1/jobs/{job_id}`
6. Retrieve artifacts/metrics as needed.

## Agent / MCP Discovery

- Tool list: `GET /api/v1/agent/tools`
- MCP capability schema: `GET /api/v1/mcp/capabilities`
- Tool invoke contract: `POST /api/v1/agent/tools:invoke`
- For safe retries, send `x-idempotency-key` header when invoking tools.

## Tollama-compatible Endpoints

- `GET /api/tags`
- `POST /api/generate`
- `POST /api/chat`

If `stream=true`, parse newline-delimited JSON chunks (`application/x-ndjson`).

## Pilot Safety

- Rollout/status probe: `GET /api/v1/pilot/readiness`
- Kill-switches are exposed in readiness payload under `kill_switches`.

## Scripts

- `scripts/phase6_quickcheck.sh` performs a minimal end-to-end API sanity check.
