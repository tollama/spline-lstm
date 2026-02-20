# GUI_PHASE2_PM_TRACKER

> **HISTORICAL NOTE (문서 정합성):** 이 문서는 해당 시점의 진행 스냅샷입니다. 현재 운영/실행 계약의 단일 기준은 `docs/RUNBOOK.md`와 최신 ARCH/FINAL/CLOSEOUT 문서입니다.
> 경로/CLI/게이트 상태가 본문과 다를 수 있으며, 운영 판단 시 현재 기준 문서를 우선합니다.


## Standard Handoff Format

### 1) 요청/목표
- 프로젝트: `~/spline-lstm`
- 역할: Project Manager (PM)
- 목표: **GUI Phase 2(백엔드 실연동 + 상태흐름 안정화)** 실행 추적 및 Gate 기반 완료 판정 기준선 확정
- 필수 포함 범위:
  - WBS / 의존성 / 상태
  - Gate 기준
  - Completion Declaration

---

### 2) Phase 2 범위 정의 (백엔드 실연동 + 상태흐름 안정화)

#### 2-1. In-Scope
1. FastAPI 백엔드 골격 구축 및 `/api/v1` 계약 엔드포인트 최소 셋 구현
2. UI(API client)와 백엔드 실연동 (mock opt-in 모드 유지)
3. Run Job 기준 상태흐름 `queued → running → success/fail` 안정화
4. Job 로그 조회/표시 및 실패 메시지 UX 일관화
5. Phase 2 데모 시나리오(최소 3개) 실행 증빙 수집

#### 2-2. Out-of-Scope
- 인증/권한(AuthN/AuthZ) 완성
- WebSocket/SSE 기반 실시간 스트리밍(Phase 3+ 후보)
- 고급 성능 최적화/부하테스트 완성
- 멀티유저/분산 스케줄링

---

### 3) WBS / 의존성 / 상태

> 상태 정의: `NS(미착수) / IP(진행중) / RD(검토대기) / DN(완료) / BLK(차단)`

| WBS ID | 작업 항목 | 선행 의존성 | 산출물/근거 | 상태 | 오너 |
|---|---|---|---|---|---|
| GUI-P2-01 | Phase 2 범위/계약 기준선 고정 | Phase1 Gate PASS | `docs/GUI_PHASE_PLAN.md`, `docs/GUI_ARCHITECTURE.md` | DN | PM/Architect |
| GUI-P2-02 | FastAPI 앱 골격 및 `/api/v1/health` 구현 | GUI-P2-01 | `backend/app/main.py` (또는 동등 경로), 헬스체크 응답 | NS | BE/Coder |
| GUI-P2-03 | 파이프라인 실행 제출 API 구현 (`POST /pipelines/spline-tsfm:run`) | GUI-P2-02 | API 핸들러 + 입력 검증 스키마 | NS | BE/Coder |
| GUI-P2-04 | Job 상태/로그 API 구현 (`/jobs/{id}`, `/jobs/{id}/logs`) | GUI-P2-03 | 상태 저장소/로그 조회 API | NS | BE/Coder |
| GUI-P2-05 | Runner Adapter 연동(subprocess + 상태전이) | GUI-P2-03 | runner 매핑 코드, 상태머신 증빙 | NS | BE/Coder |
| GUI-P2-06 | UI 실연동(환경별 mock/real 전환 포함) | GUI-P2-02~05 | `ui/src/api/client.ts`, `.env` 규칙, 실연동 캡처 | IP | FE/Coder |
| GUI-P2-07 | RunJob 상태흐름 안정화(폴링/종료조건/오류분기) | GUI-P2-06 | `ui/src/pages/RunJobPage.tsx`, 상태/로그 UI | IP | FE/Coder |
| GUI-P2-08 | 통합 시나리오 테스트(최소 3개 E2E 수동) | GUI-P2-06~07 | `docs/GUI_PHASE2_TEST_RESULTS.md` | NS | Tester |
| GUI-P2-09 | 코드/문서 정합성 리뷰 및 Must-fix 정리 | GUI-P2-07~08 | `docs/GUI_PHASE2_REVIEW.md` | NS | Reviewer |
| GUI-P2-10 | PM Gate 집계 및 Phase 2 종료 선언 | GUI-P2-09 | 본 문서 6장 Completion 갱신 | NS | PM |

#### 3-1. 현재 의존성 체인 요약
- 핵심 경로(Critical Path): `GUI-P2-02 → 03 → 05 → 06 → 07 → 08 → 09 → 10`
- 선행 게이트:
  - **Phase1 PASS** 확인 시 Phase2 Entry 유효
- 차단 가능 지점:
  - backend 골격 미존재 시 실연동 테스트 전면 지연
  - 상태 저장소/로그 조회 미완성 시 상태흐름 안정화 검증 불가

#### 3-2. 현재 상태 스냅샷 (기준일: 2026-02-18)
- 확인 사항:
  - Phase1 Gate 문서상 PASS 근거 존재
  - `ui/`는 mock 기반/opt-in 실험 경로 보유
  - `backend/` 실구현 디렉터리/엔드포인트 증빙은 아직 확인되지 않음
- PM 판정:
  - Phase2는 **착수 상태(IN PROGRESS)**
  - 백엔드 실연동 트랙은 **초기 단계(backend WBS NS 중심)**

