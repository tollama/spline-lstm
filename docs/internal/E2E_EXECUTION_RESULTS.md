# E2E_EXECUTION_RESULTS — Spline-LSTM E2E 실제 실행 결과

## Standard Handoff Format

### 1) 요청/목표
- 역할: Tester
- 프로젝트: `~/spline-lstm`
- 목표: `docs/E2E_TEST_PLAN.md` 기준 E2E 전체 실행 및 증빙
- 실행 범위:
  1. quick-gate 세트
  2. e2e-path (`run_e2e.sh` + `smoke_test.sh`)
  3. regression 세트
  4. 확장 경로(`compare_runner`, phase5 extension)

---

### 2) 실행 환경/시각
- OS: macOS (Darwin arm64)
- Python: `python3` (환경 내 3.9 계열)
- 의존성: `requirements.txt` 설치 상태 확인
- 실행 일시(로컬): 2026-02-18 19:18~19:19 (KST)

---

### 3) 실행 커맨드 전체

#### 3.1 사전 준비
```bash
cd ~/spline-lstm
python3 -m pip install -r requirements.txt
```

#### 3.2 quick-gate
```bash
python3 -m pytest -q \
  tests/test_phase4_run_id_guard.py \
  tests/test_artifacts.py \
  tests/test_training_runner_cli_contract.py \
  tests/test_training_leakage.py \
  | tee logs/quick-gate-pytest-20260218-191832.log

RUN_ID=local-quick-20260218-191832 EPOCHS=1 \
  bash scripts/smoke_test.sh \
  | tee logs/quick-gate-smoke-20260218-191832.log
```

#### 3.3 e2e-path
```bash
RUN_ID=local-e2e-20260218-191847 EPOCHS=1 \
  bash scripts/run_e2e.sh \
  | tee logs/e2e-path-run_e2e-20260218-191847.log

RUN_ID=local-e2e-smoke-20260218-191847 EPOCHS=1 \
  bash scripts/smoke_test.sh \
  | tee logs/e2e-path-smoke_test-20260218-191847.log
```

#### 3.4 regression
```bash
python3 -m pytest -q \
  tests/test_phase2_pipeline.py \
  tests/test_preprocessing_pipeline.py \
  tests/test_data_contract.py \
  tests/test_phase3_repro_baseline.py \
  tests/test_phase5_extension.py \
  | tee logs/regression-pytest-20260218-191902.log
```

#### 3.5 확장 경로 (compare_runner + phase5 extension)
```bash
RUN_ID=local-compare-20260218-191936 EPOCHS=1 \
  bash scripts/run_compare.sh \
  | tee logs/extension-run_compare-20260218-191936.log

python3 -m pytest -q \
  tests/test_phase5_extension.py \
  tests/test_phase5_multivariate_proto.py \
  | tee logs/extension-phase5-pytest-20260218-191943.log
```

---

### 4) PASS/FAIL 요약

| 구분 | 실행 항목 | 결과 | 근거 |
|---|---|---|---|
| quick-gate | core contract pytest | PASS | `13 passed` (`logs/quick-gate-pytest-20260218-191832.log`) |
| quick-gate | smoke gate | PASS | `[SMOKE][OK] all checks passed` (`logs/quick-gate-smoke-20260218-191832.log`) |
| e2e-path | `run_e2e.sh` | PASS | `[E2E][OK] completed` (`logs/e2e-path-run_e2e-20260218-191847.log`) |
| e2e-path | post smoke | PASS | `[SMOKE][OK] all checks passed` (`logs/e2e-path-smoke_test-20260218-191847.log`) |
| regression | core regression pytest | PASS | `16 passed` (`logs/regression-pytest-20260218-191902.log`) |
| extension | `run_compare.sh` (compare_runner) | PASS | comparison json/md 생성 (`logs/extension-run_compare-20260218-191936.log`) |
| extension | phase5 extension pytest | PASS | `7 passed` (`logs/extension-phase5-pytest-20260218-191943.log`) |

**총평:** 요청 범위 전 항목 PASS

---

### 5) 실패 항목/원인/재현법/로그 경로
- 이번 실행에서는 **실패 항목 없음**.
- 참고 경고(비차단):
  - `NotOpenSSLWarning` (urllib3 + LibreSSL)
  - pandas `'H'` freq FutureWarning
  - TensorFlow NodeDef unknown attribute 로그
- 위 경고들은 이번 게이트에서 테스트 실패를 유발하지 않았음.

---

### 6) artifacts 생성 확인표

#### 6.1 quick/e2e smoke run 산출물

| Run ID | processed.npz | meta.json | preprocessor.pkl | metrics.json | report.md | metadata.json | best.keras | last.keras |
|---|---|---|---|---|---|---|---|---|
| `local-quick-20260218-191832` | O | O | O | O | O | O | O | O |
| `local-e2e-20260218-191847` | O | O | O | O | O | O | O | O |
| `local-e2e-smoke-20260218-191847` | O | O | O | O | O | O | O | O |

#### 6.2 확장 경로 산출물

| Run ID | comparison json | comparison md |
|---|---|---|
| `local-compare-20260218-191936` | `artifacts/comparisons/local-compare-20260218-191936.json` (O) | `artifacts/comparisons/local-compare-20260218-191936.md` (O) |

---

### 7) 로그/증빙 파일 경로
- 상태 요약 env
  - `logs/quick-gate-status-20260218-191832.env`
  - `logs/e2e-path-status-20260218-191847.env`
  - `logs/regression-status-20260218-191902.env`
  - `logs/extension-run_compare-status-20260218-191936.env`
  - `logs/extension-phase5-status-20260218-191943.env`
- 실행 로그
  - `logs/quick-gate-pytest-20260218-191832.log`
  - `logs/quick-gate-smoke-20260218-191832.log`
  - `logs/e2e-path-run_e2e-20260218-191847.log`
  - `logs/e2e-path-smoke_test-20260218-191847.log`
  - `logs/regression-pytest-20260218-191902.log`
  - `logs/extension-run_compare-20260218-191936.log`
  - `logs/extension-phase5-pytest-20260218-191943.log`

---

### 8) 결론
- 계획 문서 기준 필수 실행 범위(quick-gate, e2e-path, regression, 확장 경로) 모두 실제 실행 완료.
- 결과: **전 항목 PASS**, 필수 산출물 및 증빙 로그 확보 완료.
