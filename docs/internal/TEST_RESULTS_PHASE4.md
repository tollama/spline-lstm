# TEST_RESULTS_PHASE4

## Standard Handoff Format

### 1) 요청/목표
- 프로젝트: `~/spline-lstm`
- 목표: 운영화 항목 검증 (Phase 4 Tester)
- 필수 작업:
  1. 원클릭 E2E 스모크 테스트
  2. run_id mismatch 차단 테스트
  3. 문서 기준 재현 테스트(README/runbook 순서)
  4. 결과 문서화
- 조건: synthetic data 우선, 실패 원인/재현법 기록

### 2) 수행 범위
- synthetic 우선으로 runner 단일 커맨드 E2E 실행
- run_id mismatch fail-fast 테스트 단독 실행
- README 기준 명령 순서 재현 실행
- runbook 성격의 phase3 검증 명령(`tests/test_phase3_repro_baseline.py`) 별도 재실행

### 3) 실행 커맨드
```bash
# A. One-click E2E smoke (synthetic)
python3 -m src.training.runner \
  --run-id phase4-e2e-smoke \
  --synthetic \
  --synthetic-samples 360 \
  --synthetic-noise 0.06 \
  --epochs 5 \
  --batch-size 16 \
  --sequence-length 24 \
  --horizon 1 \
  --seed 123 \
  --artifacts-dir artifacts \
  --checkpoints-dir checkpoints \
  --verbose 0

# B. run_id mismatch 차단 테스트
python3 -m pytest -q \
  tests/test_artifacts.py::TestArtifactRules::test_validate_artifact_run_id_mismatch_raises

# C. README 순서 재현
python3 -m pip install -r requirements.txt
python3 examples/train_example.py
python3 -m pytest tests/ -v
python3 -m src.preprocessing.smoke --run-id phase4-readme-smoke

# D. runbook 대체(phase3 gate 문서 기준 핵심 커맨드)
python3 -m pytest -q tests/test_phase3_repro_baseline.py
```

### 4) 결과 요약
- 전체 판정: **PARTIAL FAIL**
- 세부:
  1. 원클릭 E2E 스모크: **PASS**
  2. run_id mismatch 차단: **PASS**
  3. 문서 기준 재현(README/runbook): **PARTIAL FAIL**
     - README `examples/train_example.py` 단계 실패
     - 나머지 README/phase3 runbook 대체 명령은 성공

### 5) 테스트 상세 결과

#### [PASS] 항목 1 — 원클릭 E2E 스모크
- 실행 run_id: `phase4-e2e-smoke`
- 결과: 종료 코드 0
- 주요 산출물 확인:
  - `artifacts/metrics/phase4-e2e-smoke.json`
  - `artifacts/reports/phase4-e2e-smoke.md`
  - `artifacts/metadata/phase4-e2e-smoke.json`
  - `checkpoints/phase4-e2e-smoke/best.keras`
  - `checkpoints/phase4-e2e-smoke/last.keras`
- 참고 지표:
  - `rmse=0.205897`, `r2=0.406536`

#### [PASS] 항목 2 — run_id mismatch 차단
- 테스트: `test_validate_artifact_run_id_mismatch_raises`
- 결과: `1 passed`
- 의미: model/preprocessor run_id 불일치 시 예외 발생(차단) 확인

#### [PARTIAL FAIL] 항목 3 — 문서 기준 재현

##### 3-1) README 재현 결과
- `python3 -m pip install -r requirements.txt` → **PASS**
- `python3 examples/train_example.py` → **FAIL**
- `python3 -m pytest tests/ -v` → **PASS** (`29 passed, 2 skipped`)
- `python3 -m src.preprocessing.smoke --run-id phase4-readme-smoke` → **PASS**

##### 3-2) runbook 대체 재현 결과
- 명시적 `runbook.md` 파일은 저장소에서 확인되지 않음
- phase3 gate 문서의 재현 커맨드로 대체 실행:
  - `python3 -m pytest -q tests/test_phase3_repro_baseline.py` → **PASS** (`2 passed`)

### 6) 실패 원인/재현법

#### 실패 #1: README example checkpoint 저장 경로 확장자 누락
- 실패 명령:
  - `python3 examples/train_example.py`
- 에러 메시지(요지):
  - `ValueError: Invalid filepath extension for saving... Received: filepath=./checkpoints/example_model`
- 직접 원인:
  - Keras 저장 시 `.keras` 또는 `.h5` 확장자 필요
  - 예제 스크립트가 확장자 없는 이름으로 `save_checkpoint("example_model")` 호출
- 재현 방법:
  1. `cd ~/spline-lstm`
  2. `python3 examples/train_example.py`
  3. 학습 종료 후 저장 단계에서 동일 ValueError 발생

### 7) 산출물
- 본 문서: `docs/TEST_RESULTS_PHASE4.md`
- 실행 로그(로컬 임시 파일):
  - `/tmp/phase4_pip.log`
  - `/tmp/phase4_example.log`
  - `/tmp/phase4_pytest_all.log`
  - `/tmp/phase4_pre_smoke.log`
- 핵심 결과물:
  - `artifacts/metrics/phase4-e2e-smoke.json`
  - `artifacts/reports/phase4-e2e-smoke.md`
  - `artifacts/metadata/phase4-e2e-smoke.json`
  - `checkpoints/phase4-e2e-smoke/{best,last}.keras`
  - `artifacts/processed/phase4-readme-smoke/{processed.npz,meta.json}`
  - `artifacts/models/phase4-readme-smoke/preprocessor.pkl`

### 8) 권장 후속 조치
1. `examples/train_example.py`의 체크포인트 파일명에 `.keras` 확장자 반영
2. README에 현재 실행 가능 커맨드 기준으로 example 섹션 업데이트
3. runbook 문서를 별도 파일(`docs/RUNBOOK.md`)로 고정해 재현 절차 명확화

### 9) 인수인계 메모
- synthetic data 우선 원칙으로 실행함
- 운영화 관점에서 핵심 러너(E2E)와 run_id mismatch 차단은 정상
- 문서 재현성은 README example 단계 1건이 blocker로 남아 있어 수정 필요
