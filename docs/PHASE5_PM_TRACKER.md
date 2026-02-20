# PHASE 5 PM TRACKER (확장 옵션 운영/진행 관리 최종)

> **HISTORICAL NOTE (문서 정합성):** 이 문서는 해당 시점의 진행 스냅샷입니다. 현재 운영/실행 계약의 단일 기준은 `docs/RUNBOOK.md`와 최신 ARCH/FINAL/CLOSEOUT 문서입니다.
> 경로/CLI/게이트 상태가 본문과 다를 수 있으며, 운영 판단 시 현재 기준 문서를 우선합니다.


## Standard Handoff Format

### 1) 요청/목표
- 역할: PM (운영/진행 관리)
- 프로젝트: `~/spline-lstm`
- 목표: **Phase 5(확장 옵션) 진행 관리 + 최종 종료 판정**
- 산출물 범위:
  1. WBS/의존성/Gate(Architect·Coder·Reviewer·Tester) 통합 관리
  2. Completion Declaration(종료 선언)
  3. Phase5 종료 요약 + 후속 백로그 제시

기준 근거 문서:
- `docs/BLUEPRINT.md` (Week5~6 옵션 스코프)
- `docs/PHASE4_PM_GATE_FINAL_2.md` (이전 최종 문서)
- `docs/TEST_RESULTS_PHASE4_FIXPASS2.md` (Phase4 재검증 PASS)
- `README.md`, `src/models/lstm.py` (현재 구현 범위 확인)

---

### 2) Phase 5 범위 정의 (옵션 확장)
Blueprint 기준 Phase 5 확장 스코프:
1. GRU/Attention-LSTM 프로토타입 비교
2. multivariate 입력 파이프라인 초안
3. covariates(외생변수) 통합
4. edge 배포 후보(ONNX/TFLite) 벤치마크

PM 기준 완료 조건(Phase 5 Exit):
- [ ] 확장 기능 코드 + 실행 경로 + 문서가 일치
- [ ] 비교/벤치 결과가 `run_id` 기반 artifact로 재현 가능
- [ ] Gate A/Coder/Reviewer/Tester 전원 PASS
- [ ] Completion Blocker 0건

---

### 3) WBS / 의존성 / 상태
> 상태: `NS(미착수) / IP(진행중) / DN(완료) / BLK(블로커)`

| WBS ID | 작업 | 담당(Role) | 선행 의존성 | 핵심 산출물 | 상태 |
|---|---|---|---|---|---|
| P5-01 | Phase5 확장 계약(범위/DoD/지표) 고정 | Architect/PM | Phase4 PASS | `docs/PHASE5_ARCH.md` (신규 필요) | NS |
| P5-02 | GRU 모델 구현(학습/추론/저장 계약 포함) | Coder | P5-01 | `src/models/*`, 테스트 | NS |
| P5-03 | Attention-LSTM 비교 실험 자동화(run_id) | Coder | P5-01 | metrics/report artifact | NS |
| P5-04 | multivariate 입력 스키마 + 전처리 파이프라인 | Coder | P5-01 | `src/preprocessing/*`, schema 테스트 | NS |
| P5-05 | covariates 통합(캘린더/외부요인) | Coder | P5-04 | feature 계약 + 검증 테스트 | NS |
| P5-06 | edge 후보 변환/벤치(ONNX/TFLite) | Coder | P5-02~P5-05 | latency/memory/metric 리포트 | NS |
| P5-07 | 확장 기능 회귀/품질 리뷰 | Reviewer | P5-02~P5-06 | `docs/PHASE5_REVIEW.md` (신규 필요) | NS |
| P5-08 | 확장 기능 E2E/성능 검증 | Tester | P5-02~P5-07 | `docs/TEST_RESULTS_PHASE5*.md` (신규 필요) | NS |
| P5-09 | PM 통합 Gate 판정 + 종료 선언 | PM | P5-01~P5-08 | 본 문서 5~6장 | IP |

요약:
- DN: 0
- IP: 1 (PM 통합 판정 문서화 진행)
- NS: 8
- BLK: 0

---

### 4) Gate 판정 (현재 시점)

#### 4.1 Entry Gate (Phase4 선행조건)
- 상태: **PASS**
- 근거: `docs/TEST_RESULTS_PHASE4_FIXPASS2.md`에서 Phase4 최종 PASS 확인
- 판단: Phase5 착수 가능 상태

