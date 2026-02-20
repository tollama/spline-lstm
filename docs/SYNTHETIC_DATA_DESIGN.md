# SYNTHETIC_DATA_DESIGN

## 0) 문서 목적
- Spline-LSTM 프로젝트에서 사용할 **현실형 synthetic data 생성 시나리오 3종(S1/S2/S3)**을 표준화한다.
- 데이터 생성/검증/테스트가 같은 계약(contract)을 보도록 파라미터, ground truth 보존 규칙, phase 연결 지점을 고정한다.
- 본 문서는 구현팀(Coder)·검증팀(Tester)·리뷰어(Reviewer)가 바로 실행 가능한 수준의 설계 기준이다.

---

## 1) 시나리오 정의 (S1/S2/S3)

### S1. 기본형 (추세 + 계절성 + 노이즈)
**목적**
- 모델/파이프라인의 최소 동작 보증(smoke + 기본 회귀 성능 확인)
- 재현 가능한 baseline 데이터셋 제공

**신호 구성**
- `y(t) = trend(t) + seasonality(t) + epsilon(t)`
- trend: 선형 또는 완만한 2차 추세
- seasonality: 일/주기 성분(단일 혹은 2중 주기)
- epsilon: 가우시안 white noise

**특징**
- 결측/이상치 없음
- 균일 샘플링(regular interval)
- 스키마 완전 준수

---

### S2. 현실형 (이벤트 + 결측 + 이상치 + 불규칙 샘플링)
**목적**
- 운영 환경에서 자주 발생하는 데이터 품질 이슈를 반영
- 전처리(spline/interpolation/정렬) + 학습 robust성 평가

**신호 구성**
- S1 기반 신호에 다음 교란을 주입
  1. 이벤트 충격(event shock): 특정 구간 level shift / transient spike
  2. 결측(missing): MCAR + MAR 혼합
  3. 이상치(outlier): 단발성 스파이크 + 짧은 구간 plateau 이상값
  4. 불규칙 샘플링(irregular sampling): timestamp jitter + 랜덤 드롭

**특징**
- 데이터 계약은 유지(컬럼명/타입은 정상)
- 품질 문제는 전처리 단계에서 복구 가능 범위 내로 제한

---

### S3. 가혹형 (drift + covariate 누락 + 스키마 오류)
**목적**
- fail-fast/guardrail/복구 전략 검증
- 모델 성능 저하 조기 감지 및 차단 메커니즘 테스트

**신호 구성**
- S2 기반 + 다음 리스크 추가
  1. Concept/Distribution drift: 시점 이후 추세 기울기·분산·계절 진폭 변화
  2. Covariate 누락: 외생 변수 일부 컬럼 대량 누락 또는 전구간 결측
  3. 스키마 오류: 컬럼 타입 불일치, 필수 컬럼 누락, timestamp 역정렬/중복

**특징**
- 일부 케이스는 의도적으로 학습 불가 상태를 만든다(정상 동작이 아니라 **정상 실패**가 기대 결과).
- 품질 저하 허용이 아닌, 에러 코드/검증 메시지/차단 동작 확인이 핵심.

---

## 2) 시나리오별 파라미터 표

### 2.1 공통 파라미터
| 파라미터 | 기본값 | 범위/옵션 | 설명 |
|---|---:|---|---|
| seed | 123 | int | 전 구간 재현성 고정 |
| n_samples | 800 | 240~5000 | 총 시점 수 |
| freq | 1h | 5m/15m/1h/1d | 기준 샘플링 간격 |
| horizon | 1 | 1~24 | 예측 horizon |
| train/val/test | 0.6/0.2/0.2 | 합=1.0 | split 비율 |
| noise_std | 0.08 | 0.0~0.3 | 기본 노이즈 세기 |

### 2.2 S1 파라미터
| 그룹 | 파라미터 | 기본값 | 범위/옵션 | 규칙 |
|---|---|---:|---|---|
| Trend | trend_type | linear | linear/quadratic | 기본 linear |
| Trend | trend_slope | 0.01 | 0.001~0.05 | 양의 추세 기본 |
| Seasonality | period_1 | 24 | 12~168 | 1차 계절 주기 |
| Seasonality | amp_1 | 1.0 | 0.2~3.0 | 1차 진폭 |
| Seasonality | period_2 | null | 6~84 또는 null | 보조 계절성(선택) |
| Noise | noise_dist | gaussian | gaussian/student_t | 기본 gaussian |
| Noise | noise_std | 0.08 | 0.0~0.3 | 공통값 사용 가능 |

