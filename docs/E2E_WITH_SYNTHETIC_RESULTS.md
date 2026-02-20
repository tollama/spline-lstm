# E2E_WITH_SYNTHETIC_RESULTS

## Standard Handoff Format

### 1) 요청/목표
- 프로젝트: `~/spline-lstm`
- 목표: 생성된 synthetic CSV(`data/raw/synthetic/*`)를 입력으로 실제 E2E 경로 검증
- 필수 범위:
  1. S1/S2/S3 각각 `preprocessing -> training.runner -> artifacts` 생성 검증
  2. quick-gate 핵심 테스트 최소 실행
  3. 실패 시 재현 커맨드/원인 기록

### 2) 수행 범위
- synthetic 입력 파일 확인:
  - `data/raw/synthetic/synthetic_S1_n120_seed42.csv`
  - `data/raw/synthetic/synthetic_S2_n120_seed42.csv`
  - `data/raw/synthetic/synthetic_S3_n120_seed42.csv`
- 시나리오별 E2E(전처리+학습) 실행 및 산출물 무결성 확인
- quick-gate 최소 세트(pytest + smoke_test) 실행

### 3) 실행 커맨드
```bash
# A. 시나리오별 E2E (S1/S2/S3)
for SC in S1 S2 S3; do
  CSV="data/raw/synthetic/synthetic_${SC}_n120_seed42.csv"
  RID="syn-${SC,,}-<timestamp>"  # 실제 실행 시 syn-s1/s2/s3-20260218-211731

  python3 -m src.preprocessing.smoke \
    --input "$CSV" \
    --run-id "$RID" \
    --artifacts-dir artifacts

  python3 -m src.training.runner \
    --run-id "$RID" \
    --processed-npz "artifacts/processed/${RID}/processed.npz" \
    --preprocessor-pkl "artifacts/models/${RID}/preprocessor.pkl" \
    --epochs 1 \
    --batch-size 16 \
    --verbose 0 \
    --artifacts-dir artifacts \
    --checkpoints-dir checkpoints
done

# B. quick-gate 최소 실행
python3 -m pytest -q \
  tests/test_phase4_run_id_guard.py \
  tests/test_artifacts.py \
  tests/test_training_runner_cli_contract.py \
  tests/test_training_leakage.py

RUN_ID=quick-syn-20260218-211752 EPOCHS=1 bash scripts/smoke_test.sh
```

### 4) 결과 요약 (PASS/FAIL)
- 최종 판정: **PASS**
- blocker: **없음**

#### 4-1. 시나리오별 E2E 결과
| 시나리오 | run_id | 전처리 | runner | artifact 검증 | 최종 |
|---|---|---|---|---|---|
| S1 | `syn-s1-20260218-211731` | PASS | PASS | PASS | PASS |
| S2 | `syn-s2-20260218-211731` | PASS | PASS | PASS | PASS |
| S3 | `syn-s3-20260218-211731` | PASS | PASS | PASS | PASS |

#### 4-2. quick-gate 결과
| 항목 | 커맨드 | 결과 |
|---|---|---|
| core pytest | `pytest -q tests/test_phase4_run_id_guard.py tests/test_artifacts.py tests/test_training_runner_cli_contract.py tests/test_training_leakage.py` | **PASS (14 passed)** |
| smoke gate | `RUN_ID=quick-syn-20260218-211752 EPOCHS=1 bash scripts/smoke_test.sh` | **PASS** (`[SMOKE][OK] all checks passed`) |

### 5) 생성 artifact 경로

#### 5-1. S1 (`syn-s1-20260218-211731`)
- `artifacts/processed/syn-s1-20260218-211731/processed.npz`
- `artifacts/processed/syn-s1-20260218-211731/meta.json`
- `artifacts/models/syn-s1-20260218-211731/preprocessor.pkl`
- `artifacts/metrics/syn-s1-20260218-211731.json`
- `artifacts/reports/syn-s1-20260218-211731.md`
- `checkpoints/syn-s1-20260218-211731/best.keras`
- `checkpoints/syn-s1-20260218-211731/last.keras`

#### 5-2. S2 (`syn-s2-20260218-211731`)
- `artifacts/processed/syn-s2-20260218-211731/processed.npz`
- `artifacts/processed/syn-s2-20260218-211731/meta.json`
- `artifacts/models/syn-s2-20260218-211731/preprocessor.pkl`
- `artifacts/metrics/syn-s2-20260218-211731.json`
- `artifacts/reports/syn-s2-20260218-211731.md`
- `checkpoints/syn-s2-20260218-211731/best.keras`
- `checkpoints/syn-s2-20260218-211731/last.keras`

#### 5-3. S3 (`syn-s3-20260218-211731`)
- `artifacts/processed/syn-s3-20260218-211731/processed.npz`
- `artifacts/processed/syn-s3-20260218-211731/meta.json`
- `artifacts/models/syn-s3-20260218-211731/preprocessor.pkl`
- `artifacts/metrics/syn-s3-20260218-211731.json`
- `artifacts/reports/syn-s3-20260218-211731.md`
- `checkpoints/syn-s3-20260218-211731/best.keras`
- `checkpoints/syn-s3-20260218-211731/last.keras`

### 6) 성능/메트릭 요약
| 시나리오 | MAE | MSE | RMSE | robust MAPE | MASE | R2 | RMSE 개선율 vs Naive(%) | RMSE 개선율 vs MA3(%) |
|---|---:|---:|---:|---:|---:|---:|
| S1 | 1.1837 | 0.0 | 1.3532 | 116.9724 | 0.0 | -0.4387 | -374.10 | -156.73 |
| S2 | 1.0932 | 0.0 | 1.3159 | 156.4695 | 0.0 | -2.0043 | -559.20 | -256.97 |
| S3 | 1.0989 | 0.0 | 1.2700 | 111.1034 | 0.0 | -0.2364 | -14.08 | +3.91 |

- 해석:
  - 본 검증의 핵심 목적(경로/산출물 무결성)은 충족(PASS).
  - 모델 품질 관점에서는 1 epoch 조건에서 baseline 대비 열위가 다수 관찰됨(비차단).

### 7) 실패 재현 커맨드 및 원인
- **실패 케이스 없음** (이번 실행 범위 내 PASS)
- 참고(비차단 경고):
  - `NotOpenSSLWarning` (urllib3/OpenSSL 환경 경고)
  - 일부 TensorFlow/Deprecation warning
  - 모두 실행 성공/산출물 생성에는 영향 없음

### 8) 로그/증적
- 시나리오 실행 목록: `logs/synthetic-e2e-runs-20260218-211731.csv`
- 시나리오별 로그:
  - `logs/syn-s1-20260218-211731-preprocess.log`
  - `logs/syn-s1-20260218-211731-runner.log`
  - `logs/syn-s2-20260218-211731-preprocess.log`
  - `logs/syn-s2-20260218-211731-runner.log`
  - `logs/syn-s3-20260218-211731-preprocess.log`
  - `logs/syn-s3-20260218-211731-runner.log`
- quick-gate 로그:
  - `logs/quick-gate-pytest-20260218-211752.log`
  - `logs/quick-gate-smoke-20260218-211752.log`

### 9) 최종 결론
- synthetic CSV(S1/S2/S3) 입력 기반 E2E 본선 경로(`preprocessing -> training.runner -> artifacts`) 검증 완료.
- quick-gate 핵심 최소 세트도 PASS.
- **Blocker 없음, 요청된 범위 전체 완료.**
