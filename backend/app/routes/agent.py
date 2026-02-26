from __future__ import annotations

from typing import Any

from backend.app.config import API_PREFIX, PHASE6_FLAGS
from backend.app.models import AgentToolInvokeRequest
from backend.app.utils import corr, idempotency_get, idempotency_put, rate_limit_or_raise
from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.get(f"{API_PREFIX}/agent/tools")
def list_agent_tools(request: Request) -> dict[str, Any]:
    tools = [
        {"name": "run_preprocessing", "description": "Trigger preprocessing pipeline run."},
        {"name": "run_training", "description": "Trigger training run."},
        {"name": "run_inference", "description": "Trigger inference run."},
        {"name": "get_run_status", "description": "Read current run/job status."},
    ]
    return {"ok": True, "data": {"tools": tools, "correlation": corr(request)}}


@router.post(f"{API_PREFIX}/agent/tools:invoke")
def invoke_agent_tool(payload: AgentToolInvokeRequest, request: Request) -> dict[str, Any]:
    rate_limit_or_raise(key=f"agent:{request.client.host if request.client else 'local'}", limit=60, window_sec=60)
    idem_key = request.headers.get("x-idempotency-key")
    if idem_key:
        cached = idempotency_get(f"agent:{idem_key}")
        if cached:
            return cached

    supported = {"run_preprocessing", "run_training", "run_inference", "get_run_status"}
    if payload.tool not in supported:
        raise HTTPException(status_code=400, detail="unsupported tool")

    response = {
        "ok": True,
        "data": {
            "tool": payload.tool,
            "accepted": True,
            "result": {
                "message": "tool accepted",
                "arguments": payload.arguments,
            },
            "correlation": corr(request),
        },
    }

    if idem_key:
        idempotency_put(f"agent:{idem_key}", response)
    return response


@router.get(f"{API_PREFIX}/mcp/capabilities")
def mcp_capabilities(request: Request) -> dict[str, Any]:
    if not PHASE6_FLAGS["enable_mcp"]:
        raise HTTPException(status_code=503, detail="mcp disabled")
    return {
        "ok": True,
        "data": {
            "server": "spline-forecast-mcp",
            "version": "phase6.v1",
            "tools": [
                {
                    "name": "run_preprocessing",
                    "input_schema": {"type": "object", "properties": {"run_id": {"type": "string"}}},
                },
                {
                    "name": "run_training",
                    "input_schema": {"type": "object", "properties": {"run_id": {"type": "string"}}},
                },
                {
                    "name": "run_inference",
                    "input_schema": {"type": "object", "properties": {"run_id": {"type": "string"}}},
                },
                {
                    "name": "get_run_status",
                    "input_schema": {"type": "object", "properties": {"job_id": {"type": "string"}}},
                },
                {
                    "name": "list_artifacts",
                    "input_schema": {"type": "object", "properties": {"run_id": {"type": "string"}}},
                },
                {
                    "name": "compare_runs",
                    "input_schema": {
                        "type": "object",
                        "properties": {"base_run_id": {"type": "string"}, "candidate_run_id": {"type": "string"}},
                    },
                },
            ],
            "correlation": corr(request),
        },
    }
