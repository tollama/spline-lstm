# PHASE 3 PM TRACKER (기준선 비교 + 재현성 고정)

> **HISTORICAL NOTE (문서 정합성):** 이 문서는 해당 시점의 진행 스냅샷입니다. 현재 운영/실행 계약의 단일 기준은 `docs/RUNBOOK.md`와 최신 ARCH/FINAL/CLOSEOUT 문서입니다.
> 경로/CLI/게이트 상태가 본문과 다를 수 있으며, 운영 판단 시 현재 기준 문서를 우선합니다.


## Standard Handoff Format

### 1) Request / Scope
- 역할: PM (운영/진행 관리)
- 프로젝트: `~/spline-lstm`
- 목표: **Phase 3 = 기준선 비교 자동화 + 재현성 고정 완료 관리**
- 산출물 요구:
  - `docs/PHASE3_PM_TRACKER.md`
  - WBS, 의존성, Gate 판정, Completion Declaration
- 기준일: 2026-02-18

### 2) 현재 코드/증빙 기준선 (What I Checked)
- 핵심 문서
  - `docs/BLUEPRINT.md` (Phase 3 요구: naive/moving-average 기준선, seed/환경 고정)
  - `docs/PHASE2_PM_TRACKER.md`
  - `docs/PHASE2_REVIEW_GATE_FINAL_2.md`
- 핵심 코드
  - `src/training/runner.py` (seed 설정 존재)
  - `src/training/trainer.py` (학습/평가/아티팩트 저장)
- 테스트/실행
  - `python3 -m pytest -q` → **27 passed, 2 skipped**
- 현재 갭(Phase 3 관점)
  - 기준선(naive/moving average) 계산 및 비교 리포트 **전용 모듈/테스트 부재**
  - 재현성 고정(환경 lock, run metadata의 commit hash/환경정보 기록) **운영 계약 미완료**

---

## 0) 문서 목적
- Phase 3 범위(기준선 비교 + 재현성 고정)를 **실행 중심으로 관리**한다.
- “구현 존재”가 아니라 “반복 실행 시 동일 규칙/근거로 성능 판단 가능” 상태를 완료 기준으로 둔다.

---

## 1) Phase 3 목표 / 완료 조건

### 목표
1. LSTM 결과를 기준선(최소 naive, moving average)과 자동 비교 가능하게 만든다.
2. 동일 설정 재실행 시 결과 편차를 관리할 수 있도록 재현성 계약(seed + metadata + 환경)을 고정한다.
3. Gate(Architect/Coder/Reviewer/Tester) 기반으로 완료 선언 품질을 강제한다.

### Phase 3 Done 조건(요약)
- [ ] Phase 3 WBS P3-01~P3-10 전부 `DN`
- [ ] Gate A/Coder/Reviewer/Tester 전부 `PASS`
- [ ] Completion Declaration의 Blocker 0건(또는 승인된 예외만 존재)

---

## 2) WBS (작업분해), 담당(role), 의존성, 상태

> 상태 정의: `NS(미착수) / IP(진행중) / RD(검토대기) / DN(완료)`

