# MANUAL_TEST_GUIDE

Spline-LSTM 프로젝트를 로컬에서 사람이 직접 검증하기 위한 수동 테스트 가이드입니다.

- 대상 경로: `~/spline-lstm`
- 원칙: **실행 중심**, **python3 기준**, **run_id 단위 추적**
- 권장: 각 테스트는 새로운 `RUN_ID`로 수행

---

## 1) 사전 준비 (환경/의존성, python3 기준)

### 1.1 기본 환경 확인

```bash
cd ~/spline-lstm
python3 --version
python3 -m pip --version
```

### 1.2 가상환경(권장)

```bash
cd ~/spline-lstm
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

### 1.3 디렉터리/권한 확인

```bash
cd ~/spline-lstm
mkdir -p artifacts logs
python3 - <<'PY'
from pathlib import Path
for p in ["artifacts", "logs", "scripts/run_e2e.sh", "scripts/smoke_test.sh", "scripts/run_compare.sh"]:
    print(f"{p}:", "OK" if Path(p).exists() else "MISSING")
PY
```

### 1.4 사전 점검(선택)

```bash
cd ~/spline-lstm
python3 -m pytest -q tests/test_data_contract.py tests/test_preprocessing_pipeline.py
```

---

## 2) 빠른 스모크 테스트 (quick-gate)

> 목적: 2~5분 내 핵심 계약(contracts)과 기본 E2E 경로가 깨지지 않았는지 확인

### 2.1 core contract tests

```bash
cd ~/spline-lstm
python3 -m pytest -q \
  tests/test_phase4_run_id_guard.py \
  tests/test_artifacts.py \
  tests/test_training_runner_cli_contract.py \
  tests/test_training_leakage.py
```

### 2.2 smoke gate 실행

```bash
cd ~/spline-lstm
RUN_ID=local-quick-$(date +%Y%m%d-%H%M%S) EPOCHS=1 bash scripts/smoke_test.sh
```

### 2.3 quick-gate 즉시 판정

```bash
cd ~/spline-lstm
python3 - <<'PY'
import json
from pathlib import Path
m = sorted(Path("artifacts/metrics").glob("local-quick-*.json"), key=lambda p: p.stat().st_mtime)
assert m, "local-quick metrics not found"
run_id = m[-1].stem
required = [
    f"artifacts/metrics/{run_id}.json",
    f"artifacts/reports/{run_id}.md",
    f"artifacts/checkpoints/{run_id}/best.keras",
    f"artifacts/models/{run_id}/preprocessor.pkl",
]
for p in required:
    assert Path(p).exists(), f"missing: {p}"
payload = json.loads(Path(required[0]).read_text(encoding="utf-8"))
for k in ("mae", "rmse", "mape", "r2"):
    assert k in payload["metrics"], f"missing metric: {k}"
print("[PASS] quick-gate:", run_id)
PY
```

---

## 3) E2E 수동 테스트 (`run_e2e.sh`, `smoke_test.sh`)

## 3.1 One-click E2E (`run_e2e.sh`)

```bash
cd ~/spline-lstm
RUN_ID=local-e2e-$(date +%Y%m%d-%H%M%S) EPOCHS=1 bash scripts/run_e2e.sh
```

성공 시 기대:
- `artifacts/processed/<run_id>/processed.npz`
- `artifacts/processed/<run_id>/meta.json`
- `artifacts/models/<run_id>/preprocessor.pkl`
- `artifacts/checkpoints/<run_id>/best.keras`
- `artifacts/checkpoints/<run_id>/last.keras`
- `artifacts/metrics/<run_id>.json`
- `artifacts/reports/<run_id>.md`
- `artifacts/metadata/<run_id>.json`

## 3.2 E2E + 자동 검증(`smoke_test.sh`)

```bash
cd ~/spline-lstm
RUN_ID=local-e2e-smoke-$(date +%Y%m%d-%H%M%S) EPOCHS=1 bash scripts/smoke_test.sh
```

### 3.3 E2E 후 수동 health check

```bash
cd ~/spline-lstm
python3 - <<'PY'
import json, pickle
from pathlib import Path

