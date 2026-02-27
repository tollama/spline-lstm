# PHASE3 Test Failure Log

## Scope
- Test file: `tests/test_phase3_repro_baseline.py`
- Command: `python3 -m pytest -q tests/test_phase3_repro_baseline.py`
- Data policy: synthetic 우선 (CLI synthetic)

## Result Summary
- Total: 2 tests
- Passed: 0
- Failed: 2

## Failure 1 — Baseline comparison
- Test: `test_phase3_reproducibility_and_baseline_vs_model`
- Failure message:
  - `Model did not beat/track naive baseline within tolerance.`
  - `model_rmse=0.257621, baseline_rmse=0.083772, allowed_factor=1.15`
- Observed behavior:
  - 동일 config 재실행 편차 자체는 허용범위 내로 보이나,
  - 현재 짧은 학습 설정(`epochs=2`)에서 persistence baseline보다 모델 RMSE가 크게 높음.
- Suspected causes:
  1. 학습 epoch 부족으로 underfitting
  2. synthetic 파형에서 persistence baseline이 매우 강함
  3. 현재 모델/하이퍼파라미터가 baseline-friendly 설정이 아님

## Failure 2 — Metadata presence
- Test: `test_phase3_metadata_presence_split_config_commit`
- Failure message:
  - `Missing split index metadata. Expected one of keys: split_index/split_indices/split/data_split`
- Observed behavior:
  - runner metrics payload에는 `config`는 존재
  - `split index` 및 `commit hash` 관련 필드 미포함
- Suspected causes:
  1. `src/training/runner.py` payload schema에 split metadata 미구현
  2. git commit hash 수집/주입 로직 미구현 (`.git` 부재 환경도 고려 필요)

## Recommended follow-ups
1. Baseline test 안정화
   - epochs 증가(예: 10~20) 또는 baseline 정의 재검토(평균 baseline vs persistence)
   - 허용 범위를 데이터/seed 기준으로 재보정
2. Metadata 확장
   - payload에 split index(원시 인덱스 경계) 추가
   - commit hash 필드 추가 (`git rev-parse --short HEAD`, 실패 시 `"unknown"` 정책 명시)
3. CI 정책
   - 미구현 항목은 일시적으로 `xfail(strict=True, reason=...)` 처리 후 구현 완료 시 해제
