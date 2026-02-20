# PHASE5_ARCH — Spline-LSTM MVP Phase 5 설계 고정

> 기준 문서: `docs/PHASE4_ARCH.md`, `docs/BLUEPRINT.md`  
> 범위: **확장 옵션 설계 고정 (GRU/Attention, multivariate/covariates, edge 후보)**

---

## 0) 목표와 비목표

### 목표
- 모델 확장 옵션(`lstm`, `gru`, `attention_lstm`)을 **단일 러너 계약**으로 고정한다.
- univariate(기존)에서 multivariate/covariates까지 확장 가능한 **입력/출력 shape 계약**을 고정한다.
- 모델 비교 실험(정확도+운영성)을 재현 가능하게 수행할 **실험 설계/비교표 포맷**을 고정한다.
- Edge 후보(ONNX/TFLite)의 PoC 진입/합격 기준을 수치화해 **Go/No-Go 판단 기준**을 고정한다.

### 비목표
- Phase 5에서 대규모 성능 튜닝(HPO) 수행
- 실제 모바일 앱/임베디드 런타임 배포
- 서빙 인프라(온라인 API, A/B 시스템) 구축

---

## 1) Phase 5 아키텍처 개요 (고정)

```text
[Preprocessing Phase4 Contract]
  └─ processed.npz + preprocessor.pkl + meta.json
         │
         ▼
[Phase5 Runner Contract]
  ├─ --model-type {lstm|gru|attention_lstm}
  ├─ --target-cols / --covariate-spec / --feature-mode
  ├─ X: [B, L, F_total]
  └─ y: [B, H * F_target]
         │
         ▼
[Experiment Harness]
  ├─ 공통 split/seed/epochs 고정
  ├─ 정확도 + 지연시간 + 모델크기 수집
  └─ artifacts/benchmarks/{run_id}.json
         │
         ▼
[Edge PoC Gate]
  ├─ Export: Keras → ONNX/TFLite
  ├─ Inference parity check
  └─ Latency/Size/Operator 지원성 판정
```

핵심 규칙:
1. Phase 5 확장은 **기존 Phase 4 run_id/아티팩트 계약을 깨지 않는다**.
2. 모델 비교는 반드시 동일 데이터 split/seed에서 수행한다(공정성 고정).
3. Edge 후보는 “변환 성공”이 아니라 **정확도/지연/사이즈 기준 동시 충족**을 합격으로 본다.

---

## 2) 확장 인터페이스 계약 (입력 shape + covariate schema)

## 2.1 CLI/Config 계약

러너 확장 인자(고정):

- `--model-type`: `lstm | gru | attention_lstm`
- `--feature-mode`: `univariate | multivariate`
- `--target-cols`: 예) `target` 또는 `target_a,target_b`
- `--dynamic-covariates`: 예) `temp,promo`
- `--static-covariates`: 예) `store_id,region`
- `--covariate-spec`: JSON 파일 경로 (`configs/covariates/*.json`)
- `--export-formats`: `none | onnx | tflite | onnx,tflite` (runner에서 값 유효성 검증 + config snapshot 기록까지 지원, 실제 export 실행은 미구현)

기본값(하위호환):
- `model_type=lstm`
- `feature_mode=univariate`
- `target_cols=["target"]`
- covariates 미지정 시 기존 univariate 경로 그대로 동작

## 2.2 텐서 shape 계약 (고정)

- 입력 `X`: **`[batch, lookback, F_total]`**
- 라벨 `y`: **`[batch, horizon * F_target]`**
- 정의:
  - `F_target = len(target_cols)`
  - `F_dynamic_cov = len(dynamic_covariates)`
  - `F_total = F_target + F_dynamic_cov + F_calendar + F_static_emb(optional)`

필수 규칙:
1. `F_total >= F_target >= 1`
2. `X.shape[1] == lookback`
3. `y.shape[1] == horizon * F_target`
4. 모델 출력 dense units는 `horizon * F_target`로 고정

하위호환 규칙:
- 기존 univariate는 `F_target=1`, `F_total=1`로 간주하여 동일 계약 만족

## 2.3 covariate schema 계약 (JSON)

권장 파일: `configs/covariates/default.schema.json`

```json
{
  "version": "phase5.v1",
  "timestamp_col": "timestamp",
  "target_cols": ["target"],
  "dynamic_covariates": [
    {"name": "temp", "dtype": "float32", "scaler": "standard", "required": false},
    {"name": "promo", "dtype": "int8", "encoding": "binary", "required": false}
  ],
  "calendar_features": {
    "enabled": true,
    "features": ["hour_sin", "hour_cos", "dow_sin", "dow_cos"]
  },
  "static_covariates": [
    {"name": "store_id", "dtype": "string", "encoding": "embedding", "dim": 8, "required": false}
  ],
  "missing_policy": {
    "target": "interpolate_then_drop_if_remaining",
    "dynamic_covariates": "ffill_bfill_then_zero",
    "static_covariates": "unknown_token"
  }
}
```

