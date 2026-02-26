from __future__ import annotations

from typing import Any

from backend.app.config import PHASE6_FLAGS
from backend.app.models import TollamaChatRequest, TollamaGenerateRequest
from backend.app.utils import jsonl_stream, rate_limit_or_raise, utc_now_iso
from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/api/tags")
def tollama_tags() -> dict[str, Any]:
    return {
        "models": [
            {
                "name": "spline-lstm:latest",
                "model": "spline-lstm",
                "modified_at": utc_now_iso(),
                "size": 0,
                "digest": "sha256:spline-lstm-phase6",
                "details": {"family": "lstm", "format": "keras"},
            }
        ]
    }


@router.post("/api/generate")
def tollama_generate(payload: TollamaGenerateRequest):
    if not PHASE6_FLAGS["enable_tollama_adapter"]:
        raise HTTPException(status_code=503, detail="tollama adapter disabled")
    rate_limit_or_raise(key="tollama:generate", limit=120, window_sec=60)
    response_text = (
        "[spline-lstm] Forecast assistant ready. "
        "Use /api/v1/forecast/preview for adjusted covariate what-if simulation. "
        f"Prompt echo: {payload.prompt[:120]}"
    )
    final = {
        "model": payload.model,
        "created_at": utc_now_iso(),
        "response": response_text,
        "done": True,
    }
    if payload.stream:
        return jsonl_stream(
            [
                {"model": payload.model, "created_at": utc_now_iso(), "response": response_text[:48], "done": False},
                final,
            ]
        )
    return final


@router.post("/api/chat")
def tollama_chat(payload: TollamaChatRequest):
    if not PHASE6_FLAGS["enable_tollama_adapter"]:
        raise HTTPException(status_code=503, detail="tollama adapter disabled")
    rate_limit_or_raise(key="tollama:chat", limit=120, window_sec=60)
    user_messages = [m.get("content", "") for m in payload.messages if m.get("role") == "user"]
    last_user = user_messages[-1] if user_messages else ""
    final = {
        "model": payload.model,
        "created_at": utc_now_iso(),
        "message": {
            "role": "assistant",
            "content": f"[spline-lstm] received: {last_user[:120]}",
        },
        "done": True,
    }
    if payload.stream:
        return jsonl_stream(
            [
                {
                    "model": payload.model,
                    "created_at": utc_now_iso(),
                    "message": {"role": "assistant", "content": "[spline-lstm] thinking..."},
                    "done": False,
                },
                final,
            ]
        )
    return final
