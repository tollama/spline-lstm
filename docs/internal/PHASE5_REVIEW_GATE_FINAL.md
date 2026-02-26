# PHASE5_REVIEW_GATE_FINAL — Gate C 재최종 판정

## Standard Handoff Format

### 1) Summary
- 대상: `~/spline-lstm`
- 범위: `coder-spline-mvp-phase5` 반영 이후 Reviewer 재최종 판정
- 검증 축:
  1. `docs/PHASE5_ARCH.md` 존재 및 계약 정합성
  2. 확장 E2E 경로(`compare_runner`, multivariate 전처리) 구현 여부
  3. `docs/TEST_RESULTS_PHASE5.md` 최신화/증빙 적정성
  4. MVP 본선 경로 회귀 위험

**최종 판정: Gate C = FAIL**
- 사유: 핵심 계약(Phase5 ARCH의 러너 인터페이스/입력 계약)과 실제 실행 경로가 아직 부분 불일치.

---

### 2) Evidence Check

#### A. `PHASE5_ARCH.md` 존재/계약 정합성
- 확인 결과: **존재함** (`docs/PHASE5_ARCH.md`).
- 문서상 고정 계약(요약):
  - `--model-type`, `--feature-mode`, `--target-cols`, `--covariate-spec`
  - 입력/라벨 계약: `X=[B,L,F_total]`, `y=[B,H*F_target]`
  - 산출물 확장 키: `feature_names`, `target_indices` 등

- 구현 정합성 점검:
  - `src/models/lstm.py`: `input_features` 일반화 + `GRUModel` 추가는 반영됨(긍정).
  - `src/training/runner.py`: **여전히 LSTM 단일 경로**, `--model-type`/`--feature-mode` 등 확장 인자 부재.
  - `src/preprocessing/pipeline.py`: multivariate PoC(`X_mv`,`y_mv`,`features_scaled`) 저장은 반영됨.

=> 판단: **문서는 존재/개선됨. 단, 문서 계약 대비 실행 경로 정합성은 완전 충족 아님.**

#### B. 확장 E2E 경로 구현 여부 (`compare_runner`, multivariate 전처리)
- `src/training/compare_runner.py`: 존재, LSTM vs GRU 비교 실행 가능.
- `scripts/run_compare.sh`: compare runner 실행 경로 제공.
- 증빙 파일: `artifacts/comparisons/phase5-poc-001.json` (생성 시각 포함).

- multivariate 전처리:
  - `src/preprocessing/window.py`: `make_windows_multivariate()` 구현.
  - `src/preprocessing/pipeline.py`: `covariate_cols` 입력 시 `X_mv`, `y_mv` 저장.
  - 증빙: `artifacts/processed/phase5-mv-001/meta.json` 및 `processed.npz` 내 `X_mv`,`y_mv` 확인.

- 미충족 지점:
  - `compare_runner`는 현재 `input_features=1` 고정(실질적으로 univariate 기반).
  - `runner.py`가 `X_mv`를 학습 입력으로 사용하는 확장 E2E를 제공하지 않음.

=> 판단: **PoC 구성요소는 구현됨. 그러나 “multivariate까지 연결된 통합 E2E”는 부분 미완.**

#### C. `TEST_RESULTS_PHASE5` 최신화/증빙
- 문서 존재: `docs/TEST_RESULTS_PHASE5.md`.
- 문서 기재 명령 재실행 결과:
  - 세트 A: `17 passed, 2 skipped` (11.36s)
  - 세트 B: `13 passed` (2.23s)
  - 총합: `30 passed, 2 skipped` (문서와 일치)
- 경고(비차단): `NotOpenSSLWarning`, `PyparsingDeprecationWarning`.

=> 판단: **테스트 결과 문서는 최신 상태이며, 최소한의 회귀/스모크 증빙은 유효.**

#### D. MVP 본선 경로 회귀 위험
- 긍정 요소:
  - 기존 MVP 핵심 회귀 테스트군 통과.
  - `run_id` guard/아티팩트 계약 테스트 유지.
- 잔여 위험:
  - Phase5 문서 계약(확장 러너/입력 모드)과 코드 실행 경로의 불일치 상태에서, 향후 강제 통합 시 회귀 유발 가능성 존재.
  - multivariate 경로가 현재 “전처리 산출물 생성”에 치우쳐 있고, 학습 러너 본선 경로 결합이 약함.

=> 위험도: **중간(Medium)**

---

### 3) Must / Should / Nice

## Must fix
1. **ARCH 계약과 Runner 인터페이스 정합화 (차단 이슈)**
   - `docs/PHASE5_ARCH.md`의 핵심 계약(`--model-type`, `--feature-mode`, 확장 입력 계약)이 `src/training/runner.py`에 반영되어야 함.
   - 현재 상태는 문서-코드 간 불일치로 Gate C 차단 사유.

## Should fix
1. `compare_runner`가 multivariate 입력(`F_total>1`)을 직접 수용하도록 확장하고, 비교 결과에 데이터 모드(`univariate/multivariate`)를 명시.
2. `processed.npz` 확장 키(`feature_names`, `target_indices`)를 ARCH 계약 수준으로 명시/저장해 후속 단계 호환성 강화.
3. `docs/TEST_RESULTS_PHASE5.md`에 compare_runner 실행 결과(명령/산출물/요약 지표)를 별도 섹션으로 추가.

## Nice to have
1. Phase5 전용 CI 게이트(job) 추가: compare_runner + multivariate smoke + MVP 핵심 회귀 묶음.
2. 경고 노이즈(SSL/pyparsing) 저감 가이드 추가.

---

### 4) Gate C Decision
- 규칙: Must fix = 0 이어야 PASS
- 현재: **Must fix 1건 잔존**

## 최종 판정: **Gate C FAIL**

---

### 5) Re-test Exit Criteria (권장)
1. `runner.py`에 ARCH 확장 인자/분기 반영 + 최소 1개 multivariate 학습 경로 E2E PASS 증빙.
2. `TEST_RESULTS_PHASE5.md`에 해당 실행 로그/결과를 최신 반영.
3. MVP 핵심 회귀군 재통과 확인(기존 30 passed, 2 skipped 수준 유지).

---

### 6) Quick Evidence Index
- 계약 문서: `docs/PHASE5_ARCH.md`
- 확장 비교 러너: `src/training/compare_runner.py`, `scripts/run_compare.sh`
- multivariate 전처리: `src/preprocessing/pipeline.py`, `src/preprocessing/window.py`
- 테스트 결과: `docs/TEST_RESULTS_PHASE5.md`
- 비교 산출물: `artifacts/comparisons/phase5-poc-001.json`
- multivariate 산출물: `artifacts/processed/phase5-mv-001/meta.json`, `.../processed.npz`
