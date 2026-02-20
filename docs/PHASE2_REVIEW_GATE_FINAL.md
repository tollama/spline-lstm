# PHASE 2 REVIEW — GATE C FINAL

- Reviewer: `reviewer-spline-mvp-phase2-gate-final`
- Date: 2026-02-18
- Scope: `coder-spline-mvp-phase2-fixpass` 반영 후 Gate C 최종 판정

## 검증 요약

### 1) preprocessing pipeline에서 split 이전 scaler fit 제거 여부
**결론: PASS**

`src/preprocessing/pipeline.py`에서 `chronological_split(series_smooth)` 후 **train 구간만**으로 scaler를 fit하고, 전체 시계열은 transform만 수행함.

- 근거: `src/preprocessing/pipeline.py:74-78`
  - `train_smooth, _, _, _ = chronological_split(series_smooth)`
  - `scaler.fit(train_smooth)`
  - `series_scaled = scaler.transform(series_smooth)`

---

### 2) train-only fit / val-test transform 여부
**결론: PASS**

`Trainer.train()`에서 raw series를 train/val/test로 먼저 분할한 뒤, normalizer는 train에만 fit하고 val/test는 transform만 수행함.

- 근거: `src/training/trainer.py:185-191`
  - `train_raw, val_raw, test_raw = self.split_series(...)`
  - `norm_params = self.fit_normalizer(train_raw, ...)`
  - `val_raw = self.normalize(val_raw, norm_params)`
  - `test_raw = self.normalize(test_raw, norm_params)`

---

### 3) 데이터 누수/shape 계약/재현성/체크포인트 무결성 재점검

#### 3-1. 데이터 누수
- **Training 경로 누수 방지: PASS**
  - `tests/test_training_leakage.py` 통과 (train-only fit, validation_data 명시, shuffle=False)

- **Preprocessing 경로 추가 누수 방지: PASS**
  - 상기 1) 항목 확인 완료

#### 3-2. Shape 계약
- **PASS**
  - `tests/test_data_contract.py` 통과 (to_supervised / LSTM input-output shape 계약 검증)

#### 3-3. 재현성
- **부분 충족 (SHOULD)**
  - `src/training/runner.py`에서 `np.random.seed(args.seed)` 및 TF seed 설정은 존재
  - 다만 완전 결정론(backend deterministic op 강제, 환경 고정)까지는 명시적으로 보장하지 않음

#### 3-4. 체크포인트 무결성
- **부분 충족 + 회귀 1건**
  - 아티팩트 run_id 일관성 검증 로직은 존재/테스트 통과 (`tests/test_artifacts.py`)
  - 그러나 전체 테스트에서 `test_phase2_runner_cli_smoke` 실패:
    - 원인: 테스트가 사용하는 CLI 옵션(`--synthetic`, `--checkpoints-dir`)이 현재 `runner.py` 인자 정의와 불일치
    - 근거:
      - 테스트: `tests/test_phase2_pipeline.py:130-134`
      - 파서: `src/training/runner.py:214-238`

---

## Must / Should / Nice

## Must fix
1. **`SplinePreprocessor.interpolate_missing()`가 결측치가 없는 입력에서 예외 발생**
   - 영향: 정상(결측 없음) 데이터에서도 preprocessing pipeline 실패 가능
   - 재현: `run_preprocessing_pipeline()` 실행 시 `ValueError: x must be non-empty`
   - 원인: `missing_mask`가 전부 False일 때 `self.transform(x[missing_mask])`가 빈 배열 호출
   - 근거: `src/preprocessing/spline.py:154-155`

2. **Phase2 runner CLI 계약 불일치로 E2E smoke 실패**
   - 영향: CI Gate에서 runner 경로 회귀, 체크포인트 포함 E2E 검증 실패
   - 실패 테스트: `tests/test_phase2_pipeline.py::test_phase2_runner_cli_smoke`
   - 원인: 테스트 인자(`--synthetic`, `--checkpoints-dir`)와 `build_parser()` 정의 불일치

## Should fix
1. 재현성 강화를 위해 deterministic 실행 가이드/옵션(backend deterministic 플래그, 버전 pinning) 명시
2. preprocessing leakage 방지(Train-only scaler fit)에 대한 전용 단위테스트 추가

## Nice to have
1. `processed.npz` 로드 시 `scaled` 우선 사용 정책에 대한 문서화(학습 경로별 normalization 책임 분리)
2. `runner.py --help` 기준으로 테스트/문서 CLI 옵션 동기화 자동 점검

---

## Gate C 최종 판정

- **Must fix 개수: 2**
- **Gate C: FAIL**

> 규칙: Must fix = 0 이어야 PASS.

---

## 실행 근거 (로컬 검증)

- 부분 테스트(누수/shape/아티팩트): `15 passed`
- 전체 테스트: `1 failed, 21 passed, 2 skipped`
  - 유일 실패: `test_phase2_runner_cli_smoke`
