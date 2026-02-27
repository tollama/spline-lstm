# PHASE2_ARCH — Spline-LSTM MVP Phase 2 설계 고정

> 기준 문서: `docs/BLUEPRINT.md`, `docs/PHASE1_ARCH.md`  
> 범위: **단일변수 LSTM 학습/평가/추론 E2E 계약 고정** (MVP 실행 가능 상태)

---

## 0) 설계 목표 (Phase 2)

### 목표
- Phase 1 전처리 산출물(`X/y split + preprocessor`)을 입력으로 받아,
  **학습(train) → 평가(eval) → 추론(infer)** 를 동일 계약으로 고정한다.
- 산출물(체크포인트, metrics, report)을 `run_id` 스코프로 일관 저장한다.
- CLI 러너 계약을 고정하여 CI/자동화에서 재현 가능하게 한다.

### 비목표
- 멀티변수(multivariate), covariates
- 모델 확장(GRU, Attention) 성능 최적화
- 서빙 인프라(REST, gRPC) 구축

---

## 1) E2E 아키텍처 (고정)

```text
[raw csv/parquet]
   └─ preprocess (Phase1)
      ├─ artifacts/processed/{run_id}/processed.npz
      ├─ artifacts/processed/{run_id}/meta.json
      └─ artifacts/models/{run_id}/preprocessor.pkl

[processed artifacts + config]
   └─ train (Phase2)
      ├─ artifacts/checkpoints/{run_id}/best.keras
      ├─ artifacts/checkpoints/{run_id}/last.keras
      ├─ artifacts/metrics/{run_id}.json
      └─ artifacts/reports/{run_id}.md

[trained runner output]
   └─ infer snapshot (Phase2 current)
      ├─ artifacts/metrics/{run_id}.json -> `inference` field (`y_true_last`, `y_pred_last`)
      └─ artifacts/reports/{run_id}.md -> latest test-window inference summary
```

핵심 규칙:
1. 모든 단계는 동일 `run_id`를 공유한다.
2. 시간순 split + train fit normalization only(데이터 누수 금지).
3. 모델/전처리 불일치(run_id, lookback, horizon) 시 즉시 실패.

---

## 2) 모델/학습/평가/추론 인터페이스 계약

## 2.1 공통 타입 계약

### 입력 텐서
- `X_*`: `np.ndarray`, shape `[N, lookback, 1]`, dtype `float32`
- `y_*`: `np.ndarray`, shape `[N, horizon]`, dtype `float32`

### 공통 메타 (`meta.json` 최소 필드)
- `run_id: str`
- `lookback: int`
- `horizon: int`
- `scaler_type: str` (`standard|minmax`)
- `schema_version: str` (예: `phase1.v2`)

---

## 2.2 모델 인터페이스 계약 (`src/models/lstm.py`)

```python
class LSTMModel:
    def __init__(
        sequence_length: int,
        hidden_units: list[int],
        dropout: float,
        learning_rate: float,
        output_units: int,
    ) -> None: ...

    def build(self) -> None: ...

    def fit_model(
        self,
        X: np.ndarray,
        y: np.ndarray,
        epochs: int,
        batch_size: int,
        validation_data: tuple[np.ndarray, np.ndarray] | None,
        early_stopping: bool,
        shuffle: bool,
        verbose: int,
    ) -> dict: ...

    def predict(self, X: np.ndarray) -> np.ndarray: ...
    def evaluate(self, X: np.ndarray, y: np.ndarray) -> dict: ...
    def save(self, path: str) -> None: ...
    def load(self, path: str) -> None: ...
```

### 강제 검증
- `X.ndim == 3`, `X.shape[1] == sequence_length`, `X.shape[2] == 1`
- `y.ndim == 2`, `y.shape[1] == output_units`
- 위반 시 `ValueError`로 fail-fast

---

## 2.3 학습 인터페이스 계약 (`src/training/trainer.py`)

```python
class Trainer:
    def train(
        self,
        data: np.ndarray,
        epochs: int,
        batch_size: int,
        test_size: float,
        val_size: float,
        normalize: bool,
        normalize_method: str,
        early_stopping: bool,
        verbose: int,
    ) -> dict: ...

    def compute_metrics(self, y_true: np.ndarray, y_pred: np.ndarray) -> dict: ...

    def save_run_artifacts(
        self,
        run_id: str,
        base_dir: str = "artifacts",
        config: dict | None = None,
        report: str | None = None,
        preprocessor_blob: bytes | None = None,
    ) -> dict[str, str]: ...
```

