#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${MODE:-ops}"
VENV_DIR="${VENV_DIR:-${ROOT_DIR}/.venv-edge-smoke}"
ARTIFACTS_DIR="${ARTIFACTS_DIR:-${ROOT_DIR}/artifacts-edge-smoke}"
CACHE_ROOT="${CACHE_ROOT:-/tmp/xdg-cache-spline-edge-smoke}"
RUN_ID="${RUN_ID:-edge-smoke-$(date +%Y%m%d-%H%M%S)}"
WHEELHOUSE_DIR="${WHEELHOUSE_DIR:-}"
MIN_FREE_DISK_MB="${MIN_FREE_DISK_MB:-0}"
MIN_TOTAL_MEMORY_MB="${MIN_TOTAL_MEMORY_MB:-0}"
ONNX_SMOKE_MODEL="${ONNX_SMOKE_MODEL:-}"
SKIP_FUNCTIONAL_SMOKE="${SKIP_FUNCTIONAL_SMOKE:-0}"

usage() {
  cat <<EOF
Usage: bash scripts/edge_smoke_env.sh [--mode ops|benchmark-onnx|train-export] [--venv-dir PATH] [--artifacts-dir PATH] [--cache-root PATH] [--run-id ID] [--wheelhouse-dir PATH]

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
    --wheelhouse-dir)
      WHEELHOUSE_DIR="$2"
      shift 2
      ;;
    --min-free-disk-mb)
      MIN_FREE_DISK_MB="$2"
      shift 2
      ;;
    --min-total-memory-mb)
      MIN_TOTAL_MEMORY_MB="$2"
      shift 2
      ;;
    --onnx-smoke-model)
      ONNX_SMOKE_MODEL="$2"
      shift 2
      ;;
    --skip-functional-smoke)
      SKIP_FUNCTIONAL_SMOKE="1"
      shift
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
if [[ -n "$WHEELHOUSE_DIR" ]]; then
  python -m pip install --no-index --find-links "$WHEELHOUSE_DIR" -r "$ROOT_DIR/$REQUIREMENTS_FILE"
else
  python -m pip install -r "$ROOT_DIR/$REQUIREMENTS_FILE"
fi

if [[ -n "$WHEELHOUSE_DIR" ]]; then
  echo "[edge-smoke] installing spline-lstm wheel from wheelhouse"
  PACKAGE_WHEEL="$(find "$WHEELHOUSE_DIR" -maxdepth 1 -type f -name 'spline_lstm-*.whl' | sort | tail -n 1)"
  if [[ -z "$PACKAGE_WHEEL" ]]; then
    echo "spline-lstm wheel not found in wheelhouse: $WHEELHOUSE_DIR" >&2
    exit 2
  fi
  python -m pip install --no-index --find-links "$WHEELHOUSE_DIR" "$PACKAGE_WHEEL"
else
  echo "[edge-smoke] installing editable package without dependency resolution"
  python -m pip install -e "$ROOT_DIR" --no-deps
fi

echo "[edge-smoke] validating environment mode=$VALIDATE_MODE"
VALIDATE_ARGS=(
  --mode "$VALIDATE_MODE"
  --cache-root "$CACHE_ROOT"
  --artifacts-dir "$ARTIFACTS_DIR"
  --min-free-disk-mb "$MIN_FREE_DISK_MB"
  --min-total-memory-mb "$MIN_TOTAL_MEMORY_MB"
)
if [[ -n "$ONNX_SMOKE_MODEL" ]]; then
  VALIDATE_ARGS+=(--onnx-smoke-model "$ONNX_SMOKE_MODEL")
fi
if [[ "$SKIP_FUNCTIONAL_SMOKE" == "1" ]]; then
  VALIDATE_ARGS+=(--skip-functional-smoke)
fi
python scripts/validate_edge_environment.py "${VALIDATE_ARGS[@]}"

if [[ "$MODE" == "ops" ]]; then
  echo "[edge-smoke] running sample release path"
  make edge-release-example RUN_ID="$RUN_ID" ARTIFACTS_DIR="$ARTIFACTS_DIR" MPLCONFIGDIR="$MPLCONFIGDIR" XDG_CACHE_HOME="$XDG_CACHE_HOME"
fi

echo "[edge-smoke] complete"
