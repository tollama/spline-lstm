# Spline-LSTM Runbook (최소 운영 절차)

본 문서는 MVP Phase 4 운영 최소 절차를 정의한다.  
기준: `docs/PHASE4_ARCH.md`

---

## 1) 사전 확인 (1분)

```bash
cd ~/spline-lstm
python3 --version
python3 -m pip show numpy pandas tensorflow urllib3 || true
```

- 작업 디렉터리: `~/spline-lstm`
- Python 실행 가능해야 함
- 쓰기 권한: `artifacts/` 생성 가능해야 함

### 1.1 권장 런타임 버전

- 권장 Python: **3.10 ~ 3.11**
- TensorFlow: `>=2.14,<2.17` (requirements 기준)

> Python 3.9 + LibreSSL 환경에서는 `urllib3`의 `NotOpenSSLWarning`이 발생할 수 있음.
> 해당 환경에서는 `urllib3<2`를 사용하거나(OpenSSL 기반 Python 권장),
> 가급적 OpenSSL 1.1.1+로 빌드된 Python 런타임으로 전환한다.

---

## 2) 표준 실행 (One-click E2E)

```bash
cd ~/spline-lstm
RUN_ID=phase4-smoke-$(date +%Y%m%d-%H%M%S)
RUN_ID="$RUN_ID" EPOCHS=3 bash scripts/run_e2e.sh
```

성공 기준:
- 최종 종료코드 `0`
- `artifacts/reports/$RUN_ID.md` 생성
- `artifacts/metrics/$RUN_ID.json` 생성

---

## 3) 산출물 확인 (필수)

```bash
ls -l \
  artifacts/processed/$RUN_ID/processed.npz \
  artifacts/processed/$RUN_ID/meta.json \
  artifacts/models/$RUN_ID/preprocessor.pkl \
  artifacts/checkpoints/$RUN_ID/best.keras \
  artifacts/checkpoints/$RUN_ID/last.keras \
  artifacts/metrics/$RUN_ID.json \
  artifacts/reports/$RUN_ID.md \
  artifacts/metadata/$RUN_ID.json
```

누락 시 실패로 간주.

---

## 4) run_id 일치 검증 (운영 게이트)

### 4.1 자동 검증
`src.training.runner`는 아래 계약 위반 시 즉시 실패한다.
- CLI `--run-id`
- `processed.npz` 경로 run_id
- `meta.json`의 `run_id`
- `preprocessor.pkl` 내부 `run_id`
- `processed.npz` 필수 키: `feature_names`, `target_indices`
- 표준 artifacts 경로(`.../processed/{run_id}/processed.npz`)인 경우 `split_contract.json` 존재 + `schema_version=phase1.split_contract.v1`

### 4.2 수동 점검 (권장)

```bash
python3 - <<'PY'
import json, pickle, sys
from pathlib import Path

run_id = sorted(Path("artifacts/metrics").glob("*.json"), key=lambda p: p.stat().st_mtime)[-1].stem

prep = Path(f"artifacts/models/{run_id}/preprocessor.pkl")
metrics = Path(f"artifacts/metrics/{run_id}.json")

with open(prep, "rb") as f:
    prep_obj = pickle.load(f)
with open(metrics, "r", encoding="utf-8") as f:
    m = json.load(f)

ok = True
if prep_obj.get("run_id") != run_id:
    print(f"[FAIL] preprocessor run_id mismatch: {prep_obj.get('run_id')} != {run_id}")
    ok = False
if m.get("run_id") != run_id:
    print(f"[FAIL] metrics run_id mismatch: {m.get('run_id')} != {run_id}")
    ok = False

if not ok:
    sys.exit(27)
print("[OK] run_id consistency check passed")
PY
```

---

## 5) 지표 확인 기준

문서 표기: **MAE, MSE, RMSE, robust MAPE, R2**  
JSON 키: `mae`, `mse`, `rmse`, `mape`, `r2`

> `mape`는 non-zero target 기준의 robust MAPE 구현이다.

---

## 6) Health Check 최소 명령

```bash
python3 - <<'PY'
import json, sys
from pathlib import Path

run_id = sorted(Path("artifacts/metrics").glob("*.json"), key=lambda p: p.stat().st_mtime)[-1].stem
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
missing = [p for p in required if not Path(p).exists()]
if missing:
    print("[FAIL] missing artifacts:")
    for p in missing:
        print(" -", p)
    sys.exit(30)

with open(f"artifacts/metrics/{run_id}.json", "r", encoding="utf-8") as f:
    m = json.load(f)
for key in ["run_id", "metrics", "checkpoints"]:
    if key not in m:
        print(f"[FAIL] metrics missing key: {key}")
        sys.exit(30)

for mk in ["mae", "mse", "rmse", "mape", "r2"]:
    if mk not in m["metrics"]:
        print(f"[FAIL] metrics missing field: {mk}")
        sys.exit(30)

print(f"[OK] health check passed: {run_id}")
PY
```

---

## 7) 운영 인수인계 메모

- 신규 운영자는 본 문서 2→3→4→5→6 순서만 수행해도 최소 운영 가능
- 배포 전 smoke 1회, 장애 후 재실행 1회는 필수
- 계약 상세/정책 변경은 `docs/PHASE4_ARCH.md`를 단일 소스로 사용

---

## 8) 현재 상태 (Phase 요약)

- Phase 1: 전처리 파이프라인 가동
- Phase 2: 학습/평가 기본 플로우 가동
- Phase 3: 단일 runner CLI 가동
- Phase 4: E2E+smoke+run_id 게이트 가동
- Phase 5(PoC): GRU 비교 + covariate/multivariate 전처리 경로 제공
