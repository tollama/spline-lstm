#!/usr/bin/env bash
set -uo pipefail

# Phase 4 smoke test gate with fail-fast code mapping + markdown validation report.
# Exit code map:
#   0  success
#   11 run_e2e failed
#   12 required artifact missing
#   13 metrics schema/run_id validation failed
RUN_ID="${RUN_ID:-phase4-smoke-$(date +%Y%m%d-%H%M%S)}"
ARTIFACTS_DIR="${ARTIFACTS_DIR:-artifacts}"
VALIDATION_REPORT="${ARTIFACTS_DIR}/reports/${RUN_ID}_smoke_validation.md"

STATUS="PASS"
FAIL_CODE=0
FAIL_REASON=""

write_report() {
  mkdir -p "$(dirname "$VALIDATION_REPORT")"
  {
    echo "# Smoke Validation Report"
    echo
    echo "- run_id: \`${RUN_ID}\`"
    echo "- status: **${STATUS}**"
    echo "- exit_code: ${FAIL_CODE}"
    [[ -n "${FAIL_REASON}" ]] && echo "- reason: ${FAIL_REASON}"
    echo
    echo "## Artifact Checks"
    echo "- metrics: \`${ARTIFACTS_DIR}/metrics/${RUN_ID}.json\`"
    echo "- report: \`${ARTIFACTS_DIR}/reports/${RUN_ID}.md\`"
    echo "- checkpoint(best): \`${ARTIFACTS_DIR}/checkpoints/${RUN_ID}/best.keras\`"
    echo "- preprocessor: \`${ARTIFACTS_DIR}/models/${RUN_ID}/preprocessor.pkl\`"
  } > "$VALIDATION_REPORT"
}

fail_fast() {
  FAIL_CODE="$1"
  FAIL_REASON="$2"
  STATUS="FAIL"
  write_report
  echo "[SMOKE][FAIL][${FAIL_CODE}] ${FAIL_REASON}"
  echo "[SMOKE] validation report: ${VALIDATION_REPORT}"
  exit "$FAIL_CODE"
}

echo "[SMOKE] run_id=${RUN_ID}"
set +e
RUN_ID="${RUN_ID}" EPOCHS="${EPOCHS:-1}" ARTIFACTS_DIR="${ARTIFACTS_DIR}" bash scripts/run_e2e.sh
rc=$?
set -e
[[ $rc -eq 0 ]] || fail_fast 11 "run_e2e failed with code=${rc}"

METRICS_PATH="${ARTIFACTS_DIR}/metrics/${RUN_ID}.json"
REPORT_PATH="${ARTIFACTS_DIR}/reports/${RUN_ID}.md"
BEST_PATH="${ARTIFACTS_DIR}/checkpoints/${RUN_ID}/best.keras"
PREP_PATH="${ARTIFACTS_DIR}/models/${RUN_ID}/preprocessor.pkl"

for p in "${METRICS_PATH}" "${REPORT_PATH}" "${BEST_PATH}" "${PREP_PATH}"; do
  [[ -f "$p" ]] || fail_fast 12 "missing required artifact: $p"
done

set +e
python3 - <<'PY' "${METRICS_PATH}" "${RUN_ID}"
import json, math, sys
metrics_path, run_id = sys.argv[1], sys.argv[2]
with open(metrics_path, "r", encoding="utf-8") as f:
    payload = json.load(f)
assert payload["run_id"] == run_id, f"run_id mismatch in metrics: {payload.get('run_id')} != {run_id}"
rmse = payload.get("metrics", {}).get("rmse")
assert isinstance(rmse, (int, float)) and math.isfinite(float(rmse)), "metrics.rmse must be finite"
for k in ("mae", "rmse", "mape", "r2"):
    assert k in payload["metrics"], f"missing metric: {k}"
print("[SMOKE][OK] metrics schema validated")
PY
rc=$?
set -e
[[ $rc -eq 0 ]] || fail_fast 13 "metrics validation failed"

write_report
echo "[SMOKE][OK] all checks passed"
echo "[SMOKE] validation report: ${VALIDATION_REPORT}"