| WBS ID | 작업 | 담당(Role) | 선행 의존성 | 산출물 | 상태 | 완료 체크리스트 |
|---|---|---|---|---|---|---|
| P3-01 | Phase 3 계약 고정(기준선 정의/재현성 요구/제외범위) | A(Architect) | Phase2 종료 | 본 문서 1~4장 | IP | [x] 목표 정의 [x] 범위 명시 [ ] 수치 PASS 기준 확정 |
| P3-02 | Baseline 지표 함수 구현(naive/moving average) | Coder | P3-01 | `src/training/baselines.py` | DN | [x] MAE/RMSE/MAPE/R2 출력 [x] 입력 shape 검증 [x] 예외 처리 |
| P3-03 | 모델 vs baseline 비교 리포트 구조 확정 | Coder | P3-02 | `artifacts/reports/{run_id}.md` 확장 | DN | [x] 모델/기준선 비교표 [x] 개선율 계산 [x] FAIL 정책 문구 |
| P3-04 | runner CLI에 baseline 비교 옵션/출력 통합 | Coder | P3-02, P3-03 | `src/training/runner.py` | DN | [x] 단일 커맨드 비교 실행 [x] run_id 저장 규칙 유지 [x] 종료코드 정책 |
| P3-05 | 재현성 metadata 고정(seed/config/commit/env) | Coder | P3-01 | metrics/config/report metadata 확장 | DN | [x] seed 기록 [x] commit hash 기록 [x] python/pkg 버전 기록 |
| P3-06 | baseline 비교 단위/계약 테스트 추가 | Tester | P3-02~P3-04 | `tests/test_baseline_contract.py` | DN | [x] naive/moving 계산 검증 [x] 비교표 키 계약 [x] 경계값 검증 |
| P3-07 | 재현성 회귀 테스트 추가(동일 seed 반복 검증) | Tester | P3-05 | `tests/test_phase3_repro_baseline.py`, `tests/test_run_metadata_schema.py` | DN | [x] 동일 조건 반복 편차 기준 [x] metadata 필수 필드 검증 |
| P3-08 | E2E 실험 2회 실행(동일 seed/설정) 및 비교 근거 확보 | Tester | P3-04~P3-07 | metrics/report 2세트 + 실행 로그 | NS | [ ] baseline 비교 PASS/FAIL 기록 [ ] 편차 기준 충족 |
| P3-09 | 리뷰 게이트(정책/품질/회귀) 최종 판정 | Reviewer | P3-06~P3-08 | `docs/PHASE3_REVIEW*.md` | NS | [ ] Must fix 0 [ ] 정책 위반 0 [ ] Gate C PASS |
| P3-10 | Gate 통합 판정 + Completion Declaration 갱신 | PM(메인) | P3-09 | 본 문서 5~6장 | NS | [ ] Gate 4종 PASS [ ] blocker 0 [ ] 완료 선언 |

---

## 3) 의존성 맵 (Execution Dependency)

```text
P3-01
 ├─> P3-02 ─> P3-03 ─> P3-04 ─┐
 └─> P3-05 ───────────────────┼─> P3-07
P3-02~P3-04 ─> P3-06 ─────────┤
P3-04~P3-07 ─> P3-08 ─> P3-09 ─> P3-10
```

### 크리티컬 패스
- **P3-02 → P3-04 → P3-06 → P3-08 → P3-09 → P3-10**
- 사유: 기준선 비교 로직/테스트/E2E 근거가 없으면 Gate 종료 자체가 불가

---

## 4) Gate 판정 기준 및 현재 판정

## 4.1 Gate A (Architect)
**PASS 기준**
- [x] 기준선 범위(naive, moving average) 정의
- [x] 재현성 요구(seed/metadata/env) 정의
- [ ] baseline 우위 판단 기준(예: MAE 개선율 최소치) 수치 확정

**현재 판정: `PENDING`**
- 근거: 범위 정의는 완료, 수치적 합격선 미확정

## 4.2 Gate Coder
**PASS 기준**
- [ ] baseline 계산/비교 구현 완료
- [ ] runner CLI 비교 실행 통합
- [ ] 재현성 metadata 저장 구현 완료

**현재 판정: `NS`**
- 근거: Phase 3 전용 구현 증빙 없음

## 4.3 Gate Reviewer
**PASS 기준**
- [ ] Must fix 0
- [ ] 정책 위반(기준선 누락/재현성 누락) 0
- [ ] 코드-테스트-문서 계약 일치

**현재 판정: `NS`**
- 근거: Phase 3 코드/테스트/리뷰 문서 미생성

## 4.4 Gate Tester
**PASS 기준**
- [ ] 자동화 테스트 통과(Phase 3 테스트 포함)
- [ ] 동일 seed/설정 반복 실행 2회에서 편차 기준 충족
- [ ] baseline 비교 리포트(run_id 단위) 근거 확보

