#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"

curl -fsS "$BASE_URL/api/v1/health" >/dev/null

cat <<'JSON' | curl -fsS -X POST "$BASE_URL/api/v1/forecast/validate-inputs" -H 'content-type: application/json' --data-binary @- >/dev/null
{
  "run_id": "quickcheck-001",
  "actor": "skill",
  "base_inputs": {
    "horizon": 2,
    "target_history": [10, 11, 12],
    "known_future_covariates": {"promo": [0, 1]},
    "static_covariates": {"store_type": "A"}
  },
  "patches": [{"op": "replace", "path": "/known_future_covariates/promo/1", "value": 2}]
}
JSON

curl -fsS "$BASE_URL/api/v1/mcp/capabilities" >/dev/null
curl -fsS "$BASE_URL/api/tags" >/dev/null

echo "phase6_quickcheck: ok"
