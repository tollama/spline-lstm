#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${MODE:-all}"
WHEELHOUSE_DIR="${WHEELHOUSE_DIR:-${ROOT_DIR}/wheelhouse-edge}"
CLEAN="${CLEAN:-0}"

usage() {
  cat <<EOF
Usage: bash scripts/build_edge_wheelhouse.sh [--mode ops|benchmark-onnx|train-export|all] [--wheelhouse-dir PATH] [--clean]

Build an offline wheelhouse for spline-lstm edge deployment profiles.
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
    --clean)
      CLEAN="1"
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

if [[ "$CLEAN" == "1" ]]; then
  rm -rf "$WHEELHOUSE_DIR"
fi
mkdir -p "$WHEELHOUSE_DIR"

if [[ "$MODE" == "all" ]]; then
  MODES=(ops benchmark-onnx train-export)
else
  MODES=("$MODE")
fi

for profile in "${MODES[@]}"; do
  req_file="$(requirements_file_for_mode "$profile")"
  echo "[edge-wheelhouse] downloading deps for mode=$profile from $req_file"
  python3 -m pip download -r "$ROOT_DIR/$req_file" -d "$WHEELHOUSE_DIR"
done

echo "[edge-wheelhouse] building project wheel"
python3 -m pip wheel "$ROOT_DIR" --no-deps -w "$WHEELHOUSE_DIR"

echo "[edge-wheelhouse] complete: $WHEELHOUSE_DIR"