metrics = sorted(Path("artifacts/metrics").glob("local-e2e*.json"), key=lambda p: p.stat().st_mtime)
assert metrics, "e2e metrics not found"
run_id = metrics[-1].stem

required = [
    f"artifacts/processed/{run_id}/processed.npz",
    f"artifacts/processed/{run_id}/meta.json",
    f"artifacts/models/{run_id}/preprocessor.pkl",
    f"artifacts/checkpoints/{run_id}/best.keras",
    f"artifacts/checkpoints/{run_id}/last.keras",
    f"artifacts/metrics/{run_id}.json",
    f"artifacts/reports/{run_id}.md",
    f"artifacts/metadata/{run_id}.json",
]
for p in required:
    assert Path(p).exists(), f"missing artifact: {p}"

meta = json.loads(Path(f"artifacts/processed/{run_id}/meta.json").read_text(encoding="utf-8"))
m = json.loads(Path(f"artifacts/metrics/{run_id}.json").read_text(encoding="utf-8"))
with open(f"artifacts/models/{run_id}/preprocessor.pkl", "rb") as f:
    prep = pickle.load(f)

assert meta.get("run_id") == run_id, "meta run_id mismatch"
assert m.get("run_id") == run_id, "metrics run_id mismatch"
assert prep.get("run_id") == run_id, "preprocessor run_id mismatch"
print("[PASS] E2E health check:", run_id)
PY
```

---

## 4) Phase별 핵심 수동 검증 포인트 (Phase1~5)

## Phase 1 (전처리/데이터 계약)
- `timestamp`, `target` 컬럼 계약 준수
- 정렬/중복/결측 처리 규칙 확인
- 전처리 산출물 저장 확인(`processed.npz`, `meta.json`, `preprocessor.pkl`)

실행:
```bash
cd ~/spline-lstm
python3 -m pytest -q tests/test_data_contract.py tests/test_preprocessing_pipeline.py tests/test_preprocessing_scaler_split.py
```

## Phase 2 (학습/평가/러너 계약)
- runner CLI 경로 정상 동작
- metrics/report/checkpoint 생성
- 학습 leakage 방지 계약

실행:
```bash
cd ~/spline-lstm
python3 -m pytest -q tests/test_phase2_pipeline.py tests/test_training_runner_cli_contract.py tests/test_training_leakage.py
```

## Phase 3 (재현성/베이스라인)
- baseline(naive/MA) 비교 필드 유지
- 재현성 메타데이터 기록/검증

실행:
```bash
cd ~/spline-lstm
python3 -m pytest -q tests/test_phase3_repro_baseline.py
```

## Phase 4 (운영 안정화/run_id guard)
- one-click E2E 성공
- smoke gate 성공
- run_id mismatch fail-fast 동작

실행:
```bash
cd ~/spline-lstm
python3 -m pytest -q tests/test_phase4_run_id_guard.py tests/test_artifacts.py
RUN_ID=phase4-manual-smoke-$(date +%Y%m%d-%H%M%S) EPOCHS=1 bash scripts/smoke_test.sh
```

## Phase 5 (확장 경로)
- compare runner(LSTM vs GRU) 결과 산출
- multivariate/covariates 전처리 경로 계약 확인

실행:
```bash
cd ~/spline-lstm
python3 -m pytest -q tests/test_phase5_extension.py tests/test_phase5_multivariate_proto.py tests/test_phase5_runner_contract_alignment.py
```

---

## 5) 확장 경로 수동 테스트 (`compare_runner`, `multivariate/covariates`)

## 5.1 compare_runner (LSTM vs GRU)

```bash
cd ~/spline-lstm
RUN_ID=local-compare-$(date +%Y%m%d-%H%M%S) EPOCHS=3 bash scripts/run_compare.sh
```

검증:
```bash
cd ~/spline-lstm
python3 - <<'PY'
import json
from pathlib import Path
p = sorted(Path("artifacts/comparisons").glob("local-compare-*.json"), key=lambda x: x.stat().st_mtime)
assert p, "comparison json not found"
payload = json.loads(p[-1].read_text(encoding="utf-8"))
assert "runs" in payload and len(payload["runs"]) >= 2, "expected >=2 model runs"
print("[PASS] compare_runner:", p[-1].stem)
PY
```

## 5.2 multivariate/covariates 전처리 경로

```bash
cd ~/spline-lstm
python3 - <<'PY'
import numpy as np
import pandas as pd
from pathlib import Path
from src.preprocessing.pipeline import PreprocessingConfig, run_preprocessing_pipeline

