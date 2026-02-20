# E2E_TEST_ARCHITECTURE — Spline-LSTM E2E 테스트 아키텍처/시나리오 설계

> 기준 코드: `src/preprocessing/pipeline.py`, `src/preprocessing/smoke.py`, `src/training/runner.py`, `src/training/compare_runner.py`, `scripts/run_e2e.sh`, `scripts/smoke_test.sh`  
> 목적: **MVP 본선 경로 보호 + 확장 경로(multivariate/covariates/compare_runner) 품질 게이트 고정**

---

## 0) 목표 / 비목표

### 목표
- preprocess → train → eval → infer → artifacts 전체 경로를 E2E 테스트 관점에서 고정한다.
- 확장 경로(multivariate/covariates/compare_runner)의 입력/출력/아티팩트 계약을 명문화한다.
- 실패코드, 관측지표, 로그 수집 규칙을 CI 친화적으로 정리한다.
- 회귀 테스트 경계선(MVP 본선 보호선)을 정의한다.

### 비목표
- 모델 성능 튜닝(HPO) 또는 SOTA 성능 검증
- 온라인 서빙/배포 인프라 테스트
- 대규모 부하/장기 soak 테스트

---

## 1) E2E 경로 정의 (MVP 본선)

## 1.1 표준 경로 (권장 실행)

```text
[Step-1 Preprocess]
python3 -m src.preprocessing.smoke --run-id <RUN_ID> ...
  -> artifacts/processed/<RUN_ID>/processed.npz
  -> artifacts/processed/<RUN_ID>/meta.json
  -> artifacts/models/<RUN_ID>/preprocessor.pkl

[Step-2 Train/Eval/Infer]
python3 -m src.training.runner --run-id <RUN_ID> --processed-npz ... --preprocessor-pkl ...
  -> artifacts/checkpoints/<RUN_ID>/best.keras
  -> artifacts/checkpoints/<RUN_ID>/last.keras
  -> artifacts/metrics/<RUN_ID>.json
  -> artifacts/reports/<RUN_ID>.md
  -> artifacts/baselines/<RUN_ID>.json
  -> artifacts/splits/<RUN_ID>.json
  -> artifacts/configs/<RUN_ID>.json
  -> artifacts/metadata/<RUN_ID>.json
```

자동화 엔트리 포인트:
- `bash scripts/run_e2e.sh` (원클릭 본선)
- `bash scripts/smoke_test.sh` (짧은 게이트)

## 1.2 E2E 시나리오 세트 (본선)

- **E2E-CORE-01 (Happy Path)**
  - 입력: synthetic smoke (`src.preprocessing.smoke` 기본 입력)
  - 기대: exit=0, metrics/report/checkpoint/preprocessor 생성
- **E2E-CORE-02 (run_id 일관성 가드)**
  - 입력: `--run-id`와 preprocessor run_id 의도적 불일치
  - 기대: `run_id mismatch` 예외로 실패(즉시 차단)
- **E2E-CORE-03 (metrics 계약 검증)**
  - 입력: 정상 러너 완료 후 `artifacts/metrics/<run_id>.json`
  - 기대: `metrics.mae/rmse/mape/r2` 필수 키 존재
- **E2E-CORE-04 (추론 산출 검증)**
  - 입력: runner 결과 JSON
  - 기대: `inference.y_true_last`, `inference.y_pred_last` 존재 및 길이=horizon

---

## 2) 확장 경로 정의 (multivariate / covariates / compare_runner)

## 2.1 Multivariate + Covariates 전처리 경로

트리거:
- `PreprocessingConfig(covariate_cols=(...))`

추가 산출물(현재 구현 기준 `processed.npz`):
- `covariates_raw`
- `features_scaled` (target + covariates)
- `X_mv`, `y_mv`

확장 E2E 시나리오:
- **E2E-EXT-01 (covariate 경로 생성)**
  - 기대: `X_mv.shape[2] == 1 + len(covariate_cols)`
- **E2E-EXT-02 (스키마 검증 실패 경로)**
  - 입력: 누락/비수치 covariate
  - 기대: 전처리 단계에서 실패, train 미진입

## 2.2 compare_runner 경로

