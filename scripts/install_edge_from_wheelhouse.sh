#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${MODE:-ops}"
WHEELHOUSE_DIR="${WHEELHOUSE_DIR:-${ROOT_DIR}/wheelhouse-edge}"
VENV_DIR="${VENV_DIR:-${ROOT_DIR}/.venv-edge-offline}"
CACHE_ROOT="${CACHE_ROOT:-/tmp/xdg-cache-spline-edge-offline}"
ARTIFACTS_DIR="${ARTIFACTS_DIR:-${ROOT_DIR}/artifacts-edge-offline}"
SKIP_VALIDATE="${SKIP_VALIDATE:-0}"
SKIP_FUNCTIONAL_SMOKE="${SKIP_FUNCTIONAL_SMOKE:-0}"

usage() {
  cat <<EOF
Usage: bash scripts/install_edge_from_wheelhouse.sh [--mode ops|benchmark-onnx|train-export] [--wheelhouse-dir PATH] [--venv-dir PATH] [--cache-root PATH] [--artifacts-dir PATH] [--skip-validate]

Install spline-lstm edge profiles from a prebuilt offline wheelhouse.
EOF
}

requirements_file_for_mode() {
  case "$1" in
    ops) echo "requirements-edge-ops.txt" ;;
    benchmark-onnx) echo "requirements-edge-runtime.txt" ;;
    train-export) echo "requirements-edge-train-export.txt" ;;
    *)
      echo "unsupported mode: $1" >&2
      exit 2
      ;;
  esac
}

validate_mode_for_mode() {
  case "$1" in
    ops) echo "ops" ;;
    benchmark-onnx) echo "benchmark-onnx" ;;
    train-export) echo "train-export" ;;
    *)
      echo "unsupported mode: $1" >&2
      exit 2
      ;;
  esac
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="$2"
      shift 2
      ;;
    --wheelhouse-dir)
      WHEELHOUSE_DIR="$2"
      shift 2
      ;;
    --venv-dir)
      VENV_DIR="$2"
      shift 2
      ;;
    --cache-root)
      CACHE_ROOT="$2"
      shift 2
      ;;
    --artifacts-dir)
      ARTIFACTS_DIR="$2"
      shift 2
      ;;
    --skip-validate)
      SKIP_VALIDATE="1"
      shift
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

REQ_FILE="$(requirements_file_for_mode "$MODE")"
VALIDATE_MODE="$(validate_mode_for_mode "$MODE")"

if [[ ! -d "$WHEELHOUSE_DIR" ]]; then
  echo "wheelhouse not found: $WHEELHOUSE_DIR" >&2
  exit 2
fi

PACKAGE_WHEEL="$(find "$WHEELHOUSE_DIR" -maxdepth 1 -type f -name 'spline_lstm-*.whl' | sort | tail -n 1)"
if [[ -z "$PACKAGE_WHEEL" ]]; then
  echo "spline-lstm wheel not found in wheelhouse: $WHEELHOUSE_DIR" >&2
  exit 2
fi

rm -rf "$VENV_DIR"
mkdir -p "$CACHE_ROOT" "$ARTIFACTS_DIR"

echo "[edge-offline] creating venv: $VENV_DIR"
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

export MPLCONFIGDIR="${CACHE_ROOT}/matplotlib"
export XDG_CACHE_HOME="${CACHE_ROOT}"
mkdir -p "$MPLCONFIGDIR"

echo "[edge-offline] installing dependencies from wheelhouse"
python -m pip install --no-index --find-links "$WHEELHOUSE_DIR" -r "$ROOT_DIR/$REQ_FILE"

echo "[edge-offline] installing spline-lstm wheel"
python -m pip install --no-index --find-links "$WHEELHOUSE_DIR" "$PACKAGE_WHEEL"

if [[ "$SKIP_VALIDATE" != "1" ]]; then
  VALIDATE_ARGS=(
    --mode "$VALIDATE_MODE"
    --cache-root "$CACHE_ROOT"
    --artifacts-dir "$ARTIFACTS_DIR"
  )
  if [[ "$SKIP_FUNCTIONAL_SMOKE" == "1" ]]; then
    VALIDATE_ARGS+=(--skip-functional-smoke)
  fi
  echo "[edge-offline] validating installed environment"
  python "$ROOT_DIR/scripts/validate_edge_environment.py" "${VALIDATE_ARGS[@]}"
fi

echo "[edge-offline] complete"