run_id = "local-mv-" + pd.Timestamp.now().strftime("%Y%m%d-%H%M%S")
path = Path("data/raw")
path.mkdir(parents=True, exist_ok=True)
csv_path = path / f"{run_id}.csv"

n = 96
df = pd.DataFrame({
    "timestamp": pd.date_range("2026-01-01", periods=n, freq="h"),
    "target": np.sin(np.linspace(0, 6, n)),
    "temp": np.linspace(10, 20, n),
    "event": (np.arange(n) % 12 == 0).astype(float),
})
df.to_csv(csv_path, index=False)

out = run_preprocessing_pipeline(
    input_path=str(csv_path),
    config=PreprocessingConfig(
        run_id=run_id,
        lookback=24,
        horizon=1,
        covariate_cols=("temp", "event"),
    ),
    artifacts_dir="artifacts",
)
print(out["processed"])
PY
```

검증:
```bash
cd ~/spline-lstm
python3 - <<'PY'
import numpy as np
from pathlib import Path
p = sorted(Path("artifacts/processed").glob("local-mv-*/processed.npz"), key=lambda x: x.stat().st_mtime)
assert p, "multivariate processed.npz not found"
npz = np.load(p[-1])
for k in ["X_mv", "y_mv", "features_scaled"]:
    assert k in npz.files, f"missing key: {k}"
print("[PASS] multivariate/covariates:", p[-1])
PY
```

---

## 6) run_id mismatch 수동 재현 테스트

> 목적: CLI run_id와 preprocessor run_id 불일치 시 **실패해야 정상**

## 6.1 정상 산출물 생성

```bash
cd ~/spline-lstm
RUN_ID=rid-a-$(date +%Y%m%d-%H%M%S) EPOCHS=1 bash scripts/run_e2e.sh
```

## 6.2 의도적으로 불일치 실행 (실패 기대)

```bash
cd ~/spline-lstm
python3 -m src.training.runner \
  --run-id rid-b-manual \
  --processed-npz "artifacts/processed/${RUN_ID}/processed.npz" \
  --preprocessor-pkl "artifacts/models/${RUN_ID}/preprocessor.pkl" \
  --epochs 1 \
  --artifacts-dir artifacts