**현재 판정: `PENDING`**
- 근거: 현재 전체 테스트는 통과하나(27 passed, 2 skipped), Phase 3 검증 항목 자체가 아직 없음

## 4.5 통합 Gate 판정
- A: PENDING
- Coder: NS
- Reviewer: NS
- Tester: PENDING

➡ **통합 판정: `NOT STARTED ~ IN PROGRESS (미완료)`**

---

## 5) 실행 계획 (남은 작업 중심)

### 즉시 실행 TODO (P0)
1. **P3-01 확정**: baseline PASS 기준 수치 합의
   - 예시: test MAE 기준 `LSTM <= naive`, `LSTM <= moving_average`
2. **P3-02~P3-04 구현 착수**: baseline 계산 + runner 통합 + report 비교표
3. **P3-06~P3-07 테스트 작성**: 계산 정확도 + 재현성 metadata 계약 검증
4. **P3-08 실행**: 동일 seed/설정 2회 실행 증빙 확보
5. **P3-09 리뷰** 후 **P3-10 Gate 통합 종료**

### 차순위 TODO (P1)
- README에 Phase 3 실행 커맨드/판정 기준 추가
- CI에 Phase 3 스모크(짧은 synthetic baseline compare) 추가

---

## 6) Completion Declaration

- Phase: **Phase 3 (기준선 비교 + 재현성 고정)**
- 현재 완료 여부: **미완료 (IN PROGRESS)**
- Gate 상태:
  - A(Architect): `PENDING`
  - Coder: `NS`
  - Reviewer: `NS`
  - Tester: `PENDING`

### 현재 Blocker
1. baseline 비교 로직/리포트/테스트 미구현
2. 재현성 metadata 계약(커밋/환경 포함) 미고정
3. 동일 seed 반복 실행 기반 실증 데이터 미확보

### 완료 선언 체크리스트
- [ ] P3-01 ~ P3-10 `DN`
- [ ] Gate A/Coder/Reviewer/Tester 모두 `PASS`
- [ ] baseline 대비 성능 판단 근거(report + metrics) 링크 기록
- [ ] 재현성 2회 실행 근거(명령/로그/아티팩트) 기록
- [ ] Blocker 0건(또는 승인된 예외만 존재)

> 위 조건 충족 시 본 섹션을 `완료 (DONE)`로 변경하고, 승인자/완료일/근거 경로를 고정 기록한다.

---

## 7) PM 요약
- 현재 저장소는 Phase 2 안정화 상태(테스트 27 passed, 2 skipped)이며, **Phase 3 핵심인 baseline 비교/재현성 고정은 본격 착수 전**이다.
- 따라서 Phase 3 완료 선언은 불가하며, 다음 핵심은 **기준선 비교 계약 확정(P3-01) → 구현/테스트(P3-02~P3-07) → 2회 재현 실험(P3-08)** 순으로 진행하는 것이다.
- PM 관점에서 최우선 리스크는 “수치 PASS 기준 미정으로 Gate 판단이 흔들리는 것”이며, 이를 먼저 고정해야 일정 지연을 막을 수 있다.

---

## 8) Implementation Update (2026-02-20)

Phase 3 계약 정합성 보강 반영:
- runner baseline MA 창 크기 옵션 추가: `--ma-window` (기본: sequence_length)
- deterministic 실행 토글 추가: `--deterministic/--no-deterministic`
- run metadata 저장 토글 추가: `--save-run-meta/--no-save-run-meta`
- Phase 3 run metadata 스키마 파일 추가 저장:
  - `artifacts/runs/{run_id}.meta.json`
  - `schema_version = phase3.runmeta.v1`
  - seed/deterministic/split_index/config/git/runtime/artifacts/status 포함
- baseline 리포트에 Phase 3 계약 키(`metrics.model/baseline/delta_vs_baseline`) 추가

추가 테스트:
- `tests/test_baseline_contract.py`
- `tests/test_run_metadata_schema.py`
