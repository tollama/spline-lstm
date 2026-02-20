# PHASE3_ARCH — Spline-LSTM MVP Phase 3 설계 고정

> 기준 문서: `docs/BLUEPRINT.md`, `docs/PHASE2_ARCH.md`  
> 범위: **Baseline 비교 + 재현성(Determinism) 계약 고정 + Run Metadata 스키마 확정**

---

## 0) 설계 목표 (Phase 3)

### 목표
- 모델 성능을 **반드시 baseline(naive, moving average)** 과 비교하도록 계약을 고정한다.
- 실험 재현성을 위해 **seed / deterministic / split-index / config + commit hash** 저장을 의무화한다.
- 모든 실행 산출물에 공통으로 쓰이는 **run metadata 저장 필드(현행)** 를 정의한다.

### 비목표
- 새로운 모델 아키텍처(Transformer, N-BEATS 등) 도입
- 하이퍼파라미터 자동 탐색(optuna 등)
- 분산 학습/멀티 GPU 최적화

---

## 1) Phase 3 아키텍처 (고정)

```text
[processed.npz + meta.json + preprocessor.pkl]
    └─ runner/train (Phase2 + Phase3)
       ├─ model train/eval
       ├─ baseline eval (naive, MA)
       ├─ reproducibility snapshot 저장
       └─ run metadata 저장

Artifacts(run_id scope):
- artifacts/checkpoints/{run_id}/best.keras
- artifacts/checkpoints/{run_id}/last.keras
- artifacts/metrics/{run_id}.json
- artifacts/reports/{run_id}.md
- artifacts/metadata/{run_id}.json   # Phase3 신규(핵심)
```

핵심 규칙:
1. **비교 없는 단독 모델 점수 보고 금지** (항상 baseline 동시 보고)
2. 재실행 재현을 위해 실행 컨텍스트를 정형화하여 저장
3. 모든 파일은 `run_id` 기준으로 추적 가능해야 함

---

## 2) Baseline 비교 계약 (naive / MA)

## 2.1 Baseline 정의 (고정)

### A) Naive baseline (Persistence)
- 정의: `y_hat(t+1..t+h) = 마지막 관측값(last_observed)`
- horizon > 1일 때 동일 값을 반복 예측

### B) Moving Average baseline (MA-k)
- 정의: `y_hat = 최근 k개 관측치 평균`
- 기본값: `k = lookback` (명시적 override 가능)
- horizon > 1일 때 동일 평균값 반복 예측

---

## 2.2 평가 동일성 계약

Baseline과 모델은 아래를 **반드시 동일하게** 사용해야 한다.
- 동일 split (test set)
- 동일 target 스케일 (권장: 역정규화 후 원 스케일에서 평가)
- 동일 metric 함수 (`mae`, `rmse`, `mape`, `r2`)

위반 시 결과 무효 처리(리포트에 `INVALID_COMPARISON` 표기).

---

## 2.3 비교 결과 저장 계약 (현재 구현)

`artifacts/metrics/{run_id}.json`에는 모델 지표와 baseline 비교가 아래 형태로 저장된다.

```json
{
  "metrics": {"mae": 0.0, "mse": 0.0, "rmse": 0.0, "mape": 0.0, "mase": 0.0, "r2": 0.0},
  "baselines": {
    "lstm": {"mae": 0.0, "rmse": 0.0, "mape": 0.0, "r2": 0.0},
    "naive_last": {"mae": 0.0, "rmse": 0.0, "mape": 0.0, "r2": 0.0},
    "moving_average_3": {"mae": 0.0, "rmse": 0.0, "mape": 0.0, "r2": 0.0},
    "relative_improvement_rmse_pct": {
      "vs_naive_last": 0.0,
      "vs_moving_average_3": 0.0
    }
  }
}
```

개선율 계산(예시):
- `rmse_improvement_pct = (baseline_rmse - model_rmse) / baseline_rmse * 100`

---

## 3) 재현성 계약 (Reproducibility Contract)

## 3.1 저장 의무 항목 (필수)

모든 run은 아래 정보를 `artifacts/metadata/{run_id}.json`에 저장한다.

