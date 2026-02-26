# PHASE 5 REVIEW — 확장 PoC 품질/리스크 평가 (Gate C)

- Reviewer: `reviewer-spline-mvp-phase5`
- Date: 2026-02-18
- Scope: `~/spline-lstm` Phase 5(확장 옵션) 구현/문서/검증 상태 리뷰
- Goal: 확장 PoC의 실효성, 품질, 리스크(특히 MVP 경로 회귀 가능성) 판정

---

## 1) 요청/검토 기준

필수 검토 포인트:
1. 확장 PoC 산출물 존재 여부 (설계/구현/테스트/리포트)
2. Must / Should / Nice 분류
3. 기존 MVP 경로 영향 여부(회귀 리스크) 평가
4. Gate C PASS/FAIL 판정

판정 규칙:
- **Must fix = 0 이면 Gate C PASS**

---

## 2) 수행 내역 (증빙 커맨드 + 결과)

### A. 전체 회귀 테스트 상태 확인
- 실행: `python3 -m pytest -q`
- 결과: **31 passed, 2 skipped**
- 해석: 현재 MVP 경로(Phase1~4 중심)는 테스트 기준 안정 상태.

### B. Phase5 관리 문서/산출물 존재 확인
- 점검:
  - `docs/PHASE5_PM_TRACKER.md` 존재
  - `docs/PHASE5_ARCH.md` 없음
  - `docs/TEST_RESULTS_PHASE5*.md` 없음
- 해석: PM 추적 문서는 있으나, Architect/Tester 산출물은 미비.

### C. 확장 기능 코드 경로 실체 점검
- 확인된 사실:
  1. `src/preprocessing/pipeline.py`에 `covariate_cols`, `X_mv/y_mv` 생성 분기 존재(부분 PoC)
  2. `src/preprocessing/window.py`에 `make_windows_multivariate()` 존재
  3. `src/models/lstm.py`는 입력 feature를 강제적으로 1로 제한 (`X.shape[2] != 1` 예외)
  4. `src/training/runner.py`는 모델 타입 선택 인자(`--model-type`) 및 multivariate 입력 선택 경로 부재
- 해석: 전처리 레벨의 부분 구현은 있으나, 학습/평가 러너와 연결되지 않아 E2E 확장 PoC로는 미완성.

### D. 확장 요구사항 대비 충족도 점검 (BLUEPRINT + PM Tracker 기준)
- 요구: GRU/Attention 비교, multivariate 입력, covariates 통합, edge(ONNX/TFLite) 벤치
- 현황:
  - GRU: 미구현
  - Attention: 클래스는 존재하나 러너 실험 경로/비교 리포트 부재
  - multivariate/covariates: 전처리 초안만 존재, E2E 미연결
  - edge 벤치: 미구현
- 해석: Phase5 핵심 완료 조건 다수가 미충족.

---

## 3) 항목별 판정

### 3-1) 확장 PoC 실행 가능성(E2E)
**판정: 미충족 (Open-Must)**
- 근거: 러너가 LSTM 단일 경로 중심이며, 모델 전환/멀티변수 입력 실험 계약이 없음.

### 3-2) 확장 기능 검증 가능성(테스트/리포트)
**판정: 미충족 (Open-Must)**
- 근거: `TEST_RESULTS_PHASE5*` 부재, 확장 전용 스모크/회귀 테스트 부재.

### 3-3) 문서/계약 완결성
**판정: 미충족 (Open-Must)**
- 근거: `PHASE5_ARCH.md` 부재로 확장 계약(입력 스키마/지표/실패 기준) 미고정.

### 3-4) MVP 경로 안정성
**판정: 충족 (Closed)**
- 근거: 전체 테스트 green(31 passed), 기본 경로는 여전히 단일변수/LSTM 계약 유지.

---

## 4) Must / Should / Nice

## Must fix
1. **Phase5 아키텍처/계약 문서 고정 (`docs/PHASE5_ARCH.md`)**
   - 모델 비교 기준, 입력 스키마(multivariate/covariates), PASS/FAIL 지표를 명시해야 함.
2. **확장 E2E 실행 경로 구현 (runner 연동)**
   - 최소: 모델 선택(LSTM/GRU/Attention), multivariate 입력 사용 경로, 결과 artifact(run_id) 일관 저장.
3. **Phase5 검증 산출물 확보 (`docs/TEST_RESULTS_PHASE5*.md`)**
   - 확장 경로가 실제 실행/재현 가능함을 테스트 로그로 증명 필요.

## Should fix
1. covariates 스케일링 정책 분리(현재는 target scaler 공유 형태의 최소 PoC)
2. 확장 전용 smoke 스크립트 추가 (`scripts/smoke_test_phase5.sh`)
3. metrics/report에 `model_type`, `n_features`, `covariate_cols` 등 추적 필드 추가

## Nice to have
1. ONNX/TFLite 변환 자동화 + latency/memory/accuracy 비교 템플릿
2. 확장 실험 매트릭스 자동 집계 테이블(모델별 성능/비용)
3. README/RUNBOOK의 확장 섹션 분리(운영자 관점 빠른 실행 가이드)

---

## 5) 기존 MVP 경로 영향 여부(회귀 리스크)

### 결론
- **현재 시점 회귀 리스크: 낮음~중간(Low-Medium)**

### 근거
- 낮음 요인:
  - 기본 테스트 스위트 전체 통과(31 passed)
  - 모델 입력 계약이 univariate로 강하게 고정되어 기존 경로 보호
- 중간 요인:
  - 전처리에 확장 분기(`X_mv/y_mv`)가 도입됐지만 러너/테스트와 비연결 상태
  - “부분 구현 + 미검증 경로”는 향후 통합 시 회귀 가능성을 키움

### 회귀 방지 권고
1. 확장 기능 merge 전, 기존 MVP 게이트 테스트(Phase1~4 핵심) 필수 고정
2. 확장 플래그 기본값 OFF + backward compatibility 테스트 추가
3. run_id/metadata 계약을 확장 경로에도 동일 적용

---

## 6) Gate C 판정

- **Must fix 개수: 3**
- **Gate C: FAIL**

판정 사유:
- Phase5 핵심 완료조건(설계 고정, E2E 경로, 테스트 증빙) 미충족.
- 규칙(“Must fix=0이면 PASS”) 불충족.

---

## 7) Standard Handoff

### Summary
- Phase5는 일부 전처리 PoC 코드가 존재하나, 확장 E2E로는 미완성 상태.
- MVP 경로는 현재 테스트 기준 안정적이나, 확장 통합 시 잠재 회귀 리스크 존재.

### Evidence
- `python3 -m pytest -q` → `31 passed, 2 skipped`
- `docs/PHASE5_PM_TRACKER.md` 확인 (다수 WBS NS)
- `src/preprocessing/pipeline.py`, `src/preprocessing/window.py` 확장 분기 존재
- `src/models/lstm.py`, `src/training/runner.py`에서 확장 E2E 경로 부재 확인

### Risks
1. 확장 요구사항 대비 구현/검증 공백으로 인한 PoC 신뢰도 부족
2. 부분 구현(전처리만 확장) 상태 장기화 시 통합 결함 위험 증가
3. 문서/테스트 부재로 인수인계 및 재현성 저하

### Next Actions
1. `PHASE5_ARCH.md` 작성(계약/평가지표/실패기준 고정)
2. runner 확장(모델 선택 + multivariate 입력) 및 artifact 계약 정렬
3. Phase5 테스트/벤치 문서(`TEST_RESULTS_PHASE5*.md`) 제출 후 재심사

### Final Decision
- **Gate C FAIL** (Must fix 3)
