# PHASE 2 PM TRACKER (LSTM 학습 파이프라인 MVP)

> **HISTORICAL NOTE (문서 정합성):** 이 문서는 해당 시점의 진행 스냅샷입니다. 현재 운영/실행 계약의 단일 기준은 `docs/RUNBOOK.md`와 최신 ARCH/FINAL/CLOSEOUT 문서입니다.
> 경로/CLI/게이트 상태가 본문과 다를 수 있으며, 운영 판단 시 현재 기준 문서를 우선합니다.


## Standard Handoff Format

### 1) Request / Scope
- 역할: PM (운영/진행 관리)
- 프로젝트: `~/spline-lstm`
- 목표: **Phase 2 = LSTM 학습 파이프라인 MVP 완료 관리**
- 산출물 요구:
  - `docs/PHASE2_PM_TRACKER.md`
  - WBS, 의존성, Gate(A/Coder/Reviewer/Tester) 판정, Completion Declaration
- 기준일: 2026-02-18

### 2) 현재 코드/증빙 기준선 (What I Checked)
- 핵심 코드
  - `src/models/lstm.py`
  - `src/training/trainer.py`
- 테스트
  - `tests/test_training_leakage.py`
  - `tests/test_artifacts.py`
  - `tests/test_models.py`
- 로컬 검증 결과
  - `python3 -m pytest -q` → **20 passed, 2 skipped**
- 현재 아티팩트 상태
  - Phase 1 전처리 산출물 중심(`artifacts/processed/smoke-001`, `artifacts/models/smoke-001/preprocessor.pkl`)
  - Phase 2 핵심 산출물(당시 기준: `artifacts/models/{run_id}/model.keras`, 현재 기준: `artifacts/checkpoints/{run_id}/{best,last}.keras`, `artifacts/metrics/{run_id}.json`, `artifacts/reports/{run_id}.md`)은 **실행 증빙 미확보**

---

## 0) 문서 목적
- Phase 2 범위(학습 루프/평가/아티팩트 저장/재현성)에서 **실행 중심으로 완료 여부를 통제**한다.
- 역할별 Gate를 통합해, “코드가 있음”이 아니라 “운영 가능한 MVP 상태”를 완료 기준으로 사용한다.

---

## 1) Phase 2 목표 / 완료 조건

### 목표
1. LSTM 학습 파이프라인(train/val/test 시간순 split) 운영 가능 상태 확보
2. leakage-safe 학습 정책 고정(train-only normalization, explicit validation_data, shuffle=False)
3. run_id 기반 모델/지표/리포트 아티팩트 저장 규칙 운영 검증
4. 최소 1회 E2E 학습 실행 근거(명령/로그/산출물) 확보

### Phase 2 Done 조건(요약)
- [ ] Phase 2 WBS P2-01~P2-10 전부 `DN`
- [ ] Gate A/Coder/Reviewer/Tester 전부 `PASS`
- [ ] Completion Declaration의 Blocker 0건(또는 승인된 예외만 존재)

---

## 2) WBS (작업분해), 담당(role), 의존성, 상태

> 상태 정의: `NS(미착수) / IP(진행중) / RD(검토대기) / DN(완료)`

| WBS ID | 작업 | 담당(Role) | 선행 의존성 | 산출물 | 상태 | 완료 체크리스트 |
|---|---|---|---|---|---|---|
| P2-01 | Phase 2 범위/입출력 계약 확정(학습/평가/아티팩트) | A(Architect) | Phase1 종료 | 본 문서 1~3장 | DN | [x] 학습 정책 명시 [x] run_id 규칙 반영 [x] 범위 외 항목 분리 |
| P2-02 | LSTM 모델 I/O 계약 점검(lookback, output_units) | Coder | P2-01 | `src/models/lstm.py` | DN | [x] X/y shape 검증 [x] output_units 계약 [x] 예외 메시지 |
| P2-03 | 학습 루프 정책 고정(split→normalize→fit) | Coder | P2-01 | `src/training/trainer.py` | DN | [x] 시간순 split [x] train-only normalize [x] explicit val + shuffle=False |
| P2-04 | 지표 계산/리턴 계약 고정(MAE, MSE, RMSE, robust MAPE, MASE, R2) | Coder | P2-03 | `trainer.compute_metrics` | DN | [x] 지표 산출 [x] 결과 dict 고정 [x] train 결과 포함 |
| P2-05 | run_id 아티팩트 저장 규칙 구현 | Coder | P2-03 | `save_run_artifacts` | DN | [x] model/preprocessor/metrics/config/report 저장 [x] run_id 검증 [x] 경로 규칙 |
| P2-06 | 아티팩트 run_id 일치 검증 로직 구현 | Coder | P2-05 | `validate_artifact_run_id_match` | DN | [x] mismatch 예외 [x] 경로 파싱 오류 처리 |
| P2-07 | 학습 누수 방지 회귀 테스트 유지 | Tester | P2-03 | `tests/test_training_leakage.py` | DN | [x] train-only normalize 검증 [x] explicit val/shuffle=False 검증 |
| P2-08 | 아티팩트 규칙 테스트 유지 | Tester | P2-05, P2-06 | `tests/test_artifacts.py` | DN | [x] 저장 파일 존재 [x] invalid run_id 거부 [x] mismatch 검증 |
| P2-09 | 실환경 E2E 학습 1회 실행 증빙(run_id 결과물) | Tester | P2-02~P2-08 | metrics/report/model 아티팩트 | IP | [ ] 학습 실행 로그 [ ] run_id 산출물 5종 [ ] 재실행 체크 |
| P2-10 | Gate 통합 판정 + Completion Declaration 갱신 | PM(메인) | P2-09 | 본 문서 5~6장 | IP | [ ] Gate 4종 PASS [ ] blocker 0 [ ] 완료 선언 |

