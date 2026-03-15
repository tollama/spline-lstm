# Edge Air-Gapped Runbook

This runbook covers offline or restricted-network deployment for edge-focused `spline-lstm` nodes.

## 1. Build the wheelhouse on a connected machine

Use the repo-managed profile requirement files so the wheelhouse matches the supported edge install modes.

```bash
# all edge profiles
make edge-wheelhouse-build

# one profile only
make edge-wheelhouse-build MODE=ops
make edge-wheelhouse-build MODE=benchmark-onnx
make edge-wheelhouse-build MODE=train-export
```

This wraps [scripts/build_edge_wheelhouse.sh](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/scripts/build_edge_wheelhouse.sh) and downloads wheels for:

- [requirements-edge-ops.txt](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/requirements-edge-ops.txt)
- [requirements-edge-runtime.txt](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/requirements-edge-runtime.txt)
- [requirements-edge-train-export.txt](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/requirements-edge-train-export.txt)

It also builds a wheel for the project itself and places everything under `wheelhouse-edge/` by default.

## 2. Transfer artifacts to the edge node

Copy to the node:

- the wheelhouse directory
- this repository checkout, or at minimum the validation/install scripts if you only need the wheel install path
- any exported model artifacts you want to benchmark or serve

## 3. Install from the wheelhouse on the edge node

```bash
# ops-only node
make edge-wheelhouse-install MODE=ops WHEELHOUSE_DIR=/opt/spline/wheelhouse-edge

# ONNX benchmark node
make edge-wheelhouse-install MODE=benchmark-onnx WHEELHOUSE_DIR=/opt/spline/wheelhouse-edge

# full train/export node
make edge-wheelhouse-install MODE=train-export WHEELHOUSE_DIR=/opt/spline/wheelhouse-edge
```

This wraps [scripts/install_edge_from_wheelhouse.sh](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/scripts/install_edge_from_wheelhouse.sh), which:

1. creates a fresh venv
2. installs dependencies with `--no-index --find-links`
3. installs the built `spline-lstm` wheel
4. runs [scripts/validate_edge_environment.py](/Users/yongchoelchoi/Documents/TollamaAI-Github/spline-lstm/scripts/validate_edge_environment.py) unless `SKIP_VALIDATE=1`

Useful overrides:

- `VENV_DIR=/opt/spline/.venv-edge`
- `CACHE_ROOT=/var/tmp/spline-cache`
- `ARTIFACTS_DIR=/var/lib/spline/artifacts`
- `SKIP_FUNCTIONAL_SMOKE=1` if you only want import/path validation

## 4. Validate node capability

You can also run the validator directly:

```bash
python3 scripts/validate_edge_environment.py --mode ops --artifacts-dir /var/lib/spline/artifacts
python3 scripts/validate_edge_environment.py --mode benchmark-onnx --artifacts-dir /var/lib/spline/artifacts
python3 scripts/validate_edge_environment.py --mode train-export --artifacts-dir /var/lib/spline/artifacts
```

Recommended flags for constrained nodes:

```bash
python3 scripts/validate_edge_environment.py \
  --mode ops \
  --artifacts-dir /var/lib/spline/artifacts \
  --cache-root /var/tmp/spline-cache \
  --min-free-disk-mb 512 \
  --min-total-memory-mb 1024
```

Notes:

- `ops` mode runs CLI smoke for `ingest_edge_device_bench.py` and `edge_release_gate.py`
- `benchmark-onnx` mode verifies `onnxruntime` and available execution providers
- add `--onnx-smoke-model /path/to/model.onnx` if you want the validator to execute a real ONNX inference pass
- `train-export` mode performs a tiny TensorFlow -> TFLite/ONNX export and runtime parity smoke

## 5. Optional clean-venv smoke flow

If the node still has access to the wheelhouse and a writable workspace, you can run the full clean-environment smoke script:

```bash
make edge-smoke-env MODE=ops WHEELHOUSE_DIR=/opt/spline/wheelhouse-edge
make edge-smoke-env MODE=benchmark-onnx WHEELHOUSE_DIR=/opt/spline/wheelhouse-edge
make edge-smoke-env MODE=train-export WHEELHOUSE_DIR=/opt/spline/wheelhouse-edge
```

## 6. Promotion-path verification

For an ops node, the fastest end-to-end check after install is:

```bash
RUN_ID=edge-offline-smoke-001 make edge-release-example
```

For a real deployment, the final required step is still to run the exported model and ingest actual device/runtime measurements from the target edge environment.
