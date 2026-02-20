# Spline-LSTM Phase Execution Plan (Architect Report)

## 1) Phase map: explicit deliverables & acceptance criteria

## Phase 1 — Data Contract + Preprocessing Foundation
**Source:** `docs/PHASE1_ARCH.md`

**Explicit deliverables**
- Fixed data contract (`timestamp`, `target`, validation/fail-fast rules)
- Preprocessing I/O contract (`X:[N,L,1]`, `y:[N,H]`, float32)
- Artifact contract (processed/meta/split_index/preprocessor/run_id pathing)
- Scaler serialization contract (`schema_version=phase1.v1`)
- AC-aligned test set (AC-1..AC-8)

**Acceptance criteria (explicit)**
- AC-1..AC-8 in `PHASE1_ARCH.md`:
  - schema pass
  - missing column fail(code 2)
  - timestamp monotonic fail(code 3)
  - missing ratio fail(code 5)
  - window shape/dtype fixed
  - preprocessor load consistency
  - run_id path consistency
  - rerun invariance

---

## Phase 2 — LSTM Train/Eval/Infer MVP
**Source:** `docs/PHASE2_ARCH.md`

**Explicit deliverables**
- Model/trainer/inference interface contracts
- Artifact set: `best.keras`, `last.keras`, `metrics/{run_id}.json`, `reports/{run_id}.md` (추론 요약은 metrics/report 내 `inference` 필드)
- Runner CLI contract (현재 구현: 예외 기반 비0 종료)
- Metrics/report schema minimum fields

**Acceptance criteria (explicit)**
- AC-1..AC-7 in `PHASE2_ARCH.md`:
  - 1 CLI run yields required artifacts
  - best checkpoint policy fixed
  - run_id mismatch fails(code 27)
  - shape violation fails(code 23)
  - predictions CSV contract
  - reproducibility tolerance (RMSE ±5%)
  - report contains command/metrics/artifact paths

---

## Phase 3 — Baseline Comparison + Reproducibility Lock
**Source:** `docs/PHASE3_ARCH.md`

**Explicit deliverables**
- Baseline contract (naive + moving average)
- Comparison schema extension in metrics
- Reproducibility contract (seed, deterministic, split-index, config, git hash)
- New run metadata artifact: `artifacts/metadata/{run_id}.json` (`phase3.runmeta.v1`)
- (현재 구현) 예외 기반 비0 종료, 상세 실패코드 미매핑

**Acceptance criteria (explicit)**
- AC-1..AC-5 in `PHASE3_ARCH.md`:
  - model+baseline metrics co-saved
  - run metadata created and key fields validated
  - reproducibility fields complete
  - rerun variance gate (RMSE ±5%)
  - invalid comparison contract causes failure

---

## Phase 4 — Operations Hardening (One-click, Smoke, Health, Recovery)
**Source:** `docs/PHASE4_ARCH.md`

**Explicit deliverables**
- One-click E2E run contract (preprocess→train/eval)
- Ops failure handling contract (현재: 비0 종료 + 로그 분류)
- run_id triple-consistency validation (path + payload + metrics)
- Smoke test and health-check rule set
- Runbook linkage for triage/recovery

**Acceptance criteria (explicit)**
- AC-1..AC-5 in `PHASE4_ARCH.md`:
  - one-click execution works
  - failure handling contract documented
  - run_id guard fixed
  - smoke/health reproducible
  - newcomer can recover within 30 min via runbook

---

## Phase 5 — Extension Contracts (Model/Data/Edge)
**Source:** `docs/PHASE5_ARCH.md`

**Explicit deliverables**
- Expanded model-type contract (`lstm|gru|attention_lstm`)
- Multivariate/covariate shape/schema contracts
- Extended preprocessing artifact keys (`feature_names`, `target_indices`, etc.)
- Benchmark matrix + comparison table format (minimum 12 runs)
- Edge PoC criteria (ONNX/TFLite export/parity/latency/size/stability)

**Acceptance criteria (explicit)**
- AC-1..AC-5 in `PHASE5_ARCH.md`:
  - extension contracts documented
  - multivariate required keys fixed
  - experiment matrix/table fixed
  - edge PoC numeric gate defined
  - univariate backward compatibility strategy documented

---

## 2) Dependency map & critical path

```text
P1 (data/preprocess contracts + artifacts)
  -> P2 (train/eval/infer contracts + core artifacts)
     -> P3 (baseline compare + reproducibility metadata)
        -> P4 (ops hardening: one-click/smoke/health/runbook)
           -> P5 (extensions: model/data/edge)
```

### Cross-phase hard dependencies
- **P2 depends on P1**: processed tensors + preprocessor contract are required.
- **P3 depends on P2**: baseline comparison wraps model evaluation outputs.
- **P4 depends on P3**: ops gates require stable artifact and metadata contracts.
- **P5 depends on P4**: extensions should not break productionized run_id/ops contract.

