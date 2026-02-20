# PHASE1_ARCH — Spline-LSTM MVP Phase 1 설계 고정

> 기준 문서: `docs/BLUEPRINT.md`  
> 범위: **Phase 1 = 데이터 계약 + 전처리 기반 고정** (모델 성능 튜닝/확장 모델은 제외)

---

## 1) Phase 1 목표/범위

### 목표
- 입력 데이터 스키마를 엄격히 고정한다.
- 전처리 파이프라인의 I/O 계약(shape, dtype, artifact)을 고정한다.
- 실패 조건/중단 정책을 명문화해 실행 시 모호함을 제거한다.
- 이후 Phase 2(학습/평가 고도화)가 바로 붙을 수 있게 인터페이스를 확정한다.

### 비목표(Phase 1에서 하지 않음)
- GRU/Attention-LSTM 도입
- multivariate/covariates 확장
- walk-forward 백테스트 자동화
- 배포 포맷 최적화(ONNX/TFLite)

---

## 2) 데이터 계약 (입력)

## 2.1 필수 입력 컬럼

| 컬럼 | 타입 | 필수 | 설명 |
|---|---|---:|---|
| `timestamp` | datetime64[ns] (timezone-naive 또는 단일 timezone으로 정규화) | Y | 시계열 시점, 단조 증가 필수 |
| `target` | float64 (내부 처리 float32 캐스팅 허용) | Y | 예측 대상 값 |

### 컬럼 제약
- 컬럼 이름은 정확히 `timestamp`, `target`.
- 추가 컬럼은 Phase 1에서 무시 가능하되, 경고 로그를 남긴다.
- 컬럼 누락 시 즉시 실패.

## 2.2 유효성 검증 규칙

### `timestamp`
1. 파싱 가능해야 함 (`pd.to_datetime` 기준)
2. `NaT` 불가
3. 오름차순 단조 증가(strictly increasing)
4. 중복 시점 불가

### `target`
1. 수치형으로 파싱 가능해야 함
2. `NaN` 허용(결측 보간 대상) — 단, 결측률 상한 적용
3. `inf`, `-inf` 불가
4. 전체 값이 상수(분산 0)면 실패

### 데이터셋 레벨 규칙
1. 최소 행 수: `n_rows >= lookback + horizon + 1`
2. 결측률 상한: `target_missing_ratio <= 0.30`
3. 선/후단 연속 결측 구간 최대 길이: `<= max_gap` (기본 24 step)
4. 시간 간격 불규칙 허용, 단 리샘플링 기준 빈도(`freq`)로 정렬/정규화 후 처리

## 2.3 실패 정책 (Fail-fast)

| 실패 유형 | 정책 | 종료 코드(권장) |
|---|---|---:|
| 필수 컬럼 누락/타입 파싱 실패 | 즉시 중단 | 2 |
| timestamp 단조/중복 위반 | 즉시 중단 | 3 |
| target의 inf/상수 시계열 | 즉시 중단 | 4 |
| 결측률 상한 초과 | 즉시 중단 | 5 |
| 보간 불가(과도한 gap 등) | 즉시 중단 | 6 |

실패 시 공통 출력:
- `artifacts/reports/{run_id}_data_validation.md`에 실패 원인/행 수/비율 기록
- STDERR에 한 줄 요약 에러 출력
- 부분 산출물(깨진 processed 파일)은 저장하지 않음

---

## 3) 전처리 I/O 계약

## 3.1 입력 (preprocess 단계)
- 입력 객체: `pd.DataFrame`
- 입력 스키마: 위 데이터 계약 준수
- 필수 파라미터:
  - `lookback: int` (>= 1)
  - `horizon: int` (>= 1)
  - `freq: str` (예: `"H"`, `"D"`)
  - `split_ratio: tuple[float,float,float]` (합=1.0)
  - `scaler_type: str` (`standard` | `minmax`)

## 3.2 처리 단계 (고정 순서)
1. Schema validation
2. Timestamp 정렬/중복 검증
3. `freq` 기준 리샘플링(필요 시)
4. 스플라인 보간(interpolate)
5. 평활(smoothing; 파라미터화)
6. Train/Val/Test 시간순 분할
7. Scaler fit(train only) + transform(all)
8. Window 생성

## 3.3 출력 (메모리 객체 계약)

### Split 텐서 shape
- `X_train`: `[N_train, lookback, 1]`, dtype `float32`
- `y_train`: `[N_train, horizon]`, dtype `float32`
- `X_val`: `[N_val, lookback, 1]`, dtype `float32`
- `y_val`: `[N_val, horizon]`, dtype `float32`
- `X_test`: `[N_test, lookback, 1]`, dtype `float32`
- `y_test`: `[N_test, horizon]`, dtype `float32`

### 인덱스/메타
- `time_index_*`: 각 split의 y 기준 timestamp 배열
- `meta` 예시:
  - `run_id`, `freq`, `lookback`, `horizon`
  - `n_raw`, `n_after_resample`, `missing_ratio_before/after`
  - `scaler_type`, `spline_params`, `smoothing_params`

## 3.4 스케일러 저장/로딩 계약

### 저장
- 파일: `artifacts/models/{run_id}/preprocessor.pkl`
- 포함 객체:
  - scaler 인스턴스
  - 입력 feature 순서(Phase 1은 `['target']`)
  - 전처리 파라미터(freq/lookback/horizon/spline/smoothing)
  - 버전 메타(`schema_version: "phase1.v2"`)