### 2.3 S2 파라미터
| 그룹 | 파라미터 | 기본값 | 범위/옵션 | 규칙 |
|---|---|---:|---|---|
| Event | event_count | 3 | 1~10 | 랜덤 구간 이벤트 수 |
| Event | event_magnitude | 2.5σ | 1.0~6.0σ | level shift/spike 강도 |
| Missing | missing_rate | 0.08 | 0.01~0.25 | 전체 결측 비율 |
| Missing | mcar_ratio | 0.6 | 0~1 | MCAR 비중 |
| Missing | mar_ratio | 0.4 | 0~1 | MAR 비중(=1-mcar) |
| Outlier | outlier_rate | 0.01 | 0.001~0.05 | 단발성 이상치 비율 |
| Outlier | outlier_scale | 4.0σ | 2.0~10.0σ | 이상치 크기 |
| Sampling | jitter_ratio | 0.15 | 0~0.5 | 간격 지터 비율 |
| Sampling | drop_rate | 0.05 | 0~0.2 | timestamp 드롭 비율 |

### 2.4 S3 파라미터
| 그룹 | 파라미터 | 기본값 | 범위/옵션 | 규칙 |
|---|---|---:|---|---|
| Drift | drift_start_ratio | 0.65 | 0.4~0.9 | 전체 시점 중 drift 시작 위치 |
| Drift | drift_slope_mult | 1.8 | 1.1~4.0 | 추세 기울기 증폭 |
| Drift | var_mult | 1.6 | 1.0~3.0 | 분산 증폭 |
| Covariate | cov_missing_cols | 1 | 1~N_cov | 누락 covariate 컬럼 수 |
| Covariate | cov_missing_rate | 0.5 | 0.1~1.0 | 컬럼별 결측 비율 |
| Schema | schema_error_type | missing_col | missing_col/type_mismatch/timestamp_disorder/duplicate_ts | 오류 유형 |
| Schema | schema_error_rate | 0.02 | 0.005~0.1 | 오류 레코드 비율 |

---

## 3) Ground Truth 보존 규칙

### 3.1 핵심 원칙
1. **원천 신호 분리 저장**: `y_clean`(교란 전), `y_observed`(교란 후)를 모두 저장
2. **주입 이력 로그화**: 이벤트/결측/이상치/drift/스키마 오류를 row-level mask로 보존
3. **복원 결과 분리**: 전처리 산출(`y_imputed` 등)은 ground truth를 덮어쓰지 않음
4. **시드 고정 재현성**: 동일 seed + 동일 파라미터면 동일 데이터 생성
5. **평가 공정성**: baseline/LSTM 비교는 동일 split·동일 scale·동일 horizon 사용

### 3.2 필수 메타 필드(권장 저장 키)
- `series_id`
- `timestamp`
- `y_clean`
- `y_observed`
- `is_missing`
- `is_outlier`
- `is_event`
- `is_drift_segment`
- `schema_error_tag` (S3)
- `split` (train/val/test)
- `seed`
- `scenario_id` (`S1|S2|S3`)

### 3.3 금지 규칙
- 전처리 결과로 `y_clean` overwrite 금지
- 테스트 단계에서 split 재샘플링 금지(비교 실험 시 split 고정)
- S3 스키마 오류 케이스를 정상 학습 케이스와 혼합 집계 금지

---

## 4) Phase별 테스트 연결 지점

| Phase | 연결 목적 | 적용 시나리오 | 핵심 검증 포인트 | 연계 테스트/문서 |
|---|---|---|---|---|
| Phase 1 (Preprocess) | 결측/불규칙 timestamp 복원 품질 | S2, S3(부분) | 보간 성공, 정렬/중복 처리, fail-fast | `tests/test_preprocessing_pipeline.py`, `docs/TEST_RESULTS_PHASE1.md` |
| Phase 2 (Runner CLI/Contract) | synthetic 입력 계약/아티팩트 무결성 | S1 | CLI 계약, 기본 학습 실행, 산출물 생성 | `tests/test_phase2_pipeline.py`, `tests/test_training_runner_cli_contract.py`, `docs/PHASE2_ARCH.md` |
| Phase 3 (Repro/Baseline) | 재현성 및 baseline 공정성 | S1, S2(light) | seed 고정, baseline 동일 split 비교 | `tests/test_phase3_repro_baseline.py`, `docs/TEST_RESULTS_PHASE3_FIXPASS.md` |
| Phase 4 (E2E Smoke) | 원클릭 E2E 안정성 | S1 기본 + S2 축약 | one-click 실행, run_id guard, health check | `docs/E2E_TEST_PLAN.md`, `docs/TEST_RESULTS_PHASE4_FIXPASS2.md` |
| Phase 5 (Extension/Robustness) | multivariate/covariate 확장 내구성 | S2, S3 | covariate 계약, 실패 케이스 격리, 비교표 일관성 | `tests/test_phase5_extension.py`, `docs/PHASE5_ARCH.md`, `docs/TEST_RESULTS_PHASE5.md` |

---

## 5) 수용 기준 (합격 기준)