### Practical critical path (delivery-accelerated)
1. **P1 contract completeness + AC tests**
2. **P2 executable artifact production (real run evidence)**
3. **P3 baseline + repro gates operational**
4. **P4 one-click + health gate passing in CI**
5. **P5 feature expansion under preserved gates**

If any of 1–4 is incomplete, P5 expansion risks rework and non-reproducible comparisons.

---

## 3) Parallelizable work packages (with risk notes)

## Stream A — Contract/Test Backbone (can run continuously)
- AC-to-test traceability matrix (P1..P5)
- Failure code conformance tests (runner/wrapper)
- Schema validators for metrics/meta/reports

**Risks**
- Contract drift between docs and code paths
- Filename/path mismatches across phases

## Stream B — Core Runtime & Artifact Integrity
- run_id propagation + mismatch fail-fast hardening
- Artifact writer normalization (`best/last/metrics/report/meta`)
- Determinism toggles + seed plumbing

**Risks**
- Environment-dependent determinism instability
- Backward compatibility breaks for legacy artifacts

## Stream C — Ops Readiness (starts after minimal P2/P3 stability)
- One-click script normalization
- smoke/health automation in CI
- runbook verification drills

**Risks**
- Docs/examples not executable as-written
- false PASS from incomplete health checks

## Stream D — Phase 5 Extension Prototyping (parallel after P4 gates are stable)
- GRU + attention-lstm interface conformance
- multivariate/covariate preprocessing contract implementation
- benchmark harness + edge PoC scripts

**Risks**
- Attention export compatibility (ONNX/TFLite)
- baseline logic ambiguity for multivariate targets

---

## 4) Suggested execution order (accelerated)

1. **Lock gate criteria alignment docs-first (1 day)**
   - Resolve contradictions between ARCH/PM docs (single source of truth)
2. **Close Phase 2 runtime evidence gap**
   - Produce reproducible run_id artifacts + tester PASS evidence
3. **Close Phase 3 baseline/repro evidence**
   - Complete baseline+meta+2-run reproducibility proof
4. **Finalize Phase 4 operational closure**
   - Ensure README/example/runbook consistency + CI smoke health PASS
5. **Activate Phase 5 in two lanes**
   - Lane 1: model/data contracts and benchmark harness
   - Lane 2: edge PoC (GRU→LSTM→Attention)

---

## 5) Current blockers (from docs)

- **Phase documentation drift/conflict**:
  - Example: `PHASE5_PM_TRACKER.md` states `PHASE5_ARCH.md` missing, but `PHASE5_ARCH.md` exists.
  - Multiple phase trackers show older gate states not aligned with later review/fixpass docs.
- **Evidence blockers** (historically recurring):
  - Missing real run artifacts for gate closure (especially P2/P3)
  - Tester final PASS lagging after implementation completion
- **Operational consistency blocker**:
  - README/example command-path inconsistency appears as recurring source of gate delay in Phase 4 docs.

---

## 6) Per-phase DoD checklist (concise)

## Phase 1 DoD
- [ ] AC-1..AC-8 test-mapped and passing
- [ ] preprocessor artifact schema/version fixed
- [ ] fail-fast codes reproducible and documented
- [ ] rerun invariance evidence captured

## Phase 2 DoD
- [ ] Single-run CLI produces full artifact set (best/last/metrics/report/predictions)
- [ ] run_id integrity checks enforced (incl. mismatch fail)
- [ ] report/metrics schema validation in CI
- [ ] at least one real run evidence attached to gate

## Phase 3 DoD
- [ ] model+naive+MA metrics persisted in unified schema
- [ ] `metadata/{run_id}.json` valid with commit/hash/seed/split-index
- [ ] reproducibility smoke (2 reruns, RMSE tolerance) passing
- [ ] comparison invalidation logic tested

## Phase 4 DoD
- [ ] one-click E2E path executable by newcomer
- [ ] smoke + health checks automated and failing correctly
- [ ] runbook recovery executed in practice drill
- [ ] README/examples/runbook fully consistent with real commands

## Phase 5 DoD
- [ ] model-type/multivariate/covariate contracts implemented without breaking prior phases
- [ ] 12-run benchmark matrix produced and summarized
- [ ] edge PoC evaluated against numeric gate criteria
- [ ] backward compatibility (univariate path) regression-pass

---

## 7) Recommended governance to keep velocity high
- Maintain one **Phase Gate Board** with 4 gates (A/Coder/Reviewer/Tester) per phase and artifact evidence links.
- Enforce **AC → Test → Artifact evidence** triad before gate closure.
- Treat ARCH docs as contract source; PM tracker as execution status only.
- Add doc-drift CI check (required files/claims existence validation) to prevent stale blocker carryover.