1. `seed` 관련
   - python/numpy/tensorflow seed 및 deterministic 요청 결과
2. `config_snapshot`
   - 실행 당시 runner 인자 스냅샷
3. `git commit hash`
   - 가능 시 `git rev-parse HEAD`, 불가하면 `null`
4. `cwd`, `created_at`, `run_id`
   - 실행 컨텍스트 추적 필드

참고: split index는 metadata 파일이 아니라 `artifacts/splits/{run_id}.json`에 저장된다.

---

## 3.2 Deterministic 실행 규칙

최소 규칙:
- Python/Numpy/TF seed를 실행 시작 시 고정
- 학습시 `shuffle=False` 고정
- 가능하면 deterministic op 활성화 (`TF_DETERMINISTIC_OPS=1`)
- 데이터 split은 난수 기반이 아닌 **인덱스 기반 시계열 분할** 사용

허용 편차 정책(운영):
- 완전 bitwise 재현이 불가한 환경에서는 metric 허용 오차를 계약한다.
- 권장: `RMSE 상대 오차 <= 5%`를 smoke gate로 사용

---

## 3.3 split-index 저장 계약

최소 저장 필드:

```json
{
  "split_index": {
    "raw": {
      "n_total": 1000,
      "train_end": 640,
      "val_end": 800,
      "test_start": 800
    },
    "sequence": {
      "n_train_seq": 616,
      "n_val_seq": 136,
      "n_test_seq": 176,
      "lookback": 24,
      "horizon": 1
    }
  }
}
```

이 인덱스가 없으면 재현 검증을 실패로 처리한다.

---

## 4) Run Metadata 스키마 정의 (v1)

파일: `artifacts/metadata/{run_id}.json`

## 4.1 스키마(현재 구현 필드)

```json
{
  "run_id": "string",
  "created_at": "ISO8601",
  "cwd": "absolute/path",
  "commit_hash": "string|null",
  "commit_hash_source": "git|unavailable",
  "git_commit": "string|null",
  "seed": {
    "seed": 42,
    "pythonhashseed": "42",
    "python_random": true,
    "numpy_random": true,
    "tensorflow_random": true,
    "tensorflow_op_determinism": true,
    "deterministic_requested": true
  },
  "config_snapshot": {
    "sequence_length": 24,
    "horizon": 1,
    "...": "runner config snapshot"
  }
}
```

---

## 4.2 검증 규칙 (현재 구현 기준)

`src.training.runner::_validate_phase3_metadata_contract`는 저장 전 아래 키/타입을 **명시 검증**한다.

- 루트
  - `schema_version == "phase3.runmeta.v1"`
  - `run_id == CLI --run-id`
  - `created_at: non-empty string`
  - `project == "spline-lstm"`
  - `config: object`
  - `artifacts: object`
- `git` 블록
  - `git: object`
  - `git.commit`: key 필수 (`null` 허용; 값이 있으면 non-empty string)
  - `git.source: non-empty string`
- `runtime` 블록
  - `runtime.python/platform/backend: non-empty string`
- `reproducibility.seed`
  - `python/numpy/tensorflow: integer`
- `reproducibility.deterministic`
  - `enabled/tf_deterministic_ops/shuffle: boolean`
- `reproducibility.split_index.raw`
  - `n_total/train_end/val_end/test_start: integer`
- `reproducibility.split_index.sequence`
  - `n_train_seq/n_val_seq/n_test_seq/lookback/horizon: integer`

검증 실패 시 typed exception `Phase3MetadataContractError`를 발생시키고,
CLI는 이를 exit code `34 (PHASE3_METADATA_CONTRACT_INVALID)`로 고정 매핑한다.

참고: legacy run metadata(`artifacts/metadata/{run_id}.json`)의 `commit_hash`는 git 비저장 환경에서 `null` 허용(`commit_hash_source=unavailable`).

---

## 5) CLI/구현 반영 계약 (실행 중심)

## 5.1 Runner 입력 옵션 확장 (권장)

`python3 -m src.training.runner`에 아래 옵션을 추가한다.
- `--ma-window` (기본: lookback)
- `--deterministic` / `--no-deterministic`
- `--save-run-meta` (기본 true)

