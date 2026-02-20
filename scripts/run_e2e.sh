#!/usr/bin/env bash
set -euo pipefail

# One-click E2E with normalized exit codes (Phase 4 contract).
# Codes: 0,10,11,12,20,21,22,27,30,31,99

RUN_ID="${RUN_ID:-e2e-$(date +%Y%m%d-%H%M%S)}"
ARTIFACTS_DIR="${ARTIFACTS_DIR:-artifacts}"
EPOCHS="${EPOCHS:-1}"
LOOKBACK="${LOOKBACK:-24}"
HORIZON="${HORIZON:-1}"
SCALING="${SCALING:-standard}"
INPUT_PATH="${INPUT_PATH:-}"

mkdir -p "${ARTIFACTS_DIR}/logs"
PRE_LOG="${ARTIFACTS_DIR}/logs/${RUN_ID}.preprocess.log"
TRAIN_LOG="${ARTIFACTS_DIR}/logs/${RUN_ID}.train.log"
HEALTH_LOG="${ARTIFACTS_DIR}/logs/${RUN_ID}.health.log"

fail() {
  local code="$1"
  shift
  echo "[E2E][FAIL][${code}] $*"
  exit "${code}"
}

if [[ -z "${RUN_ID}" || "${RUN_ID}" == *"/"* || "${RUN_ID}" == *"\\"* ]]; then
  fail 12 "invalid RUN_ID"
fi

PRE_CMD=(python3 -m src.preprocessing.smoke --run-id "${RUN_ID}" --lookback "${LOOKBACK}" --horizon "${HORIZON}" --scaling "${SCALING}" --artifacts-dir "${ARTIFACTS_DIR}")
if [[ -n "${INPUT_PATH}" ]]; then
  if [[ ! -f "${INPUT_PATH}" ]]; then
    fail 10 "input file not found: ${INPUT_PATH}"
  fi
  PRE_CMD+=(--input "${INPUT_PATH}")
fi

echo "[E2E] run_id=${RUN_ID}"
echo "[E2E] step1/3 preprocessing"
set +e
"${PRE_CMD[@]}" >"${PRE_LOG}" 2>&1
rc=$?
set -e
if [[ $rc -ne 0 ]]; then
  if grep -qiE "run_id must" "${PRE_LOG}"; then
    fail 12 "run_id validation failed (see ${PRE_LOG})"
  elif grep -qiE "timestamp|target|schema|column" "${PRE_LOG}"; then
    fail 11 "input schema validation failed (see ${PRE_LOG})"
  elif grep -qiE "No such file|FileNotFoundError|cannot find" "${PRE_LOG}"; then
    fail 10 "input read failed (see ${PRE_LOG})"
  else
    fail 20 "preprocessing failed (see ${PRE_LOG})"
  fi
fi

PROCESSED_PATH="${ARTIFACTS_DIR}/processed/${RUN_ID}/processed.npz"
PREP_PATH="${ARTIFACTS_DIR}/models/${RUN_ID}/preprocessor.pkl"
if [[ ! -f "${PROCESSED_PATH}" || ! -f "${ARTIFACTS_DIR}/processed/${RUN_ID}/meta.json" || ! -f "${PREP_PATH}" ]]; then
  fail 20 "missing preprocessing outputs"
fi

echo "[E2E] step2/3 training runner"
set +e
python3 -m src.training.runner \
  --run-id "${RUN_ID}" \
  --processed-npz "${PROCESSED_PATH}" \
  --preprocessor-pkl "${PREP_PATH}" \
  --epochs "${EPOCHS}" \
  --artifacts-dir "${ARTIFACTS_DIR}" >"${TRAIN_LOG}" 2>&1
rc=$?
set -e
if [[ $rc -ne 0 ]]; then
  if grep -qi "run_id mismatch" "${TRAIN_LOG}"; then
    fail 27 "run_id mismatch detected (see ${TRAIN_LOG})"
  elif grep -qiE "TensorFlow backend is required|ModuleNotFoundError|ImportError|shape|ValueError" "${TRAIN_LOG}"; then
    fail 21 "training runtime failure (see ${TRAIN_LOG})"
  elif grep -qiE "Permission denied|No space left|OSError" "${TRAIN_LOG}"; then
    fail 22 "metrics/report save failure (see ${TRAIN_LOG})"
  else
    fail 21 "training failed (see ${TRAIN_LOG})"
  fi
fi

echo "[E2E] step3/3 health check"
set +e
python3 scripts/health_check.py --run-id "${RUN_ID}" --artifacts-dir "${ARTIFACTS_DIR}" >"${HEALTH_LOG}" 2>&1
rc=$?
set -e
if [[ $rc -ne 0 ]]; then
  if [[ $rc -eq 27 ]]; then
    fail 27 "health check run_id mismatch (see ${HEALTH_LOG})"
  fi
  fail 30 "health check failed (see ${HEALTH_LOG})"
fi

echo "[E2E][OK] completed"
echo "- metrics: ${ARTIFACTS_DIR}/metrics/${RUN_ID}.json"
echo "- report:  ${ARTIFACTS_DIR}/reports/${RUN_ID}.md"
echo "- best:    ${ARTIFACTS_DIR}/checkpoints/${RUN_ID}/best.keras"
