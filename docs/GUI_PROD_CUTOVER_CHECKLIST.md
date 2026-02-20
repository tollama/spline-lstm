# GUI + Backend Production Cutover Checklist (No-gap, 1-page)

Scope: `ui/` (Vite React) + `backend/app/main.py` (FastAPI `/api/v1`).
Run from repo root: `cd /Users/ychoi/spline-lstm`

## 1) Preflight env vars (dev / prod-like)

### Backend (dev, auth optional)
```bash
export SPLINE_DEV_MODE=1
export SPLINE_BACKEND_EXECUTOR_MODE=mock
export SPLINE_BACKEND_ARTIFACTS_DIR=/Users/ychoi/spline-lstm/artifacts
```

### Backend (prod-like, auth required)
```bash
export SPLINE_DEV_MODE=0
export SPLINE_API_TOKEN='change-me'
export SPLINE_TRUSTED_HOSTS='localhost,127.0.0.1'
export SPLINE_CORS_ORIGINS='http://127.0.0.1:4173'
```

### UI (prod-like)
- `ui/.env.production`
  - `VITE_APP_PROFILE=prod`
  - `VITE_API_BASE_URL=/`
  - `VITE_USE_MOCK=false`

Preflight sanity:
```bash
test -f ui/.env.development && test -f ui/.env.production && echo "OK env files"
```

## 2) Startup commands (backend + ui build/preview)

### Backend start
```bash
# dev
SPLINE_DEV_MODE=1 python3 -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

# prod-like
SPLINE_DEV_MODE=0 SPLINE_API_TOKEN='change-me' \
  python3 -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

### UI build + preview
```bash
cd ui
npm run build
npm run preview -- --host 127.0.0.1 --port 4173
```

## 3) Health checks (expected responses)

```bash
# backend health (always 200)
curl -sS http://127.0.0.1:8000/api/v1/health
```
Expected: `{"ok": true, "data": {"status": "healthy", ...}}`

```bash
# ui preview reachable
curl -sS http://127.0.0.1:4173 | head -n 1
```
Expected: `<!doctype html>`

## 4) Auth verification (without/with token)

(when `SPLINE_DEV_MODE=0`)
```bash
# without token -> 401
curl -i http://127.0.0.1:8000/api/v1/dashboard/summary

# with token -> 200
curl -i -H 'X-API-Token: change-me' http://127.0.0.1:8000/api/v1/dashboard/summary
```
Expected:
- without token: `401` + `{"ok":false,"error":"unauthorized"}`
- with token: `200` + `{"ok":true,"data":...}`

## 5) E2E verification commands

```bash
# backend contract/security regression (fast)
python3 -m pytest -q tests/test_backend_security.py

# pipeline smoke gate (artifacts contract)
RUN_ID=cutover-$(date +%Y%m%d-%H%M%S) EPOCHS=1 bash scripts/smoke_test.sh

# gui smoke (requires UI preview on :4173)
cd ui && node gui_e2e_smoke.mjs
```

## 6) Rollback procedure (fast + safe)

### Fast rollback (service restore first)
1. Stop current backend/UI preview processes.
2. Restart backend in last-known-good safe mode:
```bash
SPLINE_DEV_MODE=1 python3 -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```
3. Serve last built UI from existing `ui/dist`:
```bash
cd ui && npm run preview -- --host 127.0.0.1 --port 4173
```

### Safe rollback (preserve evidence)
Before cutover, snapshot current build/artifacts:
```bash
TS=$(date +%Y%m%d-%H%M%S)
cp -a ui/dist ui/dist.rollback.$TS
cp -a artifacts artifacts.rollback.$TS
```
Rollback by restoring snapshot:
```bash
cp -a ui/dist.rollback.<TS> ui/dist
cp -a artifacts.rollback.<TS> artifacts
```

## 7) Incident triage flow (logs/artifacts/request_id)

1. **Confirm symptom**
```bash
curl -sS http://127.0.0.1:8000/api/v1/health
```
2. **Capture request_id** (client-provided or response header)
```bash
curl -sS -D /tmp/headers.txt -H 'x-request-id: cutover-incident-001' \
  http://127.0.0.1:8000/api/v1/dashboard/summary > /tmp/summary.json
```
3. **Trace by request_id**
- Response header: `x-request-id`
- API payload correlation: `data.correlation.request_id`
- Backend runtime logs (if redirected): `logs/*.log`

4. **Check run-scoped artifacts**
- `artifacts/metrics/<run_id>.json`
- `artifacts/reports/<run_id>.md`
- `artifacts/checkpoints/<run_id>/best.keras`
- `artifacts/models/<run_id>/preprocessor.pkl`

5. **If failed run**
```bash
python3 -m pytest -q tests/test_phase4_health_check.py
```
Then re-run smoke with a fresh run id and attach:
- failing command
- request_id
- `artifacts/reports/<run_id>_smoke_validation.md` (if generated)
- relevant `logs/*.log`
