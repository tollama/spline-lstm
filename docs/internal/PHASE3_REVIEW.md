# PHASE 3 REVIEW — Baseline 타당성 / 재현성 / 메타데이터 무결성

- Reviewer: `reviewer-spline-mvp-phase3`
- Date: 2026-02-18
- Scope: `~/spline-lstm` (Phase 3 MVP 요구사항 검토)
- Goal: baseline 타당성 / 재현성 / 메타데이터 무결성

---

## 1) 검증 방법

### 실행 커맨드
1. 전체 테스트
```bash
python3 -m pytest -q
```
2. Phase 3 요구사항 테스트(실질적으로 `-q -rs` 실행 시 포함)
- `tests/test_phase3_repro_baseline.py`

### 결과 요약
- 최종 테스트 상태: **2 failed, 27 passed, 2 skipped**
- 실패 테스트:
  1. `test_phase3_reproducibility_and_baseline_vs_model`
  2. `test_phase3_metadata_presence_split_config_commit`

---

## 2) 핵심 판정 (Must/Should/Nice)

## Must fix

### M1. Baseline 타당성 미충족 (naive baseline 대비 성능 열위)
- 근거 테스트: `tests/test_phase3_repro_baseline.py::test_phase3_reproducibility_and_baseline_vs_model`
- 실패 메시지:
  - `model_rmse=0.257482`, `baseline_rmse=0.083772`, 허용계수 `1.15`
- 판정 이유:
  - Phase 3의 baseline 타당성 핵심 조건(naive baseline 대비 동등/우위)을 현재 모델이 만족하지 못함.
  - 단순 변동이 아니라 3배 이상 열위 수준으로, 실험 baseline 관점에서 **차단 이슈**.

### M2. 메타데이터 무결성 미충족 (commit hash 누락)
- 근거 테스트: `tests/test_phase3_repro_baseline.py::test_phase3_metadata_presence_split_config_commit`
- 실패 메시지:
  - `Missing commit hash metadata. Expected one of keys: commit_hash/git_commit/git_sha/commit`
- 코드 근거:
  - `src/training/runner.py` payload 구성(`136~168`)에 `commit_hash/git_sha` 계열 필드가 없음.
- 판정 이유:
  - 재현/추적성의 필수 메타데이터(코드 버전 식별자) 부재.
  - 요구 범위(메타데이터 무결성)에서 **차단 이슈**.

## Should fix

### S1. 재현성 고정 수준 강화
- 현상:
  - seed 설정(`runner.py` main)에도 실행별 metric 편차가 관측됨(수동 검증에서 RMSE 편차 존재).
  - 현재 Phase3 테스트 허용치 내일 수는 있으나, 환경 의존적 드리프트 리스크가 남음.
- 권고:
  - TF deterministic op 옵션(`TF_DETERMINISTIC_OPS=1`) 및 가능 시 단일 thread/연산자 고정 전략 문서화.
  - `metrics`에 backend/OS/python/tf version까지 기록해 원인 추적성 강화.

### S2. 메타 스키마 정렬 강화
- 현상:
  - `src/preprocessing/pipeline.py:118~124`의 `meta.json`은 최소 필드만 포함하고,
    `docs/PHASE2_ARCH.md:60~65`에서 정의한 `lookback/horizon/scaler_type/schema_version` 최소 스키마와 불일치.
- 권고:
  - 전처리/학습 메타 스키마를 단일 계약으로 고정하고 검증 테스트 추가.

## Nice to have

### N1. 리포트에 baseline 비교 섹션 자동 삽입
- `docs/PHASE2_ARCH.md:170~175`의 권고(naive baseline 비교/TODO 명시)를 자동화하면 품질 게이트 해석이 쉬워짐.

### N2. Git SHA 획득 실패 시 graceful fallback 표준화
- 예: detached/비-git 환경에서 `git_sha: "unknown"`, `git_sha_error` 필드 추가.

---

## 3) 세부 근거

### 3.1 Baseline 관련
- 실패 테스트가 동일 synthetic split에서 persistence baseline을 계산해 비교함.
- 현재 구현은 baseline metric을 payload/report에 포함하지 않음 (`src/training/runner.py:136~203`).
- 실제 실패 수치상 baseline 대비 모델 성능이 크게 뒤처짐.

### 3.2 메타데이터 관련
- `split_indices`는 `Trainer.train()` 결과에 포함되며(`src/training/trainer.py:229~233`) runner payload에 반영 가능 구조.
- commit hash는 runner payload 생성 시점에 수집/주입 코드가 없음(`src/training/runner.py:136~168`).

---

## 4) Gate C 판정

- Must fix 개수: **2**
- 규칙: **Must fix = 0 이면 PASS**
- **Gate C: FAIL**

---

## 5) Standard Handoff Format

### 5.1 Summary
- Phase 3 목표( baseline 타당성 / 재현성 / 메타데이터 무결성 ) 중,
  baseline 타당성과 메타데이터 무결성에서 차단 이슈 2건 확인.
- 현재 테스트 상태는 2 fail로 Gate C 통과 불가.

### 5.2 Decisions / Must-Should-Nice
- **Must**: M1 baseline 성능 열위 해소, M2 commit hash 메타데이터 추가
- **Should**: 재현성 고정전략 강화, 메타 스키마 정렬
- **Nice**: baseline 섹션 자동화, git SHA fallback 표준화

### 5.3 Deliverables
- [x] `docs/PHASE3_REVIEW.md` 작성
- [x] Must/Should/Nice 분류
- [x] Gate C PASS/FAIL 판정

### 5.4 Immediate Next Actions
1. `runner`에 commit hash 주입 (`git rev-parse --short HEAD`) 및 payload 키(`git_sha`) 추가
2. `runner`에 naive baseline 계산/기록 추가(최소 RMSE) 후 모델 비교 기준 충족하도록 모델/학습 설정 조정
3. 전처리 `meta.json` 스키마를 `PHASE2_ARCH` 최소 계약과 정렬
4. 수정 후 `pytest -q` 재실행하여 Must 0건 확인

### 5.5 Risks / Open Points
- TF backend/환경 차이로 재현성 편차가 남을 수 있으므로 deterministic 실행 가이드가 필요.
- baseline 미충족은 데이터/모델/epoch 설정 문제일 수 있어, 단순 코드 패치만으로 해결되지 않을 가능성 있음.