```

기대 결과:
- 종료코드 비정상(0이 아니어야 함)
- stderr 또는 로그에 `run_id mismatch` 포함

## 6.3 테스트 코드 기반 확인(선택)

```bash
cd ~/spline-lstm
python3 -m pytest -q tests/test_phase4_run_id_guard.py tests/test_artifacts.py::TestArtifactRules::test_validate_artifact_run_id_mismatch_raises
```

---

## 7) PASS/FAIL 판정 기준

## PASS
- 명시된 테스트 명령 종료코드가 `0`
- 필수 아티팩트가 모두 존재
- metrics에 필수 키 존재: `run_id`, `metrics`, (`mae`,`rmse`,`mape`,`r2`)
- run_id 정합성 통과: 경로 ↔ `meta.json` ↔ `preprocessor.pkl` ↔ `metrics.json`
- 확장 경로 테스트 시 비교 결과/멀티변수 키(`X_mv`,`y_mv`) 확인

## FAIL
- 테스트 명령 종료코드 `!= 0`
- 필수 아티팩트 누락
- run_id mismatch 발생(의도적 재현 테스트 제외)
- metrics/report 스키마 누락
- smoke_test.sh에서 `[SMOKE][FAIL]` 출력

---

## 8) 문제 발생 시 체크리스트 (자주 나는 오류와 해결)

1. **ModuleNotFoundError / 의존성 누락**
   - `python3 -m pip install -r requirements.txt` 재실행
   - venv 활성화 상태 확인

2. **`run_id` 규칙 위반(빈값/슬래시 포함)**
   - 새 run_id 생성: `run-YYYYmmdd-HHMMSS` 형태 사용

3. **`run_id mismatch` 오류**
   - `--processed-npz`, `--preprocessor-pkl`, `--run-id`가 같은 run인지 확인
   - 오염 run 폴더 폐기 후 새 run_id로 전처리부터 재실행

4. **아티팩트 파일 누락 (`metrics`, `best.keras` 등)**
   - `scripts/run_e2e.sh` 재실행 후 `artifacts/.../<run_id>` 존재 확인

5. **학습 실패/백엔드 문제(TensorFlow 등)**
   - `python3 -m pytest -q tests/test_models.py`로 최소 모델 경로 확인
   - Apple Silicon/로컬 환경에서 TF 설치 상태 재점검

6. **디스크/권한 문제**
   - `artifacts/`, `checkpoints/`, `logs/` 쓰기 가능 여부 확인

7. **지표 이상치(RMSE 과다, R2 급락)**
   - seed 고정 재실행: `EPOCHS=1`로 smoke 우선
   - 입력 데이터 스키마/결측/정렬 점검

---

## 9) 결과 기록 템플릿 (복붙용)

```markdown
# Manual Test Result - Spline-LSTM

- 일시:
- 담당자:
- 브랜치/커밋:
- 환경: (OS, python3 버전, venv 여부)

## A. Quick Gate
- 명령:
  - python3 -m pytest -q tests/test_phase4_run_id_guard.py tests/test_artifacts.py tests/test_training_runner_cli_contract.py tests/test_training_leakage.py
  - RUN_ID=local-quick-... EPOCHS=1 bash scripts/smoke_test.sh
- 결과: PASS / FAIL
- run_id:
- 로그 경로:

## B. E2E Manual
- 명령:
  - RUN_ID=local-e2e-... EPOCHS=1 bash scripts/run_e2e.sh
  - RUN_ID=local-e2e-smoke-... EPOCHS=1 bash scripts/smoke_test.sh
- 결과: PASS / FAIL
- 확인 아티팩트:
  - artifacts/processed/<run_id>/processed.npz
  - artifacts/processed/<run_id>/meta.json
  - artifacts/models/<run_id>/preprocessor.pkl
  - artifacts/checkpoints/<run_id>/best.keras
  - artifacts/checkpoints/<run_id>/last.keras
  - artifacts/metrics/<run_id>.json
  - artifacts/reports/<run_id>.md
  - artifacts/metadata/<run_id>.json

## C. Phase별 검증
- Phase1: PASS / FAIL
- Phase2: PASS / FAIL
- Phase3: PASS / FAIL
- Phase4: PASS / FAIL
- Phase5: PASS / FAIL
- 비고:

## D. 확장 경로
- compare_runner: PASS / FAIL (run_id: )
- multivariate/covariates: PASS / FAIL (run_id: )

## E. run_id mismatch 재현
- 명령:
- 기대: 실패(run_id mismatch)
- 실제: PASS(의도된 차단) / FAIL

## F. 최종 판정
- 최종: PASS / FAIL
- 주요 이슈:
- 후속 조치:
```

---

## 권장 실행 순서 (요약)

1. 사전 준비(환경/의존성)
2. Quick-gate (pytest + smoke_test)
3. E2E(run_e2e.sh → smoke_test.sh)
4. Phase1~5 핵심 테스트
5. 확장 경로(compare + multivariate)
6. run_id mismatch 재현(의도적 실패 확인)
7. 템플릿으로 결과 기록
