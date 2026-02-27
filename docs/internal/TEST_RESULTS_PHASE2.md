# TEST_RESULTS_PHASE2

Date: 2026-02-18
Scope: Spline-LSTM MVP Phase 2 테스트 (학습/평가/추론 E2E + artifact 검증)

## 실행 커맨드

```bash
cd /Users/ychoi/spline-lstm
python3 -m pytest -q tests/test_phase2_pipeline.py -vv
```

## 결과 요약

- Passed: 1
- Skipped: 1
- Failed: 0

### 상세

1. `test_phase2_e2e_train_eval_infer_and_artifacts` ✅ PASS
   - synthetic 데이터로 학습 스모크 실행
   - 평가 메트릭(`mae/mse/rmse/mape/r2`) 생성 확인
   - 추론 출력 shape 검증 (`[batch, 1]`)
   - `best`/`last` 체크포인트 및 `*_metrics.json` 생성 확인
   - run_id 기반 artifact 생성 확인:
     - `artifacts/models/{run_id}/model.keras`
     - `artifacts/models/{run_id}/preprocessor.pkl`
     - `artifacts/metrics/{run_id}.json`
     - `artifacts/configs/{run_id}.yaml`
     - `artifacts/reports/{run_id}.md`

2. `test_phase2_runner_cli_smoke` ⏭ SKIP
   - 원인: `src/training/runner.py` 파일 미구현

## 실패/갭 원인 및 재현법

### 갭: Runner CLI smoke 미실행
- 원인: 프로젝트에 `src/training/runner.py`가 존재하지 않음
- 재현:
  ```bash
  cd /Users/ychoi/spline-lstm
  ls src/training/runner.py
  # -> No such file or directory
  ```
- 영향: Blueprint에 명시된 "runner CLI 기반 재현 실행"을 현재 자동 검증할 수 없음

## 산출물

- 신규 테스트 파일: `tests/test_phase2_pipeline.py`
- 결과 문서: `docs/TEST_RESULTS_PHASE2.md`
