#!/usr/bin/env bash
set -u

ARTIFACTS_DIR="${ARTIFACTS_DIR:-artifacts}"
EPOCHS="${EPOCHS:-1}"
TS="$(date +%Y%m%d-%H%M%S)"
BASE_RUN_ID="${RUN_ID_PREFIX:-pre-release}-${TS}"
SMOKE_RUN_ID="${BASE_RUN_ID}-smoke"
COMPARE_RUN_ID="${BASE_RUN_ID}-compare"
LOG_PATH="logs/pre-release-verify-${TS}.log"

mkdir -p logs

pass=0
fail=0

run_step() {
  local name="$1"
  shift
  echo "[VERIFY] >>> ${name}" | tee -a "${LOG_PATH}"
  if "$@" >>"${LOG_PATH}" 2>&1; then
    echo "[VERIFY][PASS] ${name}" | tee -a "${LOG_PATH}"
    pass=$((pass + 1))
  else
    local code=$?
    echo "[VERIFY][FAIL] ${name} (exit=${code})" | tee -a "${LOG_PATH}"
    fail=$((fail + 1))
  fi
}

echo "[VERIFY] pre-release verification started" | tee "${LOG_PATH}"
echo "[VERIFY] log=${LOG_PATH}" | tee -a "${LOG_PATH}"
echo "[VERIFY] smoke_run_id=${SMOKE_RUN_ID}" | tee -a "${LOG_PATH}"
echo "[VERIFY] compare_run_id=${COMPARE_RUN_ID}" | tee -a "${LOG_PATH}"

run_step "pytest" python3 -m pytest -q
run_step "smoke_test" env RUN_ID="${SMOKE_RUN_ID}" EPOCHS="${EPOCHS}" ARTIFACTS_DIR="${ARTIFACTS_DIR}" bash scripts/smoke_test.sh
run_step "run_compare" env RUN_ID="${COMPARE_RUN_ID}" EPOCHS="${EPOCHS}" ARTIFACTS_DIR="${ARTIFACTS_DIR}" bash scripts/run_compare.sh

echo "" | tee -a "${LOG_PATH}"
echo "[VERIFY] ===== SUMMARY =====" | tee -a "${LOG_PATH}"
echo "[VERIFY] PASS=${pass}" | tee -a "${LOG_PATH}"
echo "[VERIFY] FAIL=${fail}" | tee -a "${LOG_PATH}"

action="GO"
if [[ "${fail}" -gt 0 ]]; then
  action="NO-GO"
fi

echo "[VERIFY] RECOMMENDATION=${action}" | tee -a "${LOG_PATH}"
echo "[VERIFY] ===================" | tee -a "${LOG_PATH}"

echo "[VERIFY] done; see ${LOG_PATH}"

if [[ "${fail}" -gt 0 ]]; then
  exit 1
fi
exit 0
