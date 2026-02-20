# TEST_RESULTS_PHASE5_MUSTFIX_FINAL

- 실행 시각: 2026-02-18 20:02:08 KST
- 대상 프로젝트: `~/spline-lstm`
- 목적: Phase5 Must fix 최종 검증
  1. runner 옵션/입력 계약(`--model-type`, `--feature-mode` 등)
  2. phase5 확장 테스트 + 핵심 회귀 테스트
  3. 실패 시 재현 방법 제시

---

## 1) 검증 실행 커맨드

### A. runner 계약 + phase5 확장/회귀 pytest
```bash
python3 -m pytest -q \
  tests/test_training_runner_cli_contract.py \
  tests/test_phase5_extension.py \
  tests/test_phase5_multivariate_proto.py \
  tests/test_data_contract.py \
  tests/test_artifacts.py \
  tests/test_phase4_run_id_guard.py \
  tests/test_phase3_repro_baseline.py
```

### B. Phase5 비교 러너 smoke
```bash
RUN_ID=phase5-mustfix-final-verify EPOCHS=1 bash scripts/run_compare.sh
```

### C. PHASE5_ARCH 계약 인자 runner 수용성 확인
```bash
python3 -m src.training.runner \
  --model-type lstm \
  --feature-mode multivariate \
  --run-id phase5-contract-check \
  --epochs 1 \
  --synthetic
```

---

## 2) 결과 요약

### A. pytest 묶음
- 결과: **PASS**
- 요약: `25 passed, 15 warnings in 20.88s`
- 판단: phase5 확장 테스트 + 핵심 회귀 테스트군은 현재 코드 기준 green

### B. compare_runner smoke
- 결과: **PASS**
- 산출물:
  - `artifacts/comparisons/phase5-mustfix-final-verify.json`
  - `artifacts/comparisons/phase5-mustfix-final-verify.md`
- 판단: phase5 확장 비교 경로(별도 compare_runner)는 동작 확인

### C. runner 옵션/입력 계약(`--model-type`, `--feature-mode`)
- 결과: **FAIL**
- 에러:
  - `runner.py: error: unrecognized arguments: --model-type lstm --feature-mode multivariate`
- 판단: `docs/PHASE5_ARCH.md` 계약(확장 인자)과 `src.training.runner` CLI 인터페이스 불일치

---

## 3) PASS/FAIL 최종 판정

- **최종 판정: FAIL**
- 사유: Must fix 관점의 핵심 항목인 runner 계약 정합성 미충족

---

## 4) Blocker

1. **Blocker-1 (P0)**: `src/training/runner.py`가 `--model-type`, `--feature-mode`를 수용하지 않음
   - 영향: Phase5 ARCH에 명시된 runner 확장 계약 직접 실행 불가
   - 상태: OPEN

---

## 5) 실패 재현 방법 (Repro)

```bash
cd ~/spline-lstm
python3 -m src.training.runner \
  --model-type lstm \
  --feature-mode multivariate \
  --run-id repro-phase5-contract \
  --epochs 1 \
  --synthetic
```

예상 결과(현재):
- 종료코드 `2`
- `unrecognized arguments: --model-type ... --feature-mode ...`

---

## 6) Standard Handoff Format

### Summary
- phase5 확장 테스트/핵심 회귀(pytest 25건) 및 compare_runner smoke는 PASS.
- 그러나 Phase5 ARCH 기준 runner 필수 확장 인자 계약(`--model-type`, `--feature-mode`)이 실제 runner에서 미지원.
- 따라서 Must fix 최종 검증은 **FAIL**.

### What was validated
- runner 기존 CLI 계약 회귀 (`tests/test_training_runner_cli_contract.py`) PASS
- phase5 확장 테스트 (`tests/test_phase5_extension.py`, `tests/test_phase5_multivariate_proto.py`) PASS
- 핵심 회귀(`test_data_contract`, `test_artifacts`, `test_phase4_run_id_guard`, `test_phase3_repro_baseline`) PASS
- compare_runner 경로 smoke PASS
- PHASE5_ARCH 확장 인자 runner 직접 수용성 FAIL

### Evidence
- pytest 결과: `25 passed`
- 비교 산출물: `artifacts/comparisons/phase5-mustfix-final-verify.{json,md}`
- 계약 실패 stderr: `unrecognized arguments: --model-type ... --feature-mode ...`

### Blockers / Risks
- Blocker-1(P0): runner-문서 계약 불일치 지속 시 Phase5 Gate 수렴 불가

### Recommended next step
- `src/training/runner.py`에 `--model-type`, `--feature-mode` 인자 및 입력 분기 반영 후,
  동일 커맨드 재검증 + 본 문서 갱신.
