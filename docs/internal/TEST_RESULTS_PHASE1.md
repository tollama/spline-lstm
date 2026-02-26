# Spline-LSTM MVP Phase 1 — Test Results

Date (KST): 2026-02-18
Scope: 데이터 계약 / 전처리 / artifact(run_id) 규칙 검증

## 1) 추가된 테스트

### A. 데이터 계약 테스트 (schema/type/shape)
- `tests/test_data_contract.py`
  - `TestSupervisedDataContract::test_to_supervised_schema_shape_and_type`
    - `to_supervised` 출력 계약 검증
    - `X: [batch, lookback, 1]`, `y: [batch, horizon]` 확인
    - numpy/float dtype 확인
  - `TestSupervisedDataContract::test_to_supervised_rejects_nan_inf`
    - NaN/Inf 입력 거부 확인
  - `TestSupervisedDataContract::test_to_supervised_rejects_invalid_params_or_short_series`
    - lookback/horizon 양수 제약 및 최소 길이 제약 확인
  - `TestLSTMInputContract::*`
    - LSTM 입력/출력 shape 계약(`_validate_xy`) 검증

### B. 전처리 파이프라인 테스트 (결측/불규칙 timestamp)
- `tests/test_preprocessing_pipeline.py`
  - `test_interpolate_missing_with_internal_and_edge_nans`
    - 결측치(내부+경계) 보간 동작 검증
  - `test_irregular_timestamp_fit_and_missing_point_reconstruction`
    - 불규칙하지만 증가하는 timestamp에서 spline fit/복원 검증
    - synthetic smooth signal 기준 복원 MAE threshold 검증
  - `test_fit_rejects_non_increasing_timestamps`
    - 비증가 timestamp 거부 검증

### C. Artifact 저장/로드 테스트 (run_id 규칙)
- `tests/test_artifacts.py`
  - `test_save_run_artifacts_and_validate_run_id_match`
    - run_id 스코프 경로 생성, 파일 생성, metrics 내용, run_id 일치 검증
  - `test_validate_artifact_run_id_mismatch_raises`
    - model/preprocessor run_id 불일치 시 예외 확인
  - `test_save_run_artifacts_rejects_invalid_run_id`
    - 빈 문자열/공백/경로 구분자 포함 run_id 거부 확인
  - `test_load_checkpoint_calls_model_load`
    - load_checkpoint가 model.load를 호출하는지 검증

> 모든 테스트 데이터는 synthetic data 사용.

---

## 2) 스모크 테스트 명령

```bash
python3 -m pytest -q tests -v
```

## 3) 스모크 테스트 결과

최종 결과:
- `20 collected`
- `18 passed, 2 skipped`
- 소요 시간: 약 6.97s

스킵 사유:
- `tests/test_models.py` 내 TensorFlow 의존 테스트 2건 (`RUN_ML_TESTS` 미설정)

---

## 4) 실패 이력 및 원인 (요청사항 반영)

초기 실행 실패 원인:
1. `pytest` CLI 미설치/미노출 (`command not found: pytest`)
   - 대응: `python3 -m pytest`로 실행
2. `ModuleNotFoundError: No module named 'scipy'`
   - 대응: `python3 -m pip install scipy`
3. `ModuleNotFoundError: No module named 'pandas'`
   - 대응: `python3 -m pip install pandas`

조치 후 재실행 결과:
- 전체 테스트 정상 통과(18 passed, 2 skipped)
