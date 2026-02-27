# GUI_PHASE1_PM_TRACKER

> **HISTORICAL NOTE (문서 정합성):** 이 문서는 해당 시점의 진행 스냅샷입니다. 현재 운영/실행 계약의 단일 기준은 `docs/RUNBOOK.md`와 최신 ARCH/FINAL/CLOSEOUT 문서입니다.
> 경로/CLI/게이트 상태가 본문과 다를 수 있으며, 운영 판단 시 현재 기준 문서를 우선합니다.


## Standard Handoff Format

### 1) 요청/목표
- 프로젝트: `~/spline-lstm`
- 역할: Project Manager (PM)
- 목표: **GUI Phase 1(기초 골격)** 실행 상태를 추적하고, Gate 기반 완료 판정을 가능하게 하는 관리 기준선 확정
- 필수 포함 범위:
  - WBS / 의존성 / 상태
  - Gate 기준
  - 완료 선언(Completion Declaration)

---

### 2) Phase 1 범위 정의 (기초 골격)

#### 2-1. In-Scope
1. UI 기본 골격(탭/페이지 구조) 확정
2. API 클라이언트 호출 슬롯 정의(미연결 시 mock 폴백 포함)
3. 최소 3개 화면(Dashboard / Run Job / Results) 연결
4. 개발 실행 가이드 문서화(`docs/GUI_QUICKSTART.md`)
5. Phase 2(실백엔드 연동)로 넘길 준비 상태 명시

#### 2-2. Out-of-Scope
- FastAPI 실구현/배포
- 인증/권한
- 고급 접근성/성능 최적화 완료
- E2E 자동화 완성

---

### 3) WBS / 의존성 / 상태

> 상태 정의: `NS(미착수) / IP(진행중) / RD(검토대기) / DN(완료) / BLK(차단)`

| WBS ID | 작업 항목 | 선행 의존성 | 산출물/근거 | 상태 | 오너 |
|---|---|---|---|---|---|
| GUI-P1-01 | Phase 1 범위/목표 고정 | 없음 | `docs/GUI_PRODUCT_PLAN.md`, `docs/GUI_ARCHITECTURE.md` | DN | PM/Architect |
| GUI-P1-02 | UI 프로젝트 부트스트랩(Vite+TS) | GUI-P1-01 | `ui/package.json`, `ui/src/main.tsx` | DN | Coder |
| GUI-P1-03 | 기본 내비게이션/탭 구조 구현 | GUI-P1-02 | `ui/src/App.tsx` | DN | Coder |
| GUI-P1-04 | Dashboard/Run/Results 페이지 골격 구현 | GUI-P1-03 | `ui/src/pages/*.tsx` | DN | Coder |
| GUI-P1-05 | API 클라이언트 계약 슬롯/Mock 폴백 구현 | GUI-P1-04 | `ui/src/api/client.ts` | DN | Coder |
| GUI-P1-06 | 기본 스타일/반응형 최소 적용 | GUI-P1-03 | `ui/src/styles.css` | IP | Coder |
| GUI-P1-07 | 로컬 실행 문서화(Quickstart) | GUI-P1-02~05 | `docs/GUI_QUICKSTART.md` | DN | PM/Coder |
| GUI-P1-08 | 테스트 체크리스트 초안(수동 검증 기준) | GUI-P1-01~07 | `docs/GUI_TEST_CHECKLIST.md` | DN | Tester |
| GUI-P1-09 | Phase 1 산출물 리뷰 및 결함 정리 | GUI-P1-06~08 | 리뷰 코멘트/수정 목록 | RD | Reviewer |
| GUI-P1-10 | PM 게이트 판정 및 종료 선언 | GUI-P1-09 | 본 문서 6장 완료 선언 갱신 | IP | PM |

#### 3-1. 현재 의존성 체인 요약
- 핵심 경로(Critical Path): `GUI-P1-06 → GUI-P1-09 → GUI-P1-10`
- 차단 가능 지점:
  - 반응형/스타일 미완료 시 Reviewer Gate 보류
  - 리뷰 Critical 이슈 잔존 시 PM 종료 선언 불가

---

### 4) Gate 기준 (Phase 1)

