# GUI_PHASE3_PM_TRACKER

> **HISTORICAL NOTE (문서 정합성):** 이 문서는 해당 시점의 진행 스냅샷입니다. 현재 운영/실행 계약의 단일 기준은 `docs/RUNBOOK.md`와 최신 ARCH/FINAL/CLOSEOUT 문서입니다.
> 경로/CLI/게이트 상태가 본문과 다를 수 있으며, 운영 판단 시 현재 기준 문서를 우선합니다.


## Standard Handoff Format

### 1) 요청/목표
- 프로젝트: `~/spline-lstm`
- 역할: Project Manager (PM)
- 목표: **GUI Phase 3(실연동 안정화 + UX 개선)** 실행 추적 및 Gate 기반 완료 판정 기준선 수립
- 필수 포함 범위:
  - WBS / 의존성 / 상태
  - Gate 기준
  - Completion Declaration

---

### 2) Phase 3 범위 정의 (실연동 안정화 + UX 개선)

#### 2-1. In-Scope
1. 실백엔드 연동 경로의 오류/예외 처리 강화(타임아웃, 네트워크 단절, 서버 오류)
2. RunJob 실행/종료/재시도 UX 개선(상태 가시성, 사용자 안내 문구)
3. 결과 비교 UX 도입(최근 실행 간 핵심 지표 비교)
4. 로그 가시성 고도화(필터/검색/레벨/자동 스크롤 정책)
5. Phase 3 기능/회귀 테스트 확장 및 증빙 문서화

#### 2-2. Out-of-Scope
- 대규모 성능 튜닝(렌더/메모리 최적화 전면 작업) — Phase 4
- 파일럿/배포 운영체계 확정 — Phase 5
- 인증/권한 모델 고도화

---

### 3) WBS / 의존성 / 상태

> 상태 정의: `NS(미착수) / IP(진행중) / RD(검토대기) / DN(완료) / BLK(차단)`

| WBS ID | 작업 항목 | 선행 의존성 | 산출물/근거 | 상태 | 오너 |
|---|---|---|---|---|---|
| GUI-P3-01 | Phase3 범위/성공지표 기준선 확정 | Phase2 Exit PASS | 본 문서, `docs/GUI_PHASE_PLAN.md` 정합 확인 | IP | PM |
| GUI-P3-02 | Entry Gate 점검 (Phase2 PASS 증빙 수합) | GUI-P3-01 | `docs/GUI_PHASE2_FINAL.md`, Gate 판정 기록 | BLK | PM |
| GUI-P3-03 | 오류 분류 체계/에러코드 UX 매핑 확정 | GUI-P3-02 | 오류 매트릭스, UI 카피 가이드 | NS | Architect + FE/BE |
| GUI-P3-04 | 실연동 안정화 구현 (retry/timeout/fallback) | GUI-P3-03 | API client/상태머신/복구 경로 코드 | NS | Coder |
| GUI-P3-05 | RunJob UX 개선(로딩/실패/재시도/완료 안내) | GUI-P3-03~04 | `ui/src/pages/RunJobPage.tsx` 변경 및 캡처 | NS | FE/Coder |
| GUI-P3-06 | 결과 비교 UI(최근 실행 기준 diff) 구현 | GUI-P3-04 | 결과 비교 컴포넌트/데이터 매핑 | NS | FE/Coder |
| GUI-P3-07 | 로그 필터/검색/표시 개선 | GUI-P3-04 | 로그 패널 기능 증빙(필터/검색) | NS | FE/Coder |
| GUI-P3-08 | 통합 테스트 확장(정상/실패/복구 경로) | GUI-P3-05~07 | `docs/GUI_PHASE3_TEST_RESULTS.md` | NS | Tester |
| GUI-P3-09 | 리뷰 Gate(정합성/Must-fix) | GUI-P3-08 | `docs/GUI_PHASE3_REVIEW_GATE_FINAL.md` | NS | Reviewer |
| GUI-P3-10 | PM 통합 Gate 및 Phase3 종료 선언 | GUI-P3-09 | 본 문서 6장 Completion 갱신 | NS | PM |

#### 3-1. 현재 의존성 체인 요약
- 핵심 경로(Critical Path): `GUI-P3-02 → 03 → 04 → 05/06/07 → 08 → 09 → 10`
- 병렬 가능:
  - `GUI-P3-05/06/07`은 `GUI-P3-04` 이후 병렬 추진 가능
- 현재 Blocker:
  - **Phase2 Exit PASS 미확정 상태**에서 Phase3 Entry Gate 잠금

#### 3-2. 현재 상태 스냅샷 (기준일: 2026-02-18)
- 확인 근거: `docs/GUI_PHASE2_FINAL.md`
  - Phase2 최종 판정: **NOT DONE**
  - 사유: Reviewer 최종본/트래커 동기화 미완료
- PM 판정:
  - Phase3는 **준비 단계(IN PROGRESS)**
  - 실행 Gate 관점 상태는 **ENTRY BLOCKED**

---

### 4) Gate 기준 (Phase 3)

#### 4-1. Entry Gate
**PASS 기준**
- [ ] Phase2 최종 상태가 DONE으로 확정
- [ ] Phase2 잔여 Must-fix 0건 또는 승인된 예외 문서화
- [ ] Phase3 우선순위 백로그(안정화/UX) 확정