---

## 3) 의존성 맵 (Execution Dependency)

```text
P2-01
 ├─> P2-02 ─┐
 └─> P2-03 ─┼─> P2-04
            ├─> P2-05 ─> P2-06
            └─> P2-07
P2-05/P2-06 ─> P2-08
P2-02~P2-08 ─> P2-09 ─> P2-10
```

### 크리티컬 패스
- **P2-03 → P2-07 → P2-09 → P2-10**
- 사유: 코드/테스트 통과만으로는 완료 불가이며, 최종적으로 실제 run_id 산출물 기반 검증(P2-09)이 필요

---

## 4) Gate 판정 기준 및 현재 판정

## 4.1 Gate A (Architect)
**PASS 기준**
- [x] Phase 2 범위(학습 파이프라인 MVP)와 제외범위(멀티변수/고도화) 분리
- [x] 학습 정책(chronological split, train-only normalize, explicit validation, shuffle=False) 문서화
- [x] 아티팩트 계약(run_id path) 정의

**현재 판정: `PASS`**
- 근거: `docs/BLUEPRINT.md`, `src/training/trainer.py`, `src/models/lstm.py`와 계약 일치

## 4.2 Gate Coder
**PASS 기준**
- [x] 모델/학습 코드 계약 구현
- [x] leakage-safe 정책 반영
- [x] 아티팩트 저장/검증 로직 구현

**현재 판정: `PASS`**
- 근거:
  - `src/models/lstm.py` 입력/출력 shape 검증
  - `src/training/trainer.py` split 후 normalize, explicit validation_data, shuffle=False
  - `save_run_artifacts`, `validate_artifact_run_id_match` 구현 완료

## 4.3 Gate Reviewer
**PASS 기준**
- [x] Must-fix 이슈 0
- [x] 정책 위반(누수/랜덤 분할) 재발 없음
- [x] 코드-테스트 계약 일관성 유지

**현재 판정: `PASS (조건부)`**
- 근거: 누수/아티팩트 관련 테스트 통과, 기존 Phase1 Gate C 교정사항 유지
- 조건부 사유: 실제 학습 실행 아티팩트 검증(P2-09) 전 최종 고정은 보류

## 4.4 Gate Tester
**PASS 기준**
- [x] 자동화 테스트 통과
- [ ] 실환경 E2E 학습 1회 성공 + run_id 산출물 확보
- [ ] 재실행 시 산출 규칙 일관성 확인

**현재 판정: `PENDING`**
- 근거:
  - 자동화: `python3 -m pytest -q` → 20 passed, 2 skipped
  - 미완료: Phase 2 핵심 run_id 학습 산출물(모델/지표/리포트) 실증 미확보

## 4.5 통합 Gate 판정
- A: PASS
- Coder: PASS
- Reviewer: PASS(조건부)
- Tester: PENDING

➡ **통합 판정: `IN PROGRESS (미완료)`**

---

## 5) 실행 계획 (남은 작업 중심)

### 즉시 실행 TODO (P0)
1. **P2-09 수행**: 학습 스크립트 1회 실행 후 run_id 산출물 5종 확보
   - 기대 산출물:
     - (당시 초안) `artifacts/models/{run_id}/model.keras`
     - (현재 구현) `artifacts/checkpoints/{run_id}/best.keras`, `artifacts/checkpoints/{run_id}/last.keras`
     - `artifacts/models/{run_id}/preprocessor.pkl`
     - `artifacts/metrics/{run_id}.json`
     - `artifacts/configs/{run_id}.yaml`
     - `artifacts/reports/{run_id}.md`
2. 테스트 결과와 아티팩트 경로를 본 문서에 링크 형태로 기록
3. Tester Gate `PASS/FAIL` 명시 후 P2-10 완료

### 차순위 TODO (P1)
- `tests/test_models.py`의 ML 테스트(skip 항목) 실행 환경(TensorFlow)에서 1회 검증 로그 확보
- README에 Phase 2 운영 커맨드(학습/아티팩트 생성/검증) 명시
- (완료) 계약 테스트 보강: `tests/test_inference_contract.py` 추가 (predictions.csv 컬럼 계약 + 실패 코드 매핑)

---

## 6) Completion Declaration

- Phase: **Phase 2 (LSTM 학습 파이프라인 MVP)**
- 현재 완료 여부: **미완료 (IN PROGRESS)**
- Gate 상태:
  - A(Architect): `PASS`
  - Coder: `PASS`
  - Reviewer: `PASS (조건부)`
  - Tester: `PENDING`

### 현재 Blocker
1. 실환경 학습 실행 기반 run_id 산출물 증빙 부재 (P2-09 미완료)
2. Tester Gate 최종 PASS 미확정

### 완료 선언 체크리스트
- [ ] P2-01 ~ P2-10 `DN`
- [ ] Gate A/Coder/Reviewer/Tester 모두 `PASS`
- [ ] Blocker 0건(또는 승인된 예외만 존재)
- [ ] 완료일/승인자/근거 링크(테스트 로그, artifact 경로) 기록

> 위 조건 충족 시 본 섹션을 `완료 (DONE)`로 변경하고, 최종 승인 로그를 첨부한다.

---

## 7) PM 요약
- 코드/테스트 기준으로 Phase 2 핵심 구현은 상당 수준 완료.
- 단, **운영 완료 선언은 실행 증빙(P2-09) 없이는 불가**.
- 현재 가장 중요한 다음 액션은 “run_id 기준 실제 학습 산출물 확보 + Tester Gate 종료”다.