#### 4.2 Gate A — Architect
- 상태: **FAIL (미충족)**
- 사유: Phase5 전용 아키텍처/계약 문서(`PHASE5_ARCH.md`) 부재

#### 4.3 Gate Coder
- 상태: **FAIL (미충족)**
- 사유:
  - GRU 구현 증빙 미확인
  - multivariate/covariates/edge 벤치 실행 경로 미구축

#### 4.4 Gate Reviewer
- 상태: **FAIL (미충족)**
- 사유: Phase5 리뷰 산출물 부재 (`docs/PHASE5_REVIEW*.md` 없음)

#### 4.5 Gate Tester
- 상태: **FAIL (미충족)**
- 사유: Phase5 테스트/벤치 결과 문서 부재 (`docs/TEST_RESULTS_PHASE5*.md` 없음)

#### 4.6 통합 Gate 판정
- **FAIL (All PASS 미충족)**
- 결론: 착수 가능(Entry PASS)이지만 **종료 조건은 전혀 충족되지 않음**

---

### 5) Completion Declaration (최종 종료 판정)
- Phase: **Phase 5 (확장 옵션)**
- 최종 선언: **NOT DONE / 종료 불가**

Blocker:
1. 확장 스코프 핵심 산출물(설계/구현/리뷰/테스트) 미생성
2. Gate A/Coder/Reviewer/Tester 전원 FAIL
3. 확장 DoD(비교표, multivariate+covariates 계약, edge PoC) 미충족

Exit Criteria (종료 재판정 조건):
- [ ] `docs/PHASE5_ARCH.md` 작성 및 승인
- [ ] GRU + Attention 비교 실험 run_id artifact 확보
- [ ] multivariate/covariates 파이프라인 및 테스트 PASS
- [ ] ONNX/TFLite 변환 및 지연/메모리/정확도 벤치 리포트 확보
- [ ] Reviewer/Tester 문서 PASS 반영
- [ ] PM 통합 Gate All PASS 갱신

---

### 6) Phase5 종료 요약 (PM)
- Phase4는 FixPass2 기준으로 종료 가능 상태에 도달하여 **Phase5 진입 권한은 확보**됨.
- 그러나 현재 저장소 기준 Phase5 확장 작업은 **실행 증빙이 없는 미착수 상태**에 가깝다.
- 따라서 PM 최종 판정은 **Phase5 종료 불가(NOT DONE)** 이며, 본 단계는 완료 선언 대신 **백로그 전환 후 재착수 관리**가 적절하다.

---

### 7) 후속 백로그 (실행 중심, 우선순위)

#### P0 (즉시 착수)
1. `PHASE5_ARCH.md` 작성: 확장 계약(입력 스키마, 성능 기준, 실패 기준) 고정
2. GRU 모델 추가 + 기존 러너 호환(체크포인트/metrics/report 계약 유지)
3. 실험 매트릭스 정의: LSTM vs GRU vs Attention (동일 데이터/동일 split)

#### P1 (핵심 확장)
4. multivariate 스키마/검증기 도입 (`target + feature columns` 계약)
5. covariates 통합(캘린더/외부요인) 및 누수 방지 테스트 추가
6. 확장 smoke 스크립트(`scripts/smoke_test_phase5.sh`) 신설

#### P2 (옵션 고도화)
7. ONNX/TFLite 변환 파이프라인 PoC
8. edge 벤치 리포트(지연/메모리/정확도 trade-off)
9. README/RUNBOOK에 확장 실행 경로 문서화

재오픈 트리거(Backlog → Active):
- 리소스(개발/테스트) 할당 + P0 항목 owner 지정 완료 시

---

### 8) PM 핸드오프 메모
- 현 시점 권장 운영 결정: **Phase5를 “종료”가 아닌 “보류/백로그 관리 상태”로 잠정 종료**
- 다음 판정 이벤트: P0 완료 후 중간 Gate 리뷰(Architect/Coder) 1회, 이후 Reviewer/Tester 순으로 종료 심사 진행
- 본 문서는 Phase5의 기준선(관리 문서)이며, 구현 증빙이 추가되면 상태(NS/IP/DN, Gate)를 즉시 갱신한다.
