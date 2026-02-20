#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   bash scripts/gen_synthetic.sh S1 720 42 "temp,promo,event"
# Defaults:
#   scenario=S1, n_samples=720, seed=42, covariates=""

SCENARIO="${1:-S1}"
N_SAMPLES="${2:-720}"
SEED="${3:-42}"
COVARIATES="${4:-}"
OUT_DIR="${OUT_DIR:-data/raw/synthetic}"
NOISE_SCALE="${NOISE_SCALE:-0.2}"

python3 -m src.data.synthetic_generator \
  --scenario "${SCENARIO}" \
  --n-samples "${N_SAMPLES}" \
  --seed "${SEED}" \
  --covariates "${COVARIATES}" \
  --noise-scale "${NOISE_SCALE}" \
  --out-dir "${OUT_DIR}"