스키마 검증 규칙:
- `target_cols` 비어 있으면 실패
- dynamic/static covariate 이름 중복 금지
- `required=true` covariate 누락 시 실패 코드 반환(권장: 13)
- calendar feature는 생성 파이프라인에서 deterministic 하게 생성

## 2.4 전처리 산출물 계약 확장

`processed.npz` 필수 키(Phase5):
- `X` (`[B,L,F_total]`)
- `y` (`[B,H*F_target]`)
- `feature_names` (`[F_total]`)
- `target_indices` (`[F_target]`, X의 feature 축 기준)
- `scaled` (학습용 시계열 행렬; 최소 `[T,F_total]`)
- `raw_target` (원 타깃)

호환성 메모(현재 구현):
- 러너는 우선 `X/y`를 사용하고, 없으면 Phase5 proto 키인 `X_mv/y_mv`를 fallback으로 허용한다.
- 둘 다 없으면 기존 경로(`scaled` 또는 `raw_target` 기반 sequence 생성)로 동작한다.
- `export_formats`는 `none/onnx/tflite`만 허용되며, config snapshot에는 정규화된 list 형태(`['none']`, `['onnx','tflite']`)로 기록된다.

`meta.json` 필수 필드 추가:
- `feature_mode`, `model_type_candidates`, `target_cols`, `dynamic_covariates`, `static_covariates`
- `X_shape`, `y_shape`, `f_total`, `f_target`, `horizon`, `lookback`

`preprocessor.pkl` 필수 필드 추가:
- `feature_schema` (covariate spec snapshot)
- `feature_order` (학습 시점 입력 순서)

---

## 3) 모델 확장 설계 고정 (LSTM/GRU/Attention)

## 3.1 모델 타입 계약

- `lstm`: 기존 `LSTMModel` 사용
- `gru`: `GRUModel` 신규 도입 (LSTM과 동일 인터페이스)
- `attention_lstm`: 기존 `AttentionLSTMModel` 확장

공통 인터페이스(고정):
- 생성자 인자: `sequence_length`, `hidden_units`, `dropout`, `learning_rate`, `output_units`, `input_features`
- 메서드: `build`, `fit_model`, `predict`, `evaluate`, `save`, `load`
- 모든 모델은 `X=[B,L,F_total]`, `y=[B,H*F_target]` 검증 로직 공유

## 3.2 코드 변경 포인트 (실행 중심)

1. `src/models/lstm.py`
   - `_validate_xy`에서 `features==1` 제한 제거
   - `Input(shape=(sequence_length, input_features))`로 일반화
   - `GRUModel` 클래스 추가
2. `src/models/__init__.py`
   - `GRUModel` export 추가
3. `src/training/runner.py`
   - `--model-type` 분기 추가 (`lstm|gru|attention_lstm`)
   - `--feature-mode`, `--target-cols`, `--dynamic-covariates`, `--static-covariates`, `--covariate-spec`, `--export-formats` 인자 및 config snapshot 반영
   - `processed.npz`의 `X/y`(또는 호환키 `X_mv/y_mv`) 직접 학습 경로 지원
4. `src/preprocessing/pipeline.py`
   - covariate 로딩/인코딩/feature ordering 반영
   - `processed.npz/meta.json/preprocessor.pkl` 확장 필드 저장

---

## 4) 모델 비교 실험 설계 (지표/비교표)

## 4.1 실험 매트릭스(최소)

- 모델: `lstm`, `gru`, `attention_lstm` (3)
- 데이터 모드: `univariate`, `multivariate+covariates` (2)
- 시드: `42`, `2026` (2)
- 총 최소 실험 수: `3 x 2 x 2 = 12 runs`

고정 조건:
- 동일 split 인덱스, 동일 epochs/batch_size, 동일 early stopping 정책
- 전처리 run_id와 학습 run_id 연동

## 4.2 평가 지표 (고정)

정확도:
- RMSE (주지표)
- MAE, MSE, RMSE, robust MAPE, MASE, R2

운영성:
- train wall-clock time (s)
- inference latency p50/p95 (ms, batch=1)
- model file size (MB)
- 파라미터 수

재현성:
- run_id, seed, commit_hash, config snapshot

## 4.3 비교표 템플릿 (고정)

| run_id | model_type | data_mode | seed | MAE | MSE | RMSE | robust MAPE | MASE | R2 | p50(ms) | p95(ms) | model_size(MB) | params | notes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| phase5-a | lstm | univariate | 42 | 0.000 | 0.000 | 0.000 | 0.00 | 0.00 | 0.00 | 0 | baseline |

판정 규칙(권장):
- Accuracy winner: RMSE 최소
- Edge winner: `p95` + `model_size` 가중합 최소
- 최종 추천: Accuracy/Edge 균형(도메인 우선순위 반영)

## 4.4 실행 커맨드 예시

