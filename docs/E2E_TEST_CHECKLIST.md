# E2E_TEST_CHECKLIST

## Standard Handoff Format

### 1) 요청/목표
- 프로젝트: `~/spline-lstm`
- 목표: **실제 실행 가능한 E2E 테스트 체크리스트/커맨드 플랜** 수립
- 범위: `preprocess -> train/eval/infer -> artifact 검증 -> 재현성 검증`
- 필수 반영 항목:
  1. Happy path / Fail path 케이스
  2. 필수 커맨드 세트(pytest + runner + scripts)
  3. 합격 기준(성능, 재현성, artifact 무결성)
  4. 자동화 우선순위(CI 연계 후보)
  5. 결과 리포트 템플릿

---

### 2) 테스트 전략 요약
- **1차 게이트(빠른 차단):** `scripts/smoke_test.sh` + 핵심 pytest 계약 테스트
- **2차 게이트(회귀 안정성):** 전체 pytest 또는 핵심 회귀 묶음 실행
- **3차 게이트(재현성):** 동일 seed/설정 2회 실행 후 metrics/split/metadata 비교
- **4차 게이트(운영 경로):** `scripts/run_e2e.sh` 및 `src.training.runner` 직접 실행 경로 확인

---

### 3) 체크리스트 (Happy path / Fail path)

#### 3-1. Happy path 체크리스트

##### [HP-01] One-click E2E 성공
- 목적: 운영 기본 경로(`scripts/run_e2e.sh`) 정상 동작 확인
- 절차:
  1. 고유 run_id 설정
  2. `bash scripts/run_e2e.sh` 실행
  3. 종료코드 0 확인
- 기대결과:
  - `artifacts/metrics/{run_id}.json` 생성
  - `artifacts/reports/{run_id}.md` 생성
  - `artifacts/checkpoints/{run_id}/best.keras` 생성
  - `artifacts/models/{run_id}/preprocessor.pkl` 생성

##### [HP-02] Smoke gate 성공
- 목적: 짧은 시간에 핵심 산출물/스키마 검증
- 절차: `bash scripts/smoke_test.sh`
- 기대결과:
  - 종료코드 0
  - metrics에 `mae/rmse/mape/r2` 키 존재
  - metrics `run_id`와 실행 run_id 일치

##### [HP-03] Runner 직접 실행(합성 데이터)
- 목적: wrapper 없이 CLI 계약 자체 검증
- 절차: `python3 -m src.training.runner ... --synthetic --seed 고정`
- 기대결과:
  - metrics/report/checkpoints/metadata/splits 생성
  - 출력 JSON에 `run_id`, `metrics`, `split_indices`, `commit_hash*` 필드 존재

##### [HP-04] Preprocess 산출물 연동 실행
- 목적: 전처리 산출물(`processed.npz`, `preprocessor.pkl`)을 runner가 정상 소비
- 절차:
  1. `python3 -m src.preprocessing.smoke --run-id <RID>`
  2. 동일 `<RID>`로 `python3 -m src.training.runner --processed-npz ... --preprocessor-pkl ...`
- 기대결과:
  - run_id guard 통과
  - 학습/평가 산출물 정상 생성

##### [HP-05] 핵심 pytest 회귀 통과
- 목적: 데이터 계약/누수 방지/run_id 무결성/CLI 계약 유지 확인
- 기대결과: 지정 테스트 전부 PASS (skip은 비차단)

---

#### 3-2. Fail path 체크리스트

##### [FP-01] run_id mismatch 차단 (CLI vs processed 경로)
- 절차: `--run-id A` + `--processed-npz artifacts/processed/B/processed.npz`
- 기대결과: 실패(fail-fast), `run_id mismatch` 메시지

##### [FP-02] run_id mismatch 차단 (CLI vs preprocessor payload)
- 절차: `--run-id A` + `--preprocessor-pkl` 내부 run_id가 B인 파일 주입
- 기대결과: 실패(fail-fast), `run_id mismatch` 메시지

##### [FP-03] 입력 산출물 불완전
- 절차: `processed.npz`에서 `scaled/raw_target` 없는 파일로 실행
- 기대결과: 실패, `processed.npz must contain one of: scaled, raw_target`

##### [FP-04] TensorFlow 백엔드 미충족
- 절차: TF 미설치 환경에서 runner 실행
- 기대결과: 실패, backend requirement 에러 명시

##### [FP-05] Smoke 산출물 누락
- 절차: smoke 실행 후 필수 파일 하나 삭제/경로 오류 유도
- 기대결과: `[SMOKE][FAIL] missing: ...` 출력 후 실패

---

### 4) 필수 커맨드 세트 (실행 순서 권장)

#### 4-1. 환경 준비
```bash
cd ~/spline-lstm
python3 -m pip install -r requirements.txt
```

#### 4-2. 빠른 게이트 (권장 1순위)
```bash
# A) one-click smoke
RUN_ID=e2e-smoke-$(date +%Y%m%d-%H%M%S) EPOCHS=1 bash scripts/smoke_test.sh

# B) 핵심 계약 테스트
python3 -m pytest -q \
  tests/test_phase4_run_id_guard.py \
  tests/test_artifacts.py \
  tests/test_training_runner_cli_contract.py \
  tests/test_training_leakage.py
```