### 5.1 S1 합격 기준
- [ ] 동일 seed 재실행 2회 시 생성 데이터 해시/요약통계가 동일
- [ ] 학습 파이프라인이 에러 없이 완료되고 metrics/report/checkpoint 생성
- [ ] baseline 비교 로직이 동일 split 기준으로 계산됨(공정성 위반 0건)

### 5.2 S2 합격 기준
- [ ] 결측/이상치/불규칙 샘플링 주입률이 설정값 대비 ±10%p 이내
- [ ] 전처리 후 필수 입력 shape/정렬 조건을 충족
- [ ] 학습 실행 성공률 ≥ 95% (seed 배치 실행 기준)
- [ ] 이벤트 구간에서 에러 지표 상승이 관측되며, 비이벤트 구간 성능이 기준치 이내 유지

### 5.3 S3 합격 기준
- [ ] drift 주입 후 성능 저하(예: RMSE 증가)가 감지/리포팅됨
- [ ] covariate 누락 케이스에서 fallback 또는 명시적 에러 처리 동작 확인
- [ ] 스키마 오류 케이스는 fail-fast로 차단되고 원인 메시지(컬럼/타입/timestamp)가 명시됨
- [ ] 정상 케이스와 비정상 케이스가 리포트에서 분리 집계됨

### 5.4 전체 게이트 기준
- [ ] S1/S2/S3 각각 최소 1개 기본 설정 preset + 1개 스트레스 preset 제공
- [ ] 생성기 파라미터/seed/시나리오 ID가 artifacts 메타에 기록됨
- [ ] CI 또는 수동 검증 문서에 시나리오별 실행 로그(run_id) 첨부

---

## 6) 실행 계획 (즉시 작업 순서)
1. `src/training/runner.py`의 synthetic 생성 경로를 시나리오 플러그인 구조(`--scenario S1|S2|S3`)로 분리
2. 생성 결과를 `y_clean/y_observed + mask` 구조로 저장하는 유틸 추가
3. S2/S3 교란 주입기(event/missing/outlier/drift/schema_error) 모듈화
4. 테스트 매트릭스 추가
   - S1: 재현성/기본 학습
   - S2: 전처리·강건성
   - S3: fail-fast·guardrail
5. 문서/리포트 템플릿에 `scenario_id`, `seed`, `injection_summary` 필드 의무화

---

## 7) 리스크 및 완화
- **리스크**: S2/S3 강도가 과하면 모델 불학습 상태가 일반 케이스까지 오염
  - **완화**: 기본 preset(운영 현실형)과 스트레스 preset(가혹형) 분리
- **리스크**: 불규칙 샘플링 + 결측 조합에서 전처리 복원 편향 발생
  - **완화**: 복원 전/후 오차를 이벤트 구간/비이벤트 구간으로 분리 리포팅
- **리스크**: 스키마 오류 테스트가 학습 테스트와 섞여 CI flakiness 유발
  - **완화**: S3-schema는 독립 잡으로 분리하고 pass 조건을 "정상 실패"로 명시

---

## 8) Standard Handoff Format

### 8.1 Summary
- Spline-LSTM synthetic data를 **S1(기본형) / S2(현실형) / S3(가혹형)** 3단계로 표준화했다.
- 각 시나리오별 파라미터, ground truth 보존 규칙, phase 테스트 연결, 합격 기준을 수치 중심으로 고정했다.

### 8.2 Decisions Locked
- 시나리오 구분: S1(정상), S2(복구 가능 품질 이슈), S3(의도적 실패 포함)
- 평가 공정성: baseline/LSTM 비교 시 동일 split/scale/horizon 강제
- 보존 계약: `y_clean`·`y_observed`·mask 동시 저장, overwrite 금지
- S3는 "학습 성공"이 아니라 "검증 가능한 정상 실패"를 합격 조건으로 허용

### 8.3 Deliverables
- [x] `docs/SYNTHETIC_DATA_DESIGN.md`
- [x] S1/S2/S3 정의 및 파라미터 표
- [x] Ground truth 보존 규칙
- [x] Phase별 테스트 연결 지점
- [x] 수용 기준(합격 기준)

### 8.4 Immediate Next Actions
1. Coder: synthetic generator를 시나리오 기반 모듈로 분리 (`--scenario` 도입)
2. Coder: 주입 마스크/메타 저장 스키마 구현
3. Tester: S1/S2/S3 preset별 테스트 케이스 추가 및 CI job 분리
4. Reviewer: fail-fast 메시지 표준(오류 코드/문구) 리뷰

### 8.5 Risks / Open Points
- drift/이벤트 강도 기본값은 실제 운영 로그 기반으로 1차 보정 필요
- covariate 누락 fallback 정책(제거 vs 대체값 주입) 확정 필요
- schema_error 케이스를 어디까지 학습 파이프라인에서 허용할지 경계 정의 필요