```bash
RUN_ID=phase5-lstm-multi-$(date +%Y%m%d-%H%M%S)
python3 -m src.training.runner \
  --run-id "$RUN_ID" \
  --processed-npz "artifacts/processed/$RUN_ID/processed.npz" \
  --model-type lstm \
  --epochs 10 --batch-size 32 --seed 42
```

(실제 운영은 `scripts/benchmark_phase5.sh`로 매트릭스 반복 실행 권장)

---

## 5) Edge 후보 (ONNX/TFLite) PoC 기준

## 5.1 PoC 범위

대상 모델:
- 1순위: `gru` (경량성 기대)
- 2순위: `lstm`
- 3순위: `attention_lstm` (연산자 호환성 리스크 확인용)

입력 시나리오:
- batch=1, lookback=24, `F_total in {1, 8}`

## 5.2 성공 기준 (Gate)

1. Export 성공
- ONNX: `.onnx` 파일 생성 + onnxruntime 로드 성공
- TFLite: `.tflite` 파일 생성 + interpreter invoke 성공

2. 정확도 동등성(parity)
- 동일 입력에서 Keras 대비 max absolute diff <= `1e-3`
- RMSE 열화 <= `+2%`

3. 성능/크기
- 단일 추론 p95 <= `30ms` (개발 노트북 기준 상대지표)
- 모델 크기 <= `10MB`

4. 안정성
- 100회 반복 추론 중 실패 0건

합격 판정:
- 위 1~4 전부 충족 시 해당 포맷 “PoC PASS”

## 5.3 리스크 및 우선 대응

- Attention 연산자의 변환 호환성(ONNX/TFLite) 불안정 가능
  - 대응: 기본 후보를 GRU/LSTM으로 두고 attention은 실험군 분리
- dynamic shape 지원 이슈
  - 대응: PoC는 고정 입력 shape(1,24,F_total)부터 시작

---

## 6) Acceptance Criteria (Phase 5 설계 고정)

- AC-1: `docs/PHASE5_ARCH.md`에 모델 타입/입력 shape/covariate schema 계약 명시
- AC-2: multivariate/covariates 확장 시 필수 산출물 키(`feature_names`, `target_indices`) 고정
- AC-3: 모델 비교 실험 매트릭스(최소 12 run)와 비교표 포맷 고정
- AC-4: ONNX/TFLite PoC 합격 기준(정확도/지연/사이즈/안정성) 수치화
- AC-5: 하위호환(univariate 기존 경로) 유지 전략 명시

---

## 7) 구현 우선순위 (즉시 실행용)

1. **인터페이스 먼저 고정**
   - `covariate schema json` + parser/validator 구현
2. **모델 입력 일반화**
   - `features==1` 제약 제거 + `GRUModel` 추가
3. **runner 분기 + 메타 확장**
   - `--model-type`, `--feature-mode` 반영
4. **벤치마크 스크립트 작성**
   - 12-run 자동 실행 + 비교표 자동 집계
5. **edge export PoC**
   - GRU→LSTM→Attention 순으로 ONNX/TFLite 검증

---

## 8) Standard Handoff Format

### 8.1 Summary
- Phase 5는 모델/데이터/배포 확장을 위한 계약을 고정했다.
- 핵심은 **(1) 모델 타입 표준화, (2) multivariate+covariates 입력 계약, (3) 비교 실험 규칙, (4) Edge PoC 합격 기준 수치화**다.

### 8.2 Decisions Locked
- 모델 타입: `lstm | gru | attention_lstm`
- 입력/출력 shape: `X=[B,L,F_total]`, `y=[B,H*F_target]`
- covariate schema(JSON) 필수 필드 및 검증 규칙
- 실험 매트릭스 최소 12-run + 공통 비교표 포맷
- Edge PoC 합격 기준(Export/Parity/Latency/Size/Stability)

### 8.3 Deliverables
- [x] `docs/PHASE5_ARCH.md`
- [x] 확장 인터페이스 계약(입력 shape 확장, covariate schema)
- [x] 모델 비교 실험 설계(지표/비교표)
- [x] Edge 후보(ONNX/TFLite) PoC 기준

### 8.4 Immediate Next Actions
1. `configs/covariates/default.schema.json` 생성 및 validator 추가
2. `src/models/lstm.py` 입력 일반화 + `GRUModel` 구현
3. `src/training/runner.py`에 `--model-type`/covariate 인자 추가
4. `scripts/benchmark_phase5.sh` + `artifacts/benchmarks/*.json` 집계기 추가
5. `scripts/export_edge_poc.py` 작성(ONNX/TFLite 변환+parity 측정)

### 8.5 Risks / Open Points
- attention 모델 export 호환성 리스크(특히 TFLite)
- multivariate 입력 시 기존 baseline 계산 로직(X 마지막 값 기준) 재정의 필요
- latency 기준은 장비 의존적이므로 절대치 + baseline 대비 상대지표 병행 권장