**FAIL 트리거**
- Phase2 Gate 미종결 상태에서 Phase3 구현 착수

현재 판정: **BLOCKED**

#### 4-2. Architect Gate
**PASS 기준**
- [ ] 오류 분류 체계(네트워크/서버/검증/실행)와 UX 문구 정책 확정
- [ ] 결과 비교 데이터 계약(입력/출력 필드) 확정
- [ ] 로그 필터/검색 정책(레벨/키워드/시간) 확정

**FAIL 트리거**
- API/화면 계약 불일치로 구현 재작업 발생

현재 판정: **PENDING**

#### 4-3. Coder Gate
**PASS 기준**
- [ ] 타임아웃/네트워크 오류 재시도 및 실패 복구 경로 동작
- [ ] 결과 비교 UI 동작(최소 2개 실행 비교)
- [ ] 로그 필터/검색 기능 정상 동작
- [ ] 핵심 플로우에서 무한 로딩/상태 불일치 0건

**FAIL 트리거**
- 복구 불가 실패 상태 잔존, 또는 상태머신 terminal 미도달

현재 판정: **PENDING**

#### 4-4. Reviewer Gate
**PASS 기준**
- [ ] Must-fix 0건
- [ ] 코드/문서/테스트 증빙 정합
- [ ] Phase4 이관 기술부채 목록 정리

**FAIL 트리거**
- Must-fix 1건 이상

현재 판정: **PENDING**

#### 4-5. Tester Gate
**PASS 기준**
- [ ] 기능 테스트 PASS율 95%+
- [ ] 실패/복구 시나리오 재현 가능 PASS
- [ ] 결과 비교/로그 필터 회귀 테스트 통과

**FAIL 트리거**
- 핵심 시나리오 재현 불가 또는 회귀 결함 재발

현재 판정: **PENDING**

#### 4-6. PM 통합 Gate 규칙
- 최종 완료 조건: `Entry PASS + Architect PASS + Coder PASS + Reviewer PASS + Tester PASS`
- `BLOCKED / PENDING / CONDITIONAL` 존재 시 상태는 `IN PROGRESS`

---

### 5) 리스크 / 이슈 / 대응

| ID | 리스크/이슈 | 영향 | 대응 계획 | 담당 | 상태 |
|---|---|---|---|---|---|
| R-GUI3-01 | Phase2 미종결 장기화 | Phase3 착수 지연 | Phase2 잔여 증빙(리뷰 최종본/트래커 동기화) 우선 종결 | PM + Reviewer | Open |
| R-GUI3-02 | 오류코드/문구 불일치 | 사용자 혼란, 지원 비용 증가 | 오류 코드 사전 + UI 카피 단일 소스화 | Architect + FE | Open |
| R-GUI3-03 | 로그 기능 확장에 따른 성능 저하 | UI 응답성 저하 | 기본 필터/limit 강제, 고급 최적화는 Phase4 분리 | FE | Open |
| R-GUI3-04 | 비교 지표 정의 불명확 | 결과 비교 신뢰성 저하 | 핵심 KPI 3~5개 우선 확정 후 범위 고정 | PM + Architect | Open |

---

### 6) 완료 선언 (Completion Declaration)

#### 6-1. 선언 템플릿
- Phase: GUI Phase 3 (실연동 안정화 + UX 개선)
- 상태: `DONE` 또는 `IN PROGRESS`
- 완료일: `YYYY-MM-DD`
- 승인자: PM / Architect / Reviewer / Tester
- 근거:
  - 안정화/UX 구현 코드 링크
  - 테스트 결과 문서
  - 리뷰 Gate 문서

#### 6-2. 현재 판정 (기준일: 2026-02-18)
- Phase: **GUI Phase 3 (실연동 안정화 + UX 개선)**
- 현재 상태: **IN PROGRESS (ENTRY BLOCKED)**
- Gate 상태:
  - Entry: **BLOCKED**
  - Architect: **PENDING**
  - Coder: **PENDING**
  - Reviewer: **PENDING**
  - Tester: **PENDING**

#### 6-3. DONE 전환 조건 (체크리스트)
- [ ] Entry Gate PASS(Phase2 DONE 확정)
- [ ] 오류/복구 UX 및 상태흐름 안정화 구현 완료
- [ ] 결과 비교 + 로그 필터/검색 기능 구현 완료
- [ ] 테스트 PASS율 95%+ 달성 및 리포트 확정
- [ ] Reviewer Must-fix 0건 및 PM 최종 승인

---

### 7) 다음 액션 (48~72시간 우선순위)
1. **PM/Reviewer**: Phase2 Reviewer 최종본 및 PM Tracker 동기화 완료 후 Phase2 DONE 재판정 (P1)
2. **Architect**: Phase3 오류 분류/문구/비교 지표 계약 초안 작성 (P1)
3. **Coder(FE/BE)**: retry/timeout/fallback 구현 설계 스파이크 및 작업 분할 (P1)
4. **Tester**: 정상/실패/복구/비교/로그 필터 시나리오 템플릿 선작성 (`docs/GUI_PHASE3_TEST_RESULTS.md` 초안) (P2)
5. **PM**: Gate 점검 리듬(화/금)으로 WBS 상태 업데이트 운영 시작 (P2)