실행:
- `python3 -m src.training.compare_runner --run-id <RUN_ID> ...`

산출물:
- `artifacts/comparisons/<RUN_ID>.json`
- `artifacts/comparisons/<RUN_ID>.md`

확장 E2E 시나리오:
- **E2E-EXT-03 (LSTM vs GRU 비교 실행)**
  - 기대: JSON 내 `models.lstm.metrics`, `models.gru.metrics`, `summary.winner_by_rmse`
- **E2E-EXT-04 (비교 리포트 최소 계약)**
  - 기대: markdown에 run_id, winner, RMSE(LSTM/GRU) 포함

---

## 3) 입력/출력/아티팩트 계약

## 3.1 단계별 I/O 계약

| 단계 | 입력 계약 | 출력 계약 |
|---|---|---|
| preprocess | CSV/Parquet + `timestamp_col` + `target_col`(+ optional covariates), `run_id` 유효 문자열 | `processed.npz`, `meta.json`, `preprocessor.pkl` |
| train/eval/infer | `--run-id`, `--processed-npz`(optional), `--preprocessor-pkl`(optional), 학습 하이퍼파라미터 | metrics/report/checkpoints/baselines/splits/configs/metadata |
| compare_runner | 시계열 입력(또는 synthetic), 공통 학습 설정 | comparisons json/md + 모델별 metrics |

## 3.2 아티팩트 최소 필수 키 계약

### `artifacts/processed/<run_id>/processed.npz`
- 필수: `X`, `y`, `timestamps`, `raw_target`, `interpolated`, `smoothed`, `scaled`
- 조건부(확장): `covariates_raw`, `features_scaled`, `X_mv`, `y_mv`

### `artifacts/processed/<run_id>/meta.json`
- 필수: `run_id`, `input_path`, `n_rows`, `X_shape`, `y_shape`
- 확장: `covariate_cols`, `X_mv_shape`, `y_mv_shape`

### `artifacts/models/<run_id>/preprocessor.pkl`
- 필수: `run_id`, `spline`, `scaler`, `config`, `multivariate`

### `artifacts/metrics/<run_id>.json`
- 필수 상위: `run_id`, `metrics`, `checkpoints`, `inference`, `config`
- 필수 지표: `metrics.mae`, `metrics.rmse`, `metrics.mape`, `metrics.r2`

---

## 4) 실패코드 / 관측지표 / 로그 수집 규칙

## 4.1 실패코드 체계 (테스트 레이어 표준)

> 현재 구현은 Python 예외 + 쉘 `exit 1` 중심이다.  
> E2E 테스트 보고서/CI에서는 아래 **논리 실패코드**로 정규화해 기록한다.

| 코드 | 분류 | 의미 | 대표 트리거 |
|---|---|---|---|
| E2E-F001 | Input Contract | 입력 파일 미존재/형식 불량 | `FileNotFoundError`, schema 검증 실패 |
| E2E-F002 | RunID Contract | run_id 불일치/부적합 | `run_id mismatch`, invalid run_id |
| E2E-F003 | Artifact Contract | 필수 아티팩트 누락 | smoke_test 파일 존재 검사 실패 |
| E2E-F004 | Metrics Contract | metrics 필수 키 누락 | `mae/rmse/mape/r2` 부재 |
| E2E-F005 | Backend/Runtime | TF backend 미설치/런타임 오류 | `TensorFlow backend is required` |
| E2E-F006 | Extension Path | multivariate/compare 확장 경로 실패 | `X_mv` 미생성, comparison payload 누락 |

## 4.2 관측지표(Observability) 수집 규칙

필수 수집(각 run_id 단위):
1. **정확도 지표**: mae, rmse, mape, r2
2. **재현성 지표**: seed, config snapshot, split indices, commit hash
3. **추론 스냅샷**: `y_true_last`, `y_pred_last`
4. **아티팩트 무결성**: 필수 파일 존재 + JSON key schema

권장 수집:
- 단계별 소요 시간(preprocess/train/eval/infer)
- 실패 발생 단계와 예외 메시지 원문

## 4.3 로그 수집 규칙