#### 4-1. Architect Gate
**PASS 기준**
- [x] Phase 1 범위(In/Out) 문서화
- [x] UI-API 계약 방향(슬롯 중심) 정의
- [x] Phase 2 연계 포인트 명시

**FAIL 트리거**
- 문서 간 범위/용어 불일치로 구현 기준이 모호한 경우

현재 판정: **PASS**

#### 4-2. Coder Gate
**PASS 기준**
- [x] `ui/` 실행 가능한 골격 확보
- [x] 3개 핵심 페이지 접근 가능
- [x] API 미연결 환경에서 mock 폴백 동작
- [ ] 반응형/스타일 최소 기준 충족 확인(추가 보강 필요)

**FAIL 트리거**
- 페이지 전환 불가/런타임 오류로 기본 플로우 중단

현재 판정: **CONDITIONAL PASS (스타일/반응형 보강 후 확정)**

#### 4-3. Reviewer Gate
**PASS 기준**
- [ ] 코드/문서 일치성 검토 완료
- [ ] Critical/Major 이슈 0건
- [ ] Phase 2 착수 가능한 기술부채 목록 정리

**FAIL 트리거**
- Critical/Major 이슈 잔존

현재 판정: **PENDING**

#### 4-4. Tester Gate
**PASS 기준**
- [x] 테스트 체크리스트 문서 존재
- [ ] 모바일/태블릿/노트북 핵심 플로우 수동 점검 완료
- [ ] 실행 실패/복구 UX 확인

**FAIL 트리거**
- 핵심 플로우(FLOW-01~05) 중 재현성 있는 실패 존재

현재 판정: **PENDING**

#### 4-5. PM 통합 Gate 규칙
- 최종 완료 조건: `Architect PASS` + `Coder PASS` + `Reviewer PASS` + `Tester PASS`
- 조건부 상태(`CONDITIONAL PASS`, `PENDING`)가 1개라도 있으면 Phase 1은 `IN PROGRESS`

---

### 5) 리스크 / 이슈 / 대응

| ID | 리스크/이슈 | 영향 | 대응 계획 | 담당 | 상태 |
|---|---|---|---|---|---|
| R-GUI-01 | 백엔드 실연동 미구현 | 실제 실행 검증 지연 | Phase 2 API 서버 골격 우선 착수 | BE/Coder | Open |
| R-GUI-02 | 반응형 기준 미확정/미검증 | 모바일 UX 저하 | 체크리스트 기반 수동 검증 + CSS 보강 | FE/Tester | Open |
| R-GUI-03 | Mock 응답과 실제 API 스키마 차이 가능성 | 통합 시 회귀 발생 | API 계약서 고정 후 타입 동기화 | Architect/FE/BE | Open |

---

### 6) 완료 선언 (Completion Declaration)

#### 6-1. 선언 템플릿
- Phase: GUI Phase 1 (기초 골격)
- 상태: `DONE` 또는 `IN PROGRESS`
- 완료일: `YYYY-MM-DD`
- 승인자: PM / Architect / Reviewer / Tester
- 근거:
  - 코드/문서 링크
  - 테스트 로그/체크리스트 결과

#### 6-2. 현재 판정 (기준일: 2026-02-18)
- Phase: **GUI Phase 1 (기초 골격)**
- 현재 상태: **IN PROGRESS**
- Gate 상태:
  - Architect: **PASS**
  - Coder: **CONDITIONAL PASS**
  - Reviewer: **PENDING**
  - Tester: **PENDING**

#### 6-3. DONE 전환 조건 (체크리스트)
- [ ] `GUI-P1-06` 반응형/스타일 최소 기준 충족
- [ ] Reviewer Gate PASS (Critical/Major 0)
- [ ] Tester Gate PASS (핵심 플로우 점검 완료)
- [ ] PM 최종 승인 및 본 섹션 상태 `DONE` 갱신

---

### 7) 다음 액션 (실행 우선순위)
1. **FE**: `ui/src/styles.css` 기준 반응형 최소 보강 완료 (P1)
2. **Reviewer**: 코드/문서 정합성 리뷰 및 결함 리스트 확정 (P1)
3. **Tester**: `docs/GUI_TEST_CHECKLIST.md` 기준 수동 검증 수행 (P1)
4. **PM**: Gate 4종 판정 집계 후 종료 선언 갱신 (P1)
