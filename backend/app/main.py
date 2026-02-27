"""Spline-LSTM backend application entry point.

Creates the FastAPI app, wires middleware, exception handlers, and includes
all route modules. Module-level singletons (store, executor) are created here
so that route handlers can import them via lazy imports.
"""

from __future__ import annotations

import uuid

from backend.app.config import _REQUEST_ID, API_PREFIX, SECURITY, STORE_PATH, logger
from backend.app.executor import JobExecutor
from backend.app.routes import agent, forecast, health, jobs, runs, tollama
from backend.app.store import JobRecord, JobStore  # noqa: F401 - re-exported for backward compat
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------
store = JobStore(STORE_PATH)
executor = JobExecutor(store)

# ---------------------------------------------------------------------------
# App creation
# ---------------------------------------------------------------------------
app = FastAPI(title="spline-lstm backend skeleton", version="0.2.0")
app.state.store = store
app.state.executor = executor

if SECURITY["trusted_hosts"]:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=SECURITY["trusted_hosts"])
if SECURITY["cors_origins"]:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=SECURITY["cors_origins"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-API-Token"],
        max_age=600,
    )

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


@app.middleware("http")
async def _security_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or f"req-{uuid.uuid4().hex[:12]}"
    token = _REQUEST_ID.set(request_id)
    request.state.request_id = request_id
    try:
        path = request.url.path
        if path.startswith(API_PREFIX) and path != f"{API_PREFIX}/health" and SECURITY["auth_required"]:
            token_header = request.headers.get("x-api-token")
            if token_header != SECURITY["api_token"]:
                return JSONResponse(status_code=401, content={"ok": False, "error": "unauthorized"})

        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["x-request-id"] = request_id
        return response
    finally:
        _REQUEST_ID.reset(token)


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------


@app.exception_handler(HTTPException)
async def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if exc.status_code >= 500:
        logger.exception("HTTPException path=%s detail=%s", request.url.path, exc.detail)
        return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": "internal server error"})
    return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": exc.detail})


@app.exception_handler(RequestValidationError)
async def _validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    logger.warning("Validation error path=%s detail=%s", request.url.path, exc.errors())
    return JSONResponse(status_code=422, content={"ok": False, "error": "invalid request"})


@app.exception_handler(Exception)
async def _generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error path=%s", request.url.path)
    return JSONResponse(status_code=500, content={"ok": False, "error": "internal server error"})


# ---------------------------------------------------------------------------
# Include routers
# ---------------------------------------------------------------------------
app.include_router(health.router)
app.include_router(jobs.router)
app.include_router(forecast.router)
app.include_router(agent.router)
app.include_router(tollama.router)
app.include_router(runs.router)
