# Phase 6 Plan: Forecasting + Agent Ecosystem Expansion

## 1) Goal Summary

This plan extends the current spline+LSTM stack beyond the Phase 5 PoC and prepares it for production-like pilot use.

Primary goals:

1. Support **covariates** end-to-end for forecasting (train + infer + serving).
2. Provide a **user-adjustable input control path** so operators can inspect and modify selected inputs before execution.
3. Expose reusable **Skill / MCP capabilities** so other AI agents can orchestrate forecasting workflows.
4. Implement API compatibility with **Tollama** style contract (`https://github.com/tollama/tollama`).
5. Define **pilot stability strategy** (safety, rollback, observability, SLO gates).

---

## 2) Workstream A — Covariate Forecasting (Core ML)

### A.1 Scope

- Expand current multivariate preprocessing PoC into stable contract:
  - historical covariates
  - known-future covariates (calendar/event/promo etc.)
  - optional dynamic/static feature split
- Training/inference parity for feature ordering and shape guarantees.

### A.2 Deliverables

1. **Data contract v2**
   - `covariate_schema` with type, nullability, source, known_future flag
   - strict feature ordering persisted in artifact metadata
2. **Model input spec v2**
   - explicit tensor mapping (`target`, `cov_hist`, `cov_future`, optional static)
3. **Inference guardrails**
   - fail-fast when serving payload lacks required covariates
   - warning path for optional covariates with fallback policy
4. **Backtest enhancements**
   - evaluate target-only vs covariate-enabled uplift

### A.3 Milestones

- M1: Data contract draft + fixtures + parser validation [✅]
- M2: Trainer/runner integration + reproducibility checks [✅]
- M3: Inference API payload validation + regression suite [✅]

### A.4 Acceptance criteria

- [x] Same run with same seed + same covariate payload produces reproducible metrics within tolerance.
- [x] Contract tests cover missing/extra/reordered covariates.
- [x] Model registry metadata contains covariate lineage for audit.

---

## 3) Workstream B — User-adjustable Inputs (Human-in-the-loop)

### B.1 Scope

Provide a controllable pre-run input layer where users can inspect and adjust specific values before forecast execution.

### B.2 Product behavior

- Add endpoint/UI flow for:
  1. loading baseline input snapshot,
  2. applying patch operations on selected fields,
  3. previewing impact-ready payload,
  4. submitting signed execution request.
- Keep immutable audit trail of:
  - original value,
  - adjusted value,
  - actor,
  - reason,
  - timestamp,
  - run_id/job_id linkage.

### B.3 Technical deliverables

1. `input_patch` schema (JSON Patch subset + domain constraints)
2. dry-run validation endpoint (`/validate-inputs`)
3. scenario preview endpoint (`/forecast/preview`)
4. policy engine:
   - allowed fields
   - value bounds
   - approval requirement for high-risk fields

### B.4 Acceptance criteria

- Unauthorized or out-of-policy edits are blocked.
- All accepted edits are traceable and replayable.
- Preview and final execution payload hashes are recorded.

---

## 4) Workstream C — Skill/MCP Capability for Other Agents

### C.1 Scope

Expose the platform as reusable agent tools.

### C.2 Capability model

- **Skill package** (`skills/forecast-ops`) for scripted workflows:
  - dataset validation
  - preprocessing run trigger
  - train/eval/infer orchestration
  - artifact lookup and summary
- **MCP server** (`mcp_forecast`) for structured tool calls:
  - `run_preprocessing`
  - `run_training`
  - `run_inference`
  - `get_run_status`
  - `list_artifacts`
  - `compare_runs`

### C.3 Non-functional requirements

- Idempotent tool invocations with request IDs.
- Rate limiting and auth for agent clients.
- Structured error taxonomy (retryable vs terminal).

### C.4 Acceptance criteria

- At least one external agent can complete end-to-end run using only MCP tool calls.
- Tool contracts versioned and published with examples.

---

## 5) Workstream D — Tollama-compatible API Layer

### D.1 Scope

Provide compatibility adapter so clients expecting Tollama-like API can call this backend with minimal changes.

### D.2 Implementation approach

- Build an **adapter router**:
  - Tollama-compatible request/response envelope
  - internal mapping to existing `/api/v1` jobs + inference pipeline
- Preserve native API while adding compatibility namespace.

### D.3 Compatibility matrix (initial)

1. `POST /api/generate` (sync or streamed response mode)
2. `POST /api/chat` (if supported by Tollama contract)
3. model listing / metadata endpoint
4. health endpoint parity

> Final endpoint names/payload fields must be validated against the upstream Tollama spec during implementation.

### D.4 Acceptance criteria

- Golden contract tests prove payload parity for required endpoints.
- Backward compatibility for existing `/api/v1` clients is maintained.

---

## 6) Workstream E — Pilot Stability & Safety Strategy

### E.1 Reliability layers

- **Progressive rollout**: shadow -> canary -> partial -> full.
- **Kill-switches**:
  - disable covariate path
  - disable user-input patching
  - disable Tollama adapter
- **Fallback modes**:
  - target-only baseline forecast
  - previous stable model pin

### E.2 Observability

- Unified tracing keys: `request_id`, `run_id`, `job_id`, `model_version`.
- SLO dashboards:
  - success rate
  - p95 latency
  - failure class distribution
  - forecast drift indicators
- Data quality alerts for covariate freshness/completeness.

### E.3 Operational governance

- Runbook updates for incident response.
- On-call severity matrix and rollback playbook.
- Weekly pilot review with risk register updates.

### E.4 Exit criteria for pilot -> broader rollout

- SLO compliance for 2 consecutive weeks.
- No unresolved Sev-1 / Sev-2 defects in forecast critical path.
- All guardrail tests green in release gate.

---

## 7) Execution Roadmap (8 weeks)

- **Week 1-2:** contract design (covariates, input patching, MCP tool specs, Tollama mapping)
- **Week 3-4:** backend implementation + adapter skeleton + validation endpoints
- **Week 5-6:** integration tests, regression hardening, observability and rollback hooks
- **Week 7:** pilot shadow/canary with selected traffic
- **Week 8:** stabilization, docs closeout, go/no-go review

---

## 8) Risk Register (Top items)

1. **Schema drift risk** for covariates across train/serve
   - Mitigation: strict schema hash + payload validator
2. **Unsafe manual adjustments** by users
   - Mitigation: policy engine + approvals + immutable audit log
3. **API mismatch with Tollama clients**
   - Mitigation: contract test suite against captured fixtures
4. **Agent misuse / runaway automation**
   - Mitigation: scoped auth tokens, quotas, idempotency keys
5. **Pilot instability under burst load**
   - Mitigation: queue controls, backpressure, staged rollout

---

## 9) Definition of Done (Phase 6)

- Covariate forecasting path is production-ready with tested contracts.
- Human-adjustable input workflow is secure and auditable.
- External agents can run standardized workflows through Skill/MCP tools.
- Tollama-compatible API contract passes required parity suite.
- Pilot reliability targets and rollback readiness are proven.
