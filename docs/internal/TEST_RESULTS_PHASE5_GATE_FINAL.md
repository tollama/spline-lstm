# TEST_RESULTS_PHASE5_GATE_FINAL

## Standard Handoff Format

### 1) 요청/목표
- 프로젝트: `~/spline-lstm`
- 목표: `coder-spline-mvp-phase5` 반영 후 **Phase5 최종 게이트 재검증**
- 검증 항목:
  1. 신규 확장 테스트 `tests/test_phase5_multivariate_proto.py` 통과
  2. 기존 MVP 회귀 테스트 통과
  3. 비교 실험 실행 경로 `scripts/run_compare.sh` 스모크

### 2) 수행 범위
- 테스트 실행은 로컬 환경(`python3 -m pytest`) 기준으로 재검증
- 비교 실험 경로는 최소 학습 epoch(`EPOCHS=1`)로 smoke 확인
- PASS/FAIL 및 blocker 유무를 최종 게이트 관점으로 명시

### 3) 실행 커맨드
```bash
# 1) 신규 확장 테스트
python3 -m pytest -q tests/test_phase5_multivariate_proto.py

# 2) 기존 MVP 회귀 테스트
python3 -m pytest -q \
  tests/test_phase2_pipeline.py \
  tests/test_preprocessing_pipeline.py \
  tests/test_data_contract.py \
  tests/test_models.py \
  tests/test_artifacts.py \
  tests/test_phase4_run_id_guard.py \
  tests/test_training_runner_cli_contract.py \
  tests/test_training_leakage.py

# 3) 비교 실험 경로(run_compare.sh) 스모크
RUN_ID=phase5-gate-final-smoke EPOCHS=1 bash scripts/run_compare.sh
```

### 4) 결과 요약 (Gate)
- 최종 판정: **PASS**
- blocker: **없음**
- 항목별 결과:
  1. `test_phase5_multivariate_proto.py`: **PASS** (`4 passed`)
  2. 기존 MVP 회귀 테스트: **PASS** (`27 passed, 2 skipped`)
  3. `run_compare.sh` 스모크: **PASS** (비교 산출물 생성 확인)

### 5) 상세 결과

#### [PASS] 항목 1 — 신규 확장 테스트
- 실행 결과: `4 passed, 15 warnings in 2.21s`
- 확인 포인트:
  - multivariate window shape 계약
  - preprocessing multivariate PoC artifact 저장
  - multivariate 입력 feature contract

#### [PASS] 항목 2 — 기존 MVP 회귀 테스트
- 실행 결과: `27 passed, 2 skipped, 15 warnings in 5.62s`
- 해석:
  - 기존 MVP 핵심 경로(파이프라인/데이터 계약/모델/아티팩트/run_id 가드/학습 계약/누수 방지) 회귀 안정 상태
  - skip 2건은 테스트 내부 조건부 skip(비차단)

#### [PASS] 항목 3 — 비교 실험 경로 smoke
- 실행 결과: 스크립트 종료 코드 0, `[OK] comparison artifacts ...` 로그 확인
- 생성 산출물:
  - `artifacts/comparisons/phase5-gate-final-smoke.json`
  - `artifacts/comparisons/phase5-gate-final-smoke.md`
- 요약:
  - `winner_by_rmse: gru`
  - `rmse_gap: 0.09948878735303879`

### 6) 실패 원인 / 재현법
- 본 검증 실행에서 실패 케이스 없음.
- 재현은 3) 실행 커맨드 그대로 수행.

### 7) 리스크/메모
- 공통 warning 관찰(비차단):
  - `NotOpenSSLWarning` (LibreSSL/OpenSSL 관련)
  - `PyparsingDeprecationWarning`
  - TensorFlow 런타임의 NodeDef attribute warning (`use_unbounded_threadpool`)
- 현재 게이트 PASS/FAIL 판정에는 영향 없음.

### 8) 최종 결론
- 요구된 3개 검증 항목 모두 통과.
- **Phase5 최종 게이트 재검증 결과: PASS (blocker 없음)**.

### 9) 산출물
- 결과 문서: `docs/TEST_RESULTS_PHASE5_GATE_FINAL.md`
- 비교 실험 산출물:
  - `artifacts/comparisons/phase5-gate-final-smoke.json`
  - `artifacts/comparisons/phase5-gate-final-smoke.md`
