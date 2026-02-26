from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    run_id: str | None = None
    runId: str | None = None
    model_type: str | None = None
    model: str | None = None
    feature_mode: str | None = "univariate"
    model_config_payload: dict[str, Any] | None = Field(default=None, alias="model_config")


class InputPatchOperation(BaseModel):
    op: str = Field(pattern="^(replace|add)$")
    path: str
    value: Any
    reason: str | None = None


class ForecastInputRequest(BaseModel):
    run_id: str
    actor: str | None = "anonymous"
    base_inputs: dict[str, Any]
    patches: list[InputPatchOperation] = Field(default_factory=list)


class AgentToolInvokeRequest(BaseModel):
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ForecastExecuteAdjustedRequest(ForecastInputRequest):
    model_type: str | None = "lstm"
    feature_mode: str | None = "multivariate"


class CovariateFieldSpec(BaseModel):
    name: str
    type: str = Field(pattern="^(numeric|categorical|boolean)$")
    required: bool = True
    known_future: bool = False
    source: str | None = None


class CovariateContractValidateRequest(BaseModel):
    covariate_schema: list[CovariateFieldSpec]
    payload: dict[str, Any]
    strict_order: bool = True


class TollamaGenerateRequest(BaseModel):
    model: str
    prompt: str
    stream: bool | None = False


class TollamaChatRequest(BaseModel):
    model: str
    messages: list[dict[str, Any]]
    stream: bool | None = False
