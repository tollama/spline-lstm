# TEST_RESULTS_SYNTHETIC_DATA

## Standard Handoff Format

### 1) 요청/목표
- 프로젝트: `~/spline-lstm`
- 목표: synthetic data 생성기가 현실형 시나리오를 올바르게 출력하는지 검증
- 필수 검증 항목:
  1. S1/S2/S3 각각 생성 성공
  2. 필수 컬럼/shape/타입 검증
  3. 결측/이상치/불규칙샘플링 주입 검증(S2/S3)
  4. seed 재현성 검증
  5. 실패 시 원인/재현법 기록

### 2) 수행 범위
- 신규 테스트 파일 추가:
  - `tests/test_synthetic_generator.py`
- 검증 대상은 프로젝트 synthetic base signal(`src.training.runner._generate_synthetic`) 기반으로,
  시나리오 S1/S2/S3를 구성하여 생성/주입/재현성 계약을 테스트함.

### 3) 실행 커맨드
```bash
python3 -m pytest -q tests/test_synthetic_generator.py
```

### 4) 결과 요약
- 전체 판정: **PASS**
- 실행 결과: **9 passed, 0 failed**
- 실행 시간: 약 2.39초

### 5) 테스트 상세 결과
- `test_synthetic_s1_s2_s3_generation_success` (param: S1/S2/S3)
  - 시나리오별 DataFrame 생성 성공 확인
- `test_synthetic_required_columns_shape_and_types` (param: S1/S2/S3)
  - 필수 컬럼(`timestamp,target,scenario`), dtype, monotonic/unique timestamp, shape 계약 확인
- `test_s2_injects_missing_and_outliers`
  - S2 결측 주입 및 IQR 기반 이상치 존재 확인
- `test_s3_injects_missing_outliers_and_irregular_sampling`
  - S3 결측/이상치/z-score 및 불규칙 시계열 간격 주입 확인
- `test_seed_reproducibility_same_seed_same_output_and_different_seed_changes`
  - 동일 seed 완전 동일 출력, 다른 seed 출력 변경 확인

### 6) 변경 사항
- 추가 파일:
  - `tests/test_synthetic_generator.py`
  - `docs/TEST_RESULTS_SYNTHETIC_DATA.md`

### 7) 실패 시 원인/재현법 (운영 템플릿)
현재 실행에서는 실패가 없었음. 이후 회귀 발생 시 아래 포맷으로 기록 권장:

```text
[FAIL] <test_nodeid>
- 증상: <assertion/error 요약>
- 원인 후보:
  1) <시나리오 주입 로직 변경>
  2) <dtype/컬럼 계약 변경>
  3) <seed 처리 방식 변경>
- 재현 커맨드:
  python3 -m pytest -q <test_nodeid>
- 최소 재현 입력:
  scenario=<S1|S2|S3>, n_samples=<N>, seed=<SEED>
- 기대/실제:
  expected=<...>
  actual=<...>
```

### 8) 리스크/메모
- 경고(warnings)는 외부 라이브러리(urllib3/matplotlib/pyparsing) deprecation/환경 경고로, 본 테스트 판정에는 영향 없음.
- 본 테스트는 synthetic scenario 계약(생성/주입/재현성)을 빠르게 회귀 검증하기 위한 단위 테스트 세트임.

### 9) 인수인계 메모
- 테스트는 `python3 -m pytest` 기준으로 실행/검증 완료.
- 동일 검증을 CI에 연결하려면 아래 단일 커맨드를 test job에 추가하면 됨:
  - `python3 -m pytest -q tests/test_synthetic_generator.py`
