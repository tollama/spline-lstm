from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def _sample_payload() -> dict:
    return {
        "run_id": "phase6-sample-001",
        "actor": "tester",
        "base_inputs": {
            "horizon": 2,
            "target_history": [10.0, 11.5, 12.0],
            "known_future_covariates": {"promo": [0, 1]},
            "static_covariates": {"store_type": "A"},
        },
        "patches": [
            {"op": "replace", "path": "/known_future_covariates/promo/1", "value": 2, "reason": "what-if"}
        ],
    }


def test_phase6_validate_and_preview_contract() -> None:
    payload = _sample_payload()

    validate = client.post("/api/v1/forecast/validate-inputs", json=payload)
    assert validate.status_code == 200
    body = validate.json()["data"]
    assert body["valid"] is True
    assert body["input_hash_before"] != body["input_hash_after"]

    preview = client.post("/api/v1/forecast/preview", json=payload)
    assert preview.status_code == 200
    pdata = preview.json()["data"]
    assert pdata["run_id"] == payload["run_id"]
    assert len(pdata["preview"]) == payload["base_inputs"]["horizon"]


def test_phase6_validate_rejects_disallowed_path() -> None:
    payload = _sample_payload()
    payload["patches"] = [{"op": "replace", "path": "/model_type", "value": "gru"}]

    response = client.post("/api/v1/forecast/validate-inputs", json=payload)
    assert response.status_code == 400


def test_phase6_agent_tool_and_tollama_endpoints() -> None:
    tools = client.get("/api/v1/agent/tools")
    assert tools.status_code == 200
    names = {item["name"] for item in tools.json()["data"]["tools"]}
    assert "run_training" in names

    invoke = client.post("/api/v1/agent/tools:invoke", json={"tool": "run_inference", "arguments": {"run_id": "r1"}})
    assert invoke.status_code == 200
    assert invoke.json()["data"]["accepted"] is True

    mcp = client.get("/api/v1/mcp/capabilities")
    assert mcp.status_code == 200
    assert mcp.json()["data"]["server"] == "spline-forecast-mcp"

    tags = client.get("/api/tags")
    assert tags.status_code == 200
    assert tags.json()["models"][0]["name"] == "spline-lstm:latest"

    gen = client.post("/api/generate", json={"model": "spline-lstm:latest", "prompt": "hello", "stream": False})
    assert gen.status_code == 200
    assert gen.json()["done"] is True

    chat = client.post(
        "/api/chat",
        json={
            "model": "spline-lstm:latest",
            "messages": [{"role": "user", "content": "run preview"}],
            "stream": False,
        },
    )
    assert chat.status_code == 200
    assert chat.json()["message"]["role"] == "assistant"


def test_phase6_execute_adjusted_and_streaming_contract() -> None:
    payload = _sample_payload()
    execute = client.post("/api/v1/forecast/execute-adjusted", json=payload)
    assert execute.status_code == 200
    data = execute.json()["data"]
    assert data["status"] == "queued"
    assert data["adjusted_input_ref"].endswith(".adjusted.json")

    stream_generate = client.post(
        "/api/generate",
        json={"model": "spline-lstm:latest", "prompt": "stream this", "stream": True},
    )
    assert stream_generate.status_code == 200
    assert "application/x-ndjson" in stream_generate.headers.get("content-type", "")
    chunks = [line for line in stream_generate.text.splitlines() if line.strip()]
    assert len(chunks) >= 2