### `train()` 반환 계약 (최소)
```json
{
  "start_time": "ISO8601",
  "end_time": "ISO8601",
  "config": {
    "sequence_length": 24,
    "prediction_horizon": 1,
    "epochs": 50,
    "batch_size": 32,
    "test_size": 0.2,
    "val_size": 0.2,
    "normalize_method": "minmax"
  },
  "history": {"loss": [], "val_loss": [], "mae": [], "val_mae": []},
  "metrics": {
    "mae": 0.0,
    "mse": 0.0,
    "rmse": 0.0,
    "mape": 0.0,
    "r2": 0.0
  },
  "normalization": {"method": "minmax", "min": 0.0, "max": 1.0}
}
```

---

## 2.4 평가 인터페이스 계약

평가는 `train()` 종료 후 test split 기준으로 수행하며, 최소 지표:
- `mae`, `rmse`, `mape`, `r2`

### 평가 리포트(`artifacts/reports/{run_id}.md`) 최소 섹션
1. Run 정보(run_id, git sha, config)
2. 데이터 요약(train/val/test 샘플 수)
3. 최종 지표 표
4. 베이스라인 대비 비교(naive optional, 미구현 시 TODO 명시)
5. 실패/경고(예: early stopping 미발동)

---

## 2.5 추론 인터페이스 계약

### 추론 입력 (현재 runner 구현)
- `model_path`: `artifacts/checkpoints/{run_id}/best.keras` 또는 `last.keras`
- `preprocessor_path`: `artifacts/models/{run_id}/preprocessor.pkl`
- `processed_npz` 또는 raw/synthetic series 입력

### 추론 출력 (현재 구현)
- 별도 `predictions.csv` 파일은 생성하지 않음
- `artifacts/metrics/{run_id}.json`의 `inference` 필드에 최신 test window 결과 저장:
  - `x_shape`
  - `y_true_last`
  - `y_pred_last`

### 추론 전 필수 검증
- CLI `--run-id` vs `processed.npz` 경로 run_id
- `processed` 형제 `meta.json`의 `run_id`
- `preprocessor.pkl` payload의 `run_id`

---

## 3) 체크포인트/metrics/report 산출물 계약

## 3.1 체크포인트 정책 (best/last)

### 파일 경로
- `artifacts/checkpoints/{run_id}/best.keras`
- `artifacts/checkpoints/{run_id}/last.keras`

### 저장 규칙
- `best.keras`: `val_loss` 최소 갱신 시 덮어쓰기
- `last.keras`: 학습 종료 시 마지막 epoch 상태 저장
- 둘 다 저장 실패 시 run 실패 처리(종료 코드 31)

### 메타 동봉(권장)
- `artifacts/models/{run_id}/checkpoint_meta.json`
```json
{
  "run_id": "20260218_173100_ab12cd3",
  "best_epoch": 17,
  "last_epoch": 25,
  "monitor": "val_loss",
  "best_val_loss": 0.0123
}
```

---

## 3.2 Metrics 계약

### 파일
- `artifacts/metrics/{run_id}.json`

### 스키마(최소)
```json
{
  "run_id": "string",
  "dataset": {
    "n_train": 0,
    "n_val": 0,
    "n_test": 0,
    "lookback": 24,
    "horizon": 1
  },
  "metrics": {
    "mae": 0.0,
    "mse": 0.0,
    "rmse": 0.0,
    "mape": 0.0,
    "r2": 0.0
  },
  "training": {
    "epochs_requested": 50,
    "epochs_ran": 25,
    "early_stopped": true,
    "best_epoch": 17
  },
  "timestamps": {
    "start_time": "ISO8601",
    "end_time": "ISO8601"
  }
}
```

---

## 3.3 Report 계약

### 파일
- `artifacts/reports/{run_id}.md` (학습/평가 + 최신 추론 요약)

### 필수 포함
- 실행 명령(재현 가능)
- 핵심 하이퍼파라미터
- 최종 지표
- 산출물 경로 목록
- 오류 발생 시 원인/스택 요약

---

## 4) Runner CLI 계약 (현행 고정)

> 현재 구현(`src/training/runner.py`)은 **단일 실행 커맨드**로 train/eval/infer 핵심 산출물을 한 번에 생성한다.
> (`train/eval/infer` 서브커맨드 설계는 향후 확장안으로 유지)

## 4.1 단일 러너 실행

```bash
python3 -m src.training.runner \
  --run-id 20260218_173100_ab12cd3 \
  --processed-npz artifacts/processed/20260218_173100_ab12cd3/processed.npz \
  --epochs 50 \
  --batch-size 32 \
  --learning-rate 0.001 \
  --hidden-units 128 64 \
  --dropout 0.2 \
  --artifacts-dir artifacts
```

### 성공 조건
- exit code `0`
- `checkpoints/{run_id}/best.keras`, `checkpoints/{run_id}/last.keras`, `metrics/{run_id}.json`, `reports/{run_id}.md` 생성

---

## 4.2 Synthetic smoke/legacy 호환 옵션

테스트/기존 스크립트 호환을 위해 아래 옵션을 지원한다.

