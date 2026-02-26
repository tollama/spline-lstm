# RELEASE CHECKLIST (Final RC)

Date: 2026-02-20 (KST)  
Project: `spline-lstm`

Use this checklist for final pre-release verification.

Related docs:
- Project overview: `README.md`
- Operator quick map: `OPERATIONS_QUICKSTART.md`
- Detailed operations/run_id policy: `docs/RUNBOOK.md`
- GUI production hardening closeout: `docs/GUI_PROD_HARDENING_CLOSEOUT.md`

## 1) Pre-release environment checks
- [ ] Python available: `python3 --version`
- [ ] Dependencies installed: `python3 -m pip install -r requirements.txt`
- [ ] Clean working tree or reviewed local diffs: `git status --short`
- [ ] Required dirs writable: `artifacts/`, `logs/`

## 2) Required quality gates

### A. Full regression
- [ ] Run: `python3 -m pytest -q`
- [ ] Expected: all tests pass (or only explicitly accepted skips)

### B. Core smoke gate (artifact + schema + checkpoint)
- [ ] Run:
  ```bash
  RUN_ID=release-smoke-$(date +%Y%m%d-%H%M%S) EPOCHS=1 bash scripts/smoke_test.sh
  ```
- [ ] Expected: `[SMOKE][OK] all checks passed`
- [ ] Confirm artifacts created:
  - `artifacts/metrics/<RUN_ID>.json`
  - `artifacts/reports/<RUN_ID>.md`
  - `artifacts/reports/<RUN_ID>_smoke_validation.md`
  - `artifacts/checkpoints/<RUN_ID>/best.keras`

### C. Phase5 compare smoke
- [ ] Run:
  ```bash
  RUN_ID=release-compare-$(date +%Y%m%d-%H%M%S) EPOCHS=1 bash scripts/run_compare.sh
  ```
- [ ] Confirm comparison artifacts:
  - `artifacts/comparisons/<RUN_ID>.json`
  - `artifacts/comparisons/<RUN_ID>.md`

## 3) One-command verifier (recommended)
- [ ] Run: `bash scripts/pre_release_verify.sh`
- [ ] Review summary section: all checks must be `PASS`
- [ ] Preserve generated log for release evidence

## 4) Artifact sanity checklist
- [ ] All generated artifact paths include matching `run_id`
- [ ] No missing required files in metrics/reports/checkpoints/comparisons
- [ ] `best.keras` exists for smoke run
- [ ] Logs exist under `logs/` for each gate execution

## 5) Release notes & quality report consistency
- [ ] `RELEASE_NOTES.md` and `docs/DAY5_FINAL_QUALITY_REPORT.md` both state:
  - regression PASS
  - smoke PASS
  - compare PASS
  - blockers: none
  - recommendation: GO

## 6) Rollback steps (operator runbook)
1. Stop using the problematic new `run_id`.
2. Restore last known-good artifacts:
   - `artifacts/processed/<run_id>/...`
   - `artifacts/models/<run_id>/preprocessor.pkl`
   - `artifacts/checkpoints/<run_id>/best.keras`
3. Re-run baseline validation:
   ```bash
   python3 -m pytest -q
   RUN_ID=rollback-smoke-$(date +%Y%m%d-%H%M%S) EPOCHS=1 bash scripts/smoke_test.sh
   ```
4. If needed, run core path without Phase5-specific options until fixed.

## 7) Final release decision
- [ ] GO only if all required gates are green and no release-blocking defects are open.