## 5.2 Runner 처리 순서 (고정)

1. seed + deterministic 설정
2. 데이터 로드/분할 및 split-index 계산
3. 모델 학습/평가
4. baseline(naive/MA) 계산/평가
5. metrics/report 저장
6. `metadata/{run_id}.json` 저장 (git hash/config/split-index 포함)

## 5.3 실패 처리

Runner는 Phase 3 비교/메타데이터 계약에 대해 전용 exit code를 사용한다.

- `32`: `PHASE3_BASELINE_COMPARISON_INVALID`
  - baseline 비교 계약 키 누락/형식 불일치/비수치/비유한값 등
- `33`: `PHASE3_BASELINE_COMPARISON_SKIPPED`
  - baseline 비교가 필수인 경로에서 비교가 생략된 경우(명시 위반)
  - runner typed exception: `Phase3BaselineComparisonSkippedError` (message 패턴 의존 제거)
- `34`: `PHASE3_METADATA_CONTRACT_INVALID`
  - Phase 3 metadata 계약 위반(명시 위반)
  - runner typed exception: `Phase3MetadataContractError` (message 패턴 의존 제거)

그 외 기존 코드 매핑(21/22/23/24/26/27)은 유지한다.

---

## 6) Acceptance Criteria (Phase 3)

- AC-1: 모든 run에서 `model + naive + MA` 지표가 한 파일에 함께 저장됨
- AC-2: `artifacts/metadata/{run_id}.json` 생성 및 스키마 검증 통과
- AC-3: seed/deterministic/split-index/config/git commit hash가 모두 기록됨
- AC-4: 동일 config+seed 재실행 시 편차가 허용 범위(RMSE ±5%) 내
- AC-5: 비교 동일성(동일 test split, 동일 metric) 위반 시 실행 실패

---

## 7) 즉시 실행 TODO (P0 → P1)

### P0 (즉시)
- [x] `src/training/baselines.py` 구현: naive/MA predictor + metric 계산 + Phase3 비교 유효성 검증
- [x] `runner.py` baseline 평가 및 metrics JSON 확장
- [x] `runner.py` metadata writer 구현 (`artifacts/metadata/{run_id}.json`)
- [x] git hash 수집 유틸 반영 (`src/utils/repro.py`)

### P1
- [x] `tests/test_baseline_contract.py` (naive/MA 계약 + invalid hard-fail)
- [x] `tests/test_run_metadata_schema.py` (필수 필드/불일치 실패)
- [ ] `tests/test_reproducibility_smoke.py` (2회 실행 편차 게이트)

---

## 8) Standard Handoff Format

### 8.1 Summary
- Phase 3에서 baseline 비교(naive/MA)를 **필수 계약**으로 고정했다.
- 재현성 핵심 요소(seed/deterministic/split-index/config+commit hash)를 **run metadata**로 고정 저장한다.
- 신규 산출물 `artifacts/metadata/{run_id}.json` 스키마(v1)를 정의했다.

### 8.2 Decisions Locked
- baseline 없는 단독 모델 지표 보고 금지
- baseline은 naive + MA(k=lookback 기본)
- split-index 및 git commit hash 누락 시 재현성 실패 처리
- metadata 파일 경로: `artifacts/metadata/{run_id}.json`

### 8.3 Deliverables
- [x] `docs/PHASE3_ARCH.md` 작성
- [x] baseline(naive/MA) 비교 계약 정의
- [x] reproducibility(Seed/Deterministic/Split-Index/Config+Commit Hash) 계약 정의
- [x] run metadata 저장 필드(현행) 정의

### 8.4 Immediate Next Actions
1. `src/training/baselines.py` 추가 후 runner 연동
2. `runner.py`에서 `metadata/{run_id}.json` 저장 로직 구현
3. 계약 기반 테스트 3종 추가 및 CI smoke gate 반영

### 8.5 Risks / Open Points
- TensorFlow/OS 조합에 따라 완전 deterministic 보장이 어려울 수 있음
- `git` 없는 환경(zip 배포 등)에서 commit hash 수집 실패 처리 정책 필요
- MAPE는 y_true=0 구간 처리 규칙 고정 필요(현재 mask 방식 유지 권장)