```bash
python3 -m src.training.runner \
  --run-id phase2-runner-smoke \
  --epochs 1 \
  --synthetic \
  --artifacts-dir artifacts \
  --checkpoints-dir checkpoints
```

- `--synthetic`: legacy no-op 호환 플래그 (입력 파일이 없으면 기본 synthetic 사용)
- `--checkpoints-dir`: 체크포인트 기본 경로(`<artifacts-dir>/checkpoints`)를 명시 경로로 오버라이드

---

## 4.3 CLI 실패 동작 (현재 구현 기준)

`src.training.runner`는 명시적 종료코드 매핑을 구현하지 않는다.
실패 시 Python 예외로 종료되며 일반적으로 비0 종료코드(대개 1)를 반환한다.

운영상 식별 가능한 대표 실패 유형:
- run_id 불일치 (`--run-id` vs `processed/meta/preprocessor`)
- `processed.npz` 텐서 shape/키 계약 위반
- TensorFlow backend 미사용/미설치
- 학습/저장 중 런타임 예외

---

## 5) 실행 시나리오 (운영 표준)

1. **전처리 완료 확인**
   - `processed.npz`, `meta.json`, `preprocessor.pkl` 존재
2. **러너 실행**
   - `python3 -m src.training.runner ...`
   - 종료 후 `best/last + metrics/report` 검증
3. **필요 시 오프라인 재평가/추론**
   - 현재 MVP는 단일 러너 결과를 기준으로 검증
4. **회귀 방지 테스트**
   - 최소 smoke test: runner CLI 1회 성공

---

## 6) Acceptance Criteria (Phase 2)

- AC-1: train CLI 1회 실행으로 `best.keras`, `last.keras`, `metrics.json`, `report.md` 생성
- AC-2: `best.keras`는 `val_loss` 기준 최적 epoch를 반영
- AC-3: model/preprocessor run_id mismatch 시 runner가 즉시 실패(비0 종료)
- AC-4: 입력 shape 위반 시 runner가 즉시 실패(비0 종료)
- AC-5: runner payload/report에 최신 추론 스냅샷(`inference`)이 저장됨
- AC-6: 동일 config+seed 재실행 시 metrics 편차가 허용 범위 내(예: RMSE ±5%)
- AC-7: report에 실행 명령/지표/산출물 경로가 모두 기록됨

---

## 7) 구현 우선순위 (실행 중심)

### P0 (즉시)
- [x] `src/training/runner.py` 단일 실행 CLI 구현 및 legacy 옵션(`--synthetic`, `--checkpoints-dir`) 호환
- [x] `best.keras`/`last.keras` 동시 저장 경로 고정
- [x] `metrics/report` 스키마 고정 저장 유틸 추가
- [x] run_id/shape/metadata 검증 로직 반영 (예외 기반 비0 실패)

### P1
- [x] `tests/test_training_runner_cli_contract.py` (CLI 계약 테스트)
- [x] `tests/test_inference_contract.py` (runner inference payload/shape)
- [x] 실패 시나리오(예외/비0 종료) 테스트

### P2
- [ ] naive baseline 자동 비교 리포트
- [ ] infer 입력 포맷(csv/parquet/json) 확장

---

## 8) Standard Handoff Format

### 8.1 Summary
- Phase 2는 단일변수 LSTM E2E(학습/평가/추론) 계약을 고정했다.
- 핵심 산출물 계약: `best/last checkpoint`, `metrics json`, `report md`.
- runner CLI는 현행 단일 실행 커맨드로 고정하고, legacy 옵션 호환(`--synthetic`, `--checkpoints-dir`)을 유지한다.

### 8.2 Decisions Locked
- 입력/출력 shape: `X [N,lookback,1]`, `y [N,horizon]`.
- 체크포인트: `best.keras` + `last.keras` 동시 관리.
- artifact는 `run_id` 스코프 강제, 불일치 시 fail-fast.
- CLI 실패는 예외 기반 비0 종료로 처리.

### 8.3 Deliverables
- [x] `docs/PHASE2_ARCH.md` 작성 완료
- [x] 모델/학습/평가/추론 인터페이스 계약 정의
- [x] 체크포인트/metrics/report 산출물 계약 정의
- [x] runner CLI 계약 정의

### 8.4 Immediate Next Actions
1. 필요 시 `src/training/runner.py`를 서브커맨드 구조로 확장(현행 단일 실행 계약과 후방호환 유지)
2. `Trainer.save_run_artifacts()`를 `best/last` 정책과 정렬
3. 계약 기반 테스트 3종 추가 후 CI smoke 연결

### 8.5 Risks / Open Points
- 상세 실패코드 정규화(필요 시 wrapper에서 별도 구현)
- `metrics` 스키마 필드 일부는 trainer 반환값 확장 필요
- TensorFlow 비설치 환경에서 CLI 스모크 테스트용 더미 백엔드 전략 필요
