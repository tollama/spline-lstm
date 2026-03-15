#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${MODE:-ops}"
VENV_DIR="${VENV_DIR:-${ROOT_DIR}/.venv-edge-smoke}"
ARTIFACTS_DIR="${ARTIFACTS_DIR:-${ROOT_DIR}/artifacts-edge-smoke}"
CACHE_ROOT="${CACHE_ROOT:-/tmp/xdg-cache-spline-edge-smoke}"
RUN_ID="${RUN_ID:-edge-smoke-$(date +%Y%m%d-%H%M%S)}"

usage() {
  cat <<EOF
Usage: bash scripts/edge_smoke_env.sh [--mode ops|benchmark-onnx|train-export] [--venv-dir PATH] [--artifacts-dir PATH] [--cache-root PATH] [--run-id ID]

Fresh-environment smoke validation for edge-focused spline-lstm installs.

Modes:
  ops            install from 'requirements-edge-ops.txt' and validate ingest/gate flow
  benchmark-onnx install from 'requirements-edge-runtime.txt' and validate ONNX benchmark support
  train-export   install from 'requirements-edge-train-export.txt' and validate full export node support
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="$2"
      shift 2
      ;;
    --venv-dir)
      VENV_DIR="$2"
      shift 2
      ;;
    --artifacts-dir)
      ARTIFACTS_DIR="$2"
      shift 2
      ;;
    --cache-root)
      CACHE_ROOT="$2"
      shift 2
      ;;
    --run-id)
      RUN_ID="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "$MODE" in
  ops)
    REQUIREMENTS_FILE="requirements-edge-ops.txt"
    VALIDATE_MODE="ops"
    ;;
  benchmark-onnx)
    REQUIREMENTS_FILE="requirements-edge-runtime.txt"
    VALIDATE_MODE="benchmark-onnx"
    ;;
  train-export)
    REQUIREMENTS_FILE="requirements-edge-train-export.txt"
    VALIDATE_MODE="train-export"
    ;;
  *)
    echo "Unsupported mode: $MODE" >&2
    exit 2
    ;;
esac

mkdir -p "$CACHE_ROOT"
mkdir -p "$ARTIFACTS_DIR"
rm -rf "$VENV_DIR"

echo "[edge-smoke] creating venv: $VENV_DIR"
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

export MPLCONFIGDIR="${CACHE_ROOT}/matplotlib"
export XDG_CACHE_HOME="${CACHE_ROOT}"
mkdir -p "$MPLCONFIGDIR"

echo "[edge-smoke] installing requirements: $REQUIREMENTS_FILE"
python -m pip install -r "$ROOT_DIR/$REQUIREMENTS_FILE"

echo "[edge-smoke] installing editable package without dependency resolution"
python -m pip install -e "$ROOT_DIR" --no-deps

echo "[edge-smoke] validating environment mode=$VALIDATE_MODE"
python scripts/validate_edge_environment.py --mode "$VALIDATE_MODE" --cache-root "$CACHE_ROOT"

if [[ "$MODE" == "ops" ]]; then
  echo "[edge-smoke] running sample release path"
  make edge-release-example RUN_ID="$RUN_ID" ARTIFACTS_DIR="$ARTIFACTS_DIR" MPLCONFIGDIR="$MPLCONFIGDIR" XDG_CACHE_HOME="$XDG_CACHE_HOME"
fi

echo "[edge-smoke] complete"