#### 4-3. E2E 실경로 검증 (script + runner + preprocessing)
```bash
# A) script 경로
RUN_ID=e2e-script-$(date +%Y%m%d-%H%M%S) EPOCHS=1 bash scripts/run_e2e.sh

# B) runner 직접 경로(synthetic)
python3 -m src.training.runner \
  --run-id e2e-runner-direct-$(date +%Y%m%d-%H%M%S) \
  --synthetic \
  --epochs 1 \
  --verbose 0 \
  --artifacts-dir artifacts

# C) preprocess -> runner 연동 경로
RID=e2e-prep-link-$(date +%Y%m%d-%H%M%S)
python3 -m src.preprocessing.smoke --run-id "$RID" --artifacts-dir artifacts
python3 -m src.training.runner \
  --run-id "$RID" \
  --processed-npz "artifacts/processed/$RID/processed.npz" \
  --preprocessor-pkl "artifacts/models/$RID/preprocessor.pkl" \
  --epochs 1 \
  --verbose 0 \
  --artifacts-dir artifacts
```

#### 4-4. 전체 회귀 (권장 2순위/야간)
```bash
python3 -m pytest -q
```

#### 4-5. Fail path 재현 커맨드(예시)
```bash
# FP-01: run_id mismatch (processed 경로)
python3 -m src.training.runner \
  --run-id run-a \
  --processed-npz artifacts/processed/run-b/processed.npz \
  --epochs 1 --verbose 0
```

---

### 5) 합격 기준 (성능/재현성/artifact 무결성)

#### 5-1. 하드 기준 (반드시 충족)
1. **성공률**
   - `scripts/smoke_test.sh` 성공(종료코드 0)
   - 핵심 pytest 묶음 전부 PASS
2. **artifact 무결성**
   - 필수 산출물 4종 존재: metrics/report/best checkpoint/preprocessor
   - metrics JSON의 `run_id`가 실행 run_id와 일치
   - run_id mismatch 시 반드시 fail-fast
3. **재현성 최소 기준**
   - 동일 seed/동일 설정 재실행 시, split metadata(`artifacts/splits/{run_id}.json`) 구조/인덱스 계약 유지
   - 실행 config snapshot 및 metadata 파일 생성

#### 5-2. 소프트 기준 (권장)
1. **성능 안정성**
   - 동일 데이터·설정에서 RMSE 급격 악화 없음(직전 기준 run 대비 허용 편차 내)
   - baseline 대비 개선률(`relative_improvement_rmse_pct`)이 지속적으로 음수로 고착되지 않을 것
2. **운영 관점 품질**
   - report(`artifacts/reports/{run_id}.md`)가 실험 재현에 필요한 설정/지표/산출물 경로를 포함

> 참고: 절대 성능 임계값은 데이터셋/노이즈 조건에 따라 달라지므로, 프로젝트에서는 **회귀 기준(이전 안정 run 대비 악화 여부)** 중심으로 관리 권장.

---

### 6) 자동화 우선순위 (CI 연계 후보)

#### P0 (즉시 CI 필수)
1. `bash scripts/smoke_test.sh` (EPOCHS=1)
2. `tests/test_phase4_run_id_guard.py`
3. `tests/test_artifacts.py`
4. `tests/test_training_runner_cli_contract.py`
5. `tests/test_training_leakage.py`

#### P1 (주기/병렬 CI 권장)
1. `python3 -m pytest -q tests/test_phase2_pipeline.py`
2. `python3 -m pytest -q tests/test_preprocessing_pipeline.py tests/test_data_contract.py`
3. `scripts/run_e2e.sh` 1회(고정 seed/run_id prefix)

#### P2 (야간/릴리즈 전)
1. `python3 -m pytest -q` 전체 회귀
2. 동일 seed 2회 러너 실행 후 metrics diff 검사(재현성 drift 감시)
3. (Phase5 사용 시) `bash scripts/run_compare.sh` smoke

---

### 7) 결과 리포트 템플릿

```md
# TEST_RESULTS_<TAG>

## Standard Handoff Format

### 1) 요청/목표
- 프로젝트:
- 목표:
- 검증 범위:

### 2) 수행 범위
- 

### 3) 실행 커맨드
```bash
# 실제 실행한 명령만 기록
```

### 4) 결과 요약 (Gate)
- 최종 판정: PASS | FAIL
- blocker: 있음 | 없음
- 항목별 요약:
  1. 
  2. 

### 5) 상세 결과
#### [PASS/FAIL] 항목명
- 로그 요약:
- 산출물 경로:
- 관찰사항:

### 6) 실패 원인 / 재현법
- 원인:
- 재현 커맨드:

### 7) 합격 기준 충족 여부
- 성능: 충족 | 미충족 (근거)
- 재현성: 충족 | 미충족 (근거)
- artifact 무결성: 충족 | 미충족 (근거)

### 8) 리스크/메모
- 

### 9) 최종 결론
- 

### 10) 산출물
- 문서:
- 아티팩트:
```

---

### 8) 인수인계 메모
- 본 체크리스트는 현재 코드 기준(`scripts/run_e2e.sh`, `scripts/smoke_test.sh`, `src.training.runner`)에 맞춰 작성됨.
- 환경 의존 이슈를 줄이기 위해 테스트 명령은 `pytest` 대신 `python3 -m pytest` 기준으로 통일.
- 운영 게이트는 **P0 자동화 + P2 야간 회귀** 2단 구조로 시작하는 것을 권장.
