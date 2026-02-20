#!/usr/bin/env bash
set -euo pipefail

RUN_ID="${RUN_ID:-phase5-compare-$(date +%Y%m%d_%H%M%S)}"
ARTIFACTS_DIR="${ARTIFACTS_DIR:-artifacts}"
EPOCHS="${EPOCHS:-3}"

python3 -m src.training.compare_runner \
  --run-id "$RUN_ID" \
  --artifacts-dir "$ARTIFACTS_DIR" \
  --epochs "$EPOCHS" \
  --verbose 0

echo "[OK] comparison artifacts: ${ARTIFACTS_DIR}/comparisons/${RUN_ID}.json"