---

### 4) Gate 기준 (Phase 2)

#### 4-1. Architect Gate
**PASS 기준**
- [x] API 계약(`/api/v1`, job 상태모델, 오류코드) 문서화
- [x] Runner Adapter 구조/상태머신 정의
- [ ] 실제 구현 경로와 문서 매핑표 확정

**FAIL 트리거**
- 계약 문서와 구현 엔드포인트/필드 불일치

현재 판정: **CONDITIONAL PASS**

#### 4-2. Coder Gate
**PASS 기준**
- [ ] FastAPI 실행 가능(health check 정상)
- [ ] run/job/log API 동작
- [ ] UI에서 mock 아닌 real backend 호출 성공
- [ ] RunJob 상태흐름이 terminal 상태까지 안정적으로 종료

**FAIL 트리거**
- 실백엔드 호출 불가 또는 상태 전이 중단/무한 폴링

현재 판정: **PENDING**

#### 4-3. Reviewer Gate
**PASS 기준**
- [ ] Must-fix 0건
- [ ] API 계약/코드/문서 정합성 확보
- [ ] Phase3로 이관할 기술부채 목록 정리

**FAIL 트리거**
- Must-fix 1건 이상 잔존

현재 판정: **PENDING**

#### 4-4. Tester Gate
**PASS 기준**
- [ ] 최소 3개 시나리오 End-to-End 성공
- [ ] 실패 시나리오(의도적 오류 입력)에서 오류 UX/복구 경로 검증
- [ ] 재현 가능한 테스트 리포트 문서화

**FAIL 트리거**
- 핵심 플로우(데이터 선택→실행→결과→로그) 중 재현성 실패 존재

현재 판정: **PENDING**

#### 4-5. PM 통합 Gate 규칙
- 최종 완료 조건: `Architect PASS` + `Coder PASS` + `Reviewer PASS` + `Tester PASS`
- `CONDITIONAL PASS` 또는 `PENDING`이 존재하면 상태는 `IN PROGRESS`

---

### 5) 리스크 / 이슈 / 대응

| ID | 리스크/이슈 | 영향 | 대응 계획 | 담당 | 상태 |
|---|---|---|---|---|---|
| R-GUI2-01 | backend 구현 지연 | 실연동 검증 일정 지연 | WBS 02~05 우선순위 상향, API 최소셋부터 완료 | PM + BE | Open |
| R-GUI2-02 | 상태모델 필드 불일치(`succeeded/failed` vs `success/fail`) | UI 상태표시 오류/회귀 | API→UI 매핑 규칙 단일화, 계약 테스트 추가 | Architect + FE/BE | Open |
| R-GUI2-03 | 로그량 증가로 UI 렌더 지연 | 사용자 체감 성능 저하 | 로그 limit/paging 기본값 강제, 가상화는 Phase3 후보 | FE + BE | Open |
| R-GUI2-04 | 문서/코드 업데이트 타이밍 불일치 | 리뷰/테스트 반복 비용 증가 | PR 템플릿에 문서 동기화 체크 항목 추가 | PM + Reviewer | Open |

---

### 6) 완료 선언 (Completion Declaration)

#### 6-1. 선언 템플릿
- Phase: GUI Phase 2 (백엔드 실연동 + 상태흐름 안정화)
- 상태: `DONE` 또는 `IN PROGRESS`
- 완료일: `YYYY-MM-DD`
- 승인자: PM / Architect / Reviewer / Tester
- 근거:
  - 코드 링크(백엔드/API/UI)
  - 테스트 결과 문서
  - 리뷰 Gate 문서

#### 6-2. 현재 판정 (기준일: 2026-02-18)
- Phase: **GUI Phase 2 (백엔드 실연동 + 상태흐름 안정화)**
- 현재 상태: **IN PROGRESS**
- Gate 상태:
  - Architect: **CONDITIONAL PASS**
  - Coder: **PENDING**
  - Reviewer: **PENDING**
  - Tester: **PENDING**

#### 6-3. DONE 전환 조건 (체크리스트)
- [ ] `GUI-P2-02~05` 백엔드 최소 API + Runner Adapter 구현 완료
- [ ] `GUI-P2-06~07` UI 실연동 및 상태흐름 안정화 완료
- [ ] `GUI-P2-08` 통합 테스트 리포트 PASS 확보
- [ ] `GUI-P2-09` Reviewer Must-fix 0건
- [ ] PM 최종 승인 및 본 섹션 상태 `DONE` 갱신

---

### 7) 다음 액션 (48~72시간 우선순위)
1. **BE/Coder**: FastAPI skeleton + `/api/v1/health` + run/job/log 최소 API 구현 (P1)
2. **FE/Coder**: UI 환경변수 기준 실백엔드 연결 스위치 정리 및 오류 UX 정합화 (P1)
3. **Tester**: Phase2 통합 시나리오 3종 테스트 케이스 초안 작성 (`docs/GUI_PHASE2_TEST_RESULTS.md` 템플릿) (P1)
4. **Reviewer**: 계약-구현 매핑 체크리스트 작성(엔드포인트/필드/에러코드) (P2)
5. **PM**: WBS ID 기준 주간 진행 리듬(화/금) Gate 점검 캘린더 고정 (P2)
