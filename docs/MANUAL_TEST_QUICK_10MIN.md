# MANUAL_TEST_QUICK_10MIN

목표: **10분 안에 현재 상태(PASS/FAIL)만 빠르게 판정**

---

## 0) 전제
- 경로: `~/spline-lstm`
- 기준: `python3` + `scripts/*`
- 권장: 터미널 1개에서 아래 순서 그대로 실행

---

## 1) 최소 사전 확인 (30초)
```bash
cd ~/spline-lstm
python3 --version
python3 -m pip --version
```

## 2) 핵심 계약 테스트 (2~3분)
```bash
cd ~/spline-lstm
python3 -m pytest -q \
  tests/test_phase4_run_id_guard.py \
  tests/test_artifacts.py \
  tests/test_training_runner_cli_contract.py \
  tests/test_training_leakage.py
```

## 3) 원클릭 E2E 실행 (2~3분)
```bash
cd ~/spline-lstm
RUN_ID=quick10-$(date +%Y%m%d-%H%M%S) EPOCHS=1 bash scripts/run_e2e.sh
```

## 4) 스모크 게이트(자동 판정) (2~3분)
```bash
cd ~/spline-lstm
RUN_ID=quick10-smoke-$(date +%Y%m%d-%H%M%S) EPOCHS=1 bash scripts/smoke_test.sh
```

## 5) 성공 판정(한눈 체크, 1분)
아래 4개가 모두 만족하면 **PASS**:
- pytest 종료코드 `0`
- `run_e2e.sh` 종료코드 `0`
- `smoke_test.sh` 출력에 `[SMOKE][OK] all checks passed`
- 아래 파일 존재
  - `artifacts/metrics/<run_id>.json`
  - `artifacts/reports/<run_id>.md`
  - `artifacts/checkpoints/<run_id>/best.keras`
  - `artifacts/models/<run_id>/preprocessor.pkl`

## 6) 실패 시 즉시 확인 경로 (1분)
우선순위:
1. 터미널 에러 마지막 50줄
2. 산출물 존재 여부
   - `artifacts/metrics/`
   - `artifacts/reports/`
   - `artifacts/checkpoints/<run_id>/`
   - `artifacts/models/<run_id>/`
   - `artifacts/processed/<run_id>/`
3. 테스트/실행 관련 문서
   - `docs/MANUAL_TEST_GUIDE.md`
   - `docs/CI_FAILURE_TRIAGE.md`

---

## 결과 보고 템플릿 (3줄 요약)
```text
1) 결과: PASS/FAIL (실행시각, 브랜치/커밋)
2) 실행: pytest=PASS/FAIL, run_e2e=PASS/FAIL, smoke=PASS/FAIL
3) 근거: run_id=<...>, 이슈 1줄(없으면 "이상 없음")
```