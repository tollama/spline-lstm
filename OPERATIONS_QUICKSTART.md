# OPERATIONS QUICKSTART

Minimal day-2 command map for operators.

## Command map

- **quick gate (fast confidence check)**
  - `make quick-gate`
  - Runs smoke gate + targeted runner/health pytest checks.
- **smoke gate (artifact contract check)**
  - `make smoke-gate`
  - Runs `scripts/smoke_test.sh` only.
- **full regression**
  - `make full-regression`
  - Runs full `pytest` suite.
- **pre-release verification**
  - `make pre-release-verify`
  - Runs regression + smoke + compare with one summary log.

## Typical usage

```bash
# default quick gate
make quick-gate

# explicit run id / faster epochs
RUN_ID=ops-quick-001 EPOCHS=1 make smoke-gate

# full regression with optional extra args
PYTEST_ARGS="-k phase5 -x" make full-regression

# release dry run
RUN_ID_PREFIX=rc EPOCHS=1 make pre-release-verify
```

## Troubleshooting pointers

- **Smoke failed with missing artifacts**
  - Check `logs/` and `artifacts/logs/<run_id>.*.log`
  - Re-run with explicit run id:
    - `RUN_ID=debug-<ts> make smoke-gate`
- **run_id mismatch / contract failure**
  - Ensure same run id is used across `processed.npz`, `meta.json`, `preprocessor.pkl`, and runner args.
  - See: `docs/RUNBOOK.md` section on run_id mismatch guard.
- **Training/runtime import errors**
  - Reinstall deps: `python3 -m pip install -r requirements.txt`
  - Confirm Python version is 3.10–3.11.
- **Pre-release verify reports NO-GO**
  - Open latest `logs/pre-release-verify-*.log`
  - Fix failed step(s), then re-run `make pre-release-verify`.

## Artifact map (run_id scoped)

- Preprocess arrays: `artifacts/processed/<run_id>/processed.npz`
- Preprocess metadata: `artifacts/processed/<run_id>/meta.json`
- Preprocessor object: `artifacts/models/<run_id>/preprocessor.pkl`
- Model checkpoints: `artifacts/checkpoints/<run_id>/best.keras`, `last.keras`
- Metrics: `artifacts/metrics/<run_id>.json`
- Report: `artifacts/reports/<run_id>.md`
- Smoke validation: `artifacts/reports/<run_id>_smoke_validation.md`
- Compare outputs: `artifacts/comparisons/<run_id>.json`, `.md`
- Verify summary log: `logs/pre-release-verify-<timestamp>.log`

## Related docs

- Project entry: `README.md`
- Detailed operations: `docs/RUNBOOK.md`
- Release gate checklist: `RELEASE_CHECKLIST.md`
