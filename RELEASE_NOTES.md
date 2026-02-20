# RELEASE NOTES — Sprint Day 5 (Final Regression + Release Candidate)

Date: 2026-02-20 (KST)
Project: `spline-lstm`
Release type: Sprint closure candidate (Phase 1~5 integrated)

## Summary
This sprint closes the end-to-end baseline and Phase 5 extension path with final regression re-validation.

- Core pipeline remains stable: preprocessing → runner train/eval/infer → artifact persistence
- Ops gates remain stable: one-click E2E + smoke validation + run_id mismatch guard
- Phase 5 extension path is release-candidate ready in PoC scope:
  - GRU comparison flow via `scripts/run_compare.sh`
  - multivariate/covariate preprocessing artifacts (`X_mv`, `y_mv`, feature metadata)
  - runner contract alignment for phase5-related options

## What changed (high level)
1. **Phase 4 operational hardening finalized**
   - `scripts/run_e2e.sh` and `scripts/smoke_test.sh` used as deployment gates
   - smoke validation report generation (`*_smoke_validation.md`)
   - run_id consistency guard enforced in runner/artifact paths

2. **Phase 5 PoC extension finalized**
   - model variant path expanded (LSTM/GRU/Attention-LSTM contracts)
   - comparison runner flow produces JSON/Markdown benchmark artifacts
   - multivariate preprocessing contract keys and metadata support added

3. **Documentation closure and gate evidence updated**
   - final gate/closure docs indicate full project completion status in latest closeout path

## Final regression & smoke evidence (Day 5)
### A) Full regression suite
- Command: `python3 -m pytest -q`
- Result: **PASS** — `75 passed, 2 skipped, 15 warnings in 24.32s`
- Log: `logs/day5-final-pytest-20260220-030251.log`

### B) Core smoke gate
- Command: `RUN_ID=day5-final-smoke-20260220-030319 EPOCHS=1 bash scripts/smoke_test.sh`
- Result: **PASS** (`[SMOKE][OK] all checks passed`)
- Artifacts:
  - `artifacts/metrics/day5-final-smoke-20260220-030319.json`
  - `artifacts/reports/day5-final-smoke-20260220-030319.md`
  - `artifacts/reports/day5-final-smoke-20260220-030319_smoke_validation.md`
  - `artifacts/checkpoints/day5-final-smoke-20260220-030319/best.keras`
- Log: `logs/day5-final-smoke-20260220-030319.log`

### C) Phase 5 compare smoke
- Command: `RUN_ID=day5-final-compare-20260220-030327 EPOCHS=1 bash scripts/run_compare.sh`
- Result: **PASS**
- Artifacts:
  - `artifacts/comparisons/day5-final-compare-20260220-030327.json`
  - `artifacts/comparisons/day5-final-compare-20260220-030327.md`
- Log: `logs/day5-final-compare-20260220-030327.log`

## Compatibility notes
- Backward compatibility is preserved for the default univariate path (`model_type=lstm`, `feature_mode=univariate`).
- Phase 5 capabilities are additive in current scope (PoC expansion path).
- Existing artifact contracts for Phase 1~4 runs remain valid.
- `python3 -m pytest` should be used in this environment (standalone `pytest` may not be on PATH).

## Known non-blocking warnings
Observed during regression/smoke runs (non-fatal in current gate results):
1. `urllib3` OpenSSL warning (`NotOpenSSLWarning`, LibreSSL in local Python build)
2. `matplotlib/pyparsing` deprecation warnings
3. TensorFlow `NodeDef ... use_unbounded_threadpool` attribute warning in compare smoke

Current assessment: warnings are **non-blocking** for this release candidate; no functional failures observed.

## Rollback guidance
If post-release regression is detected:

1. **Immediate containment**
   - Stop using affected new run_id
   - Re-run last known-good smoke path with stable settings (`EPOCHS=1`, baseline univariate)

2. **Artifact-level rollback**
   - Restore previous known-good run artifacts:
     - `artifacts/processed/<run_id>/...`
     - `artifacts/models/<run_id>/preprocessor.pkl`
     - `artifacts/checkpoints/<run_id>/best.keras`
   - Ensure `run_id` coherence across processed/meta/preprocessor/checkpoint inputs

3. **Execution-path rollback**
   - Use core runner flow without Phase5-specific options
   - Keep `--run-id-validation legacy` unless strict mode is explicitly required by release policy

4. **Verification after rollback**
   - `python3 -m pytest -q`
   - `RUN_ID=<rollback-smoke-id> EPOCHS=1 bash scripts/smoke_test.sh`

## Release operations addendum
- Canonical operator checklist: `RELEASE_CHECKLIST.md`
- One-command verifier: `bash scripts/pre_release_verify.sh`

## Release recommendation
**GO (Release Candidate acceptable)**

Rationale:
- Full regression suite green
- Core smoke gate green
- Phase 5 compare smoke green
- No blocking defects identified in Day 5 execution