- 콘솔 로그는 단계 prefix 고정:
  - `[E2E]` (run_e2e), `[SMOKE]` (smoke_test)
- 실패 시 아래 3종을 함께 저장:
  1) stdout
  2) stderr
  3) run_id 및 실행 커맨드 원문
- CI 아카이브 단위: `run_id` 폴더 기준으로 raw 로그 + 아티팩트 인덱스 저장

---

## 5) 회귀 테스트 경계선 (MVP 본선 보호)

## 5.1 절대 보호선 (깨지면 배포 차단)

1. **본선 E2E 성공**: `scripts/run_e2e.sh` 1회 성공
2. **스모크 게이트 통과**: `scripts/smoke_test.sh` 통과
3. **run_id 가드 유지**: mismatch 시 반드시 실패
4. **metrics 계약 유지**: `mae/rmse/mape/r2` 필수
5. **핵심 아티팩트 경로 유지**: processed/preprocessor/checkpoints/metrics/report

## 5.2 확장 보호선 (MVP 확장 안정화)

1. covariate 전처리 시 `X_mv/y_mv` 저장 유지
2. compare_runner 결과에 모델 2종(lstm/gru) metrics 유지
3. 확장 실패가 본선 경로를 깨뜨리지 않을 것(기본 univariate 경로 항상 동작)

## 5.3 권장 게이트 순서 (CI)

1) Fast unit/contracts (`tests/test_training_runner_cli_contract.py`, run_id guard 관련)  
2) Preprocess 계약 (`test_preprocessing_*`, `test_phase5_multivariate_proto.py`)  
3) 본선 smoke (`scripts/smoke_test.sh`)  
4) 확장 smoke (`compare_runner`, covariate 경로)

---

## 6) 실행 템플릿 (운영/CI 공용)

### 6.1 본선 E2E

```bash
RUN_ID=e2e-core-$(date +%Y%m%d-%H%M%S) EPOCHS=1 bash scripts/run_e2e.sh
```

### 6.2 본선 Smoke Gate

```bash
RUN_ID=smoke-core-$(date +%Y%m%d-%H%M%S) bash scripts/smoke_test.sh
```

### 6.3 확장 Compare Gate

```bash
python3 -m src.training.compare_runner --run-id compare-$(date +%Y%m%d-%H%M%S) --epochs 3
```

---

## 7) Standard Handoff Format

### 7.1 Summary
- Spline-LSTM E2E 테스트를 **본선 경로**(preprocess→train→eval→infer→artifacts)와 **확장 경로**(multivariate/covariates/compare_runner)로 분리해 아키텍처를 고정했다.
- 계약 중심으로 입력/출력/아티팩트/실패코드/관측지표를 정의해 CI 게이트화가 가능하다.

### 7.2 Decisions Locked
- 본선 필수 게이트: run_e2e + smoke_test + run_id mismatch 차단 + metrics key 보장
- 확장 필수 게이트: `X_mv/y_mv` 생성 계약 + compare_runner payload 계약
- 실패는 예외/exit code를 테스트 레이어 논리코드(E2E-F001~F006)로 정규화

### 7.3 Deliverables
- [x] `docs/E2E_TEST_ARCHITECTURE.md`
- [x] 본선/확장 E2E 경로 정의
- [x] I/O/아티팩트 계약 정의
- [x] 실패코드/관측/로그 수집 규칙 정의
- [x] MVP 회귀 경계선 정의

### 7.4 Immediate Next Actions
1. CI에서 `scripts/smoke_test.sh`를 필수 게이트로 승격
2. compare_runner smoke를 별도 확장 게이트(job)로 추가
3. 실패 시 E2E-F 코드 매핑 리포터(pytest plugin 또는 CI post-step) 적용
4. 단계별 duration 지표(preprocess/train/eval)를 metrics payload에 추가

### 7.5 Risks / Open Points
- TensorFlow backend 의존 경로는 환경 차이에 따라 flaky 가능
- 확장 경로(multivariate)는 현재 PoC 수준이므로 스키마 강제 수준을 점진적으로 상향 필요
- 실패코드는 아직 애플리케이션 exit code로 고정되어 있지 않아, CI 레이어 정규화가 선행되어야 함
