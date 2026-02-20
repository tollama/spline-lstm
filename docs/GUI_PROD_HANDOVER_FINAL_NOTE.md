# GUI Production Handover Final Note

Date: 2026-02-20 (Asia/Seoul)
Scope: Final audit after cutover checklist landing

Related docs:
- `../README.md`
- `./RUNBOOK.md`
- `./GUI_PROD_HARDENING_CLOSEOUT.md`
- `../RELEASE_CHECKLIST.md` (cutover checklist)

## 1) Readiness checklist status

### A. Documentation cross-links (required)
- ✅ README ↔ RUNBOOK: linked
- ✅ README ↔ cutover checklist (`RELEASE_CHECKLIST.md`): linked
- ✅ README ↔ GUI hardening closeout: linked
- ✅ RUNBOOK ↔ cutover checklist: linked
- ✅ RUNBOOK ↔ GUI hardening closeout: linked
- ✅ GUI hardening closeout ↔ RUNBOOK/checklist/README: linked
- ✅ Cutover checklist ↔ RUNBOOK/README/GUI hardening closeout: linked

### B. Final acceptance test set (required)
- ✅ Backend minimal acceptance tests PASS
  - `python3 -m pytest -q tests/test_backend_api_contract.py tests/test_backend_security.py tests/test_backend_persistence_observability.py`
  - Result: `11 passed in 3.43s`
- ✅ UI minimal acceptance tests PASS
  - `cd ui && npm test -- --run`
  - Result: `6 passed (6 files), 25 passed (25 tests)`

## 2) Exact command set for operators (Day 1)

Run from repository root unless noted.

```bash
# 1) Environment sanity
python3 --version
python3 -m pip install -r requirements.txt

# 2) Backend contract/security/persistence acceptance
python3 -m pytest -q \
  tests/test_backend_api_contract.py \
  tests/test_backend_security.py \
  tests/test_backend_persistence_observability.py

# 3) UI contract-facing unit tests
(cd ui && npm ci && npm test -- --run)

# 4) Production-like backend start (auth required)
SPLINE_DEV_MODE=0 SPLINE_API_TOKEN=<set-secure-token> \
  uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

# 5) Health check (separate shell)
curl -s http://127.0.0.1:8000/api/v1/health

# 6) Optional one-command pre-release verification bundle
RUN_ID_PREFIX=day1-verify EPOCHS=1 bash scripts/pre_release_verify.sh
```

## 3) Remaining non-blocking risks

1. GUI smoke depth remains limited for deep route/state transitions.
2. Backend job orchestration is still contract-compliant skeleton scope, not full high-scale production orchestration.
3. Distributed queue/rate-limiting/persistent worker topology is not part of this cutover scope.

These are tracked as non-blocking for current production-like cutover scope.

## 4) Final GO statement

**GO** for production-like handover within the currently defined scope.

Rationale: required docs cross-links are consistent, and the minimal backend/UI acceptance set passed without failures.