### 로딩
- 추론 시 `model.pt`와 `preprocessor.pkl`의 `run_id` 일치 필수
- `schema_version` 불일치 시 실패
- 로드 후 최소 검증:
  - `feature_order == ['target']`
  - `lookback/horizon`이 모델 메타와 일치

---

## 4) Artifact 경로 규칙

## 4.1 run_id 규칙
- 형식: `YYYYMMDD_HHMMSS_<shortsha>`
- 예: `20260218_172300_a1b2c3d`

## 4.2 산출물 경로
- 처리 데이터(bundle): `artifacts/processed/{run_id}/processed.npz`
- 전처리 메타: `artifacts/processed/{run_id}/meta.json`
- split 계약 파일: `artifacts/processed/{run_id}/split_contract.json`
- 스케일러/전처리 객체: `artifacts/models/{run_id}/preprocessor.pkl`
- 학습 체크포인트(Phase 2 연계): `artifacts/checkpoints/{run_id}/{best,last}.keras`
- 설정 스냅샷: `artifacts/configs/{run_id}.json`
- 검증/실패 리포트: `artifacts/reports/{run_id}_data_validation.md`

## 4.3 일관성 규칙
- 동일 run_id 하위 산출물만 상호 참조 가능
- 기존 run_id 재사용 금지(immutability)
- 동일 실행에서 파일 누락 시 실행 실패 처리

---

## 5) 구현 인터페이스 제안 (Phase 1)

## 5.1 모듈별 책임
- `src/preprocessing/validators.py`
  - `validate_schema(df) -> None`
  - `validate_timestamp(df) -> None`
  - `validate_target(df, config) -> None`
- `src/preprocessing/spline.py`
  - `apply_spline(series, config) -> pd.Series`
  - `apply_smoothing(series, config) -> pd.Series`
- `src/preprocessing/transform.py`
  - `split_time_series(df, ratios) -> dict`
  - `fit_transform_scaler(train, val, test, scaler_type) -> dict`
- `src/preprocessing/window.py`
  - `make_windows(array, lookback, horizon) -> tuple[X, y]`

## 5.2 CLI 계약 (현행 구현 기준)
```bash
python3 -m src.preprocessing.smoke \
  --input data/raw/series.csv \
  --run-id 20260218_172300_a1b2c3d \
  --lookback 24 \
  --horizon 1 \
  --scaling standard
```

### CLI 성공 조건
- 종료 코드 0
- `artifacts/processed/{run_id}/processed.npz` 생성
- `artifacts/processed/{run_id}/meta.json` 생성
- `artifacts/models/{run_id}/preprocessor.pkl` 생성

---

## 6) Acceptance Criteria (테스트 관점)

## AC-1 스키마 검증 성공
- Given: `timestamp,target`가 존재하고 타입이 유효한 CSV
- When: preprocess 실행
- Then: 검증 통과 및 processed artifact 생성

## AC-2 필수 컬럼 누락 실패
- Given: `target` 컬럼이 없는 입력
- When: preprocess 실행
- Then: 종료 코드 2로 실패, validation 리포트 생성

## AC-3 timestamp 단조 위반 실패
- Given: timestamp 역전 행이 포함된 입력
- When: preprocess 실행
- Then: 종료 코드 3으로 즉시 실패

## AC-4 결측률 상한 초과 실패
- Given: `target` 결측률이 30% 초과
- When: preprocess 실행
- Then: 종료 코드 5로 실패, 결측률 수치가 리포트에 기록됨

## AC-5 윈도우 shape 계약 준수
- Given: 유효 입력 + `lookback=24`, `horizon=12`
- When: preprocess 완료
- Then: `X_*` shape `[N,24,1]`, `y_*` shape `[N,12]`, dtype `float32`

## AC-6 스케일러 저장/로딩 일치
- Given: preprocess로 생성된 `preprocessor.pkl`
- When: 추론 준비 단계에서 로딩
- Then: `schema_version`, `run_id`, `feature_order` 검증 통과

## AC-7 run_id 경로 일관성
- Given: 단일 실행 run_id
- When: 산출물 저장
- Then: 모든 산출물이 동일 run_id 경로 하위에 존재

## AC-8 재실행 불변성
- Given: 동일 입력/동일 config/동일 seed
- When: preprocess 2회 실행
- Then: `processed.parquet` row 수와 split index가 동일

---

## 7) 즉시 실행 체크리스트

- [ ] `validators.py` 추가 및 실패 코드 매핑 구현
- [ ] `spline.py`에 보간/평활 파라미터 명시적 입력 적용
- [ ] `transform.py`, `window.py` 생성 후 shape assert 추가
- [ ] `preprocessor.pkl` 직렬화 스키마(`phase1.v2`) 고정
- [ ] `tests/preprocessing/`에 AC-1~AC-8 대응 테스트 작성
- [ ] `configs/phase1.yaml` 기본 템플릿 작성

---

## 8) Phase 1 DoD
- 데이터 계약 문서와 구현이 일치한다.
- 전처리 I/O(shape/dtype/artifact) 계약이 테스트로 고정된다.
- 실패 정책이 코드/리포트/종료코드로 재현 가능하다.
- Phase 2 팀이 `model.pt` 연결만으로 학습 파이프라인을 시작할 수 있다.
