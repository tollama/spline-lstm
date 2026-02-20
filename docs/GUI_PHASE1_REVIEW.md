# GUI Phase 1 리뷰

## Standard Handoff Format

### 1) 요청/목표
- 프로젝트: `~/spline-lstm`
- 역할: Reviewer (GUI Phase 1 Gate 판정)
- 목표: 현재 GUI 구현(`ui/`)이 Phase 1 게이트를 통과 가능한지 검토하고, Must/Should/Nice 분류 및 PASS/FAIL 판정 제시

---

### 2) 리뷰 범위 / 방법
- 코드 리뷰 대상
  - `ui/src/App.tsx`
  - `ui/src/pages/DashboardPage.tsx`
  - `ui/src/pages/RunJobPage.tsx`
  - `ui/src/pages/ResultsPage.tsx`
  - `ui/src/api/client.ts`
  - `ui/src/styles.css`
- 기준 문서
  - `docs/GUI_PRODUCT_PLAN.md` (MVP In-Scope)
  - `docs/GUI_TEST_CHECKLIST.md` (핵심 플로우/FAIL 조건)
  - `docs/GUI_ARCHITECTURE.md` (API 계약 방향)
- 실행 확인
  - `cd ui && npm run build` → **성공** (타입체크/번들링 통과)

---

### 3) 요약 결론
- 현재 구현은 **"UI 골격(Prototype Scaffold)" 수준**으로, 화면 전환/기본 폼/목업 데이터 표시는 동작함.
- 다만 Phase 1 게이트 기준(핵심 플로우 신뢰성, 오류 가시성, API 계약 정합, 결과/로그 동작성)으로는 필수 결함이 남아 있음.
- **Gate 판정: FAIL**

> 판정 규칙: Must fix = 0 이어야 PASS

---

### 4) Must / Should / Nice

## Must fix (게이트 차단)

1. **백엔드 장애/실패가 UI에서 성공처럼 보이는 구조 (실패 은닉)**
- 근거: `ui/src/api/client.ts:16-23, 26-39, 41-55, 57-70`
- 문제:
  - `safeFetch`가 모든 에러를 `null`로 삼키고,
  - 각 API 함수가 즉시 mock 정상 응답으로 폴백함.
- 영향:
  - 서버 다운/HTTP 오류/계약 불일치 상황에서도 사용자에게 "정상 데이터"처럼 표시됨.
  - `GUI_TEST_CHECKLIST`의 실패 처리(FLOW-04) 및 상태 신뢰성 기준 위반.
- 권고:
  - 개발모드 한정 mock 플래그(예: `VITE_USE_MOCK`) 분리
  - 운영/게이트 환경에서는 실제 오류를 surface(에러 배너, 재시도, 로그 링크)

2. **API 경로 계약 불일치 (`/api/ui/*` vs 아키텍처 `/api/v1/*`)**
- 근거:
  - 구현: `ui/src/api/client.ts:27-29, 42-44, 58-60` (`/api/ui/...`)
  - 설계: `docs/GUI_ARCHITECTURE.md` (`/api/v1/...`)
- 영향:
  - 실제 백엔드 연결 시 즉시 연동 실패 가능성 높음.
  - 현재는 Must #1의 mock 폴백 때문에 실패가 가려짐.
- 권고:
  - 단일 API 계약 문서 기준으로 엔드포인트 정규화
  - 타입/스키마(요청/응답)와 함께 계약 테스트 추가

3. **핵심 실행 플로우 상태 모델 부재 (queued/running/success/fail 추적 없음)**
- 근거:
  - `RunJobPage`는 submit 후 응답 JSON 텍스트만 출력 (`ui/src/pages/RunJobPage.tsx:16-19, 41-44`)
  - Job 상태조회/로그조회/실패 분기 UI 없음
- 영향:
  - Phase 1 핵심 여정(실행→진행→완료/실패→재시도) 검증 불가
  - 체크리스트 FLOW-01/04/05의 요구를 충족하기 어려움
- 권고:
  - `jobId` 기반 상태 폴링(or SSE) 도입
  - 상태 배지/진행도/실패 액션(재시도, 로그보기) 최소 구현

---

## Should fix (품질/완성도)

1. **입력 검증 약함 (runId/epochs 도메인 검증 부족)**
- 근거: `ui/src/pages/RunJobPage.tsx:10-15, 25-37`
- 제안:
  - runId 패턴 검증, epochs 상한/정수 검증, 에러 메시지 필드별 제공

2. **결과 페이지 로딩/에러 상태 분기 미흡**
- 근거: `ui/src/pages/ResultsPage.tsx:8-13, 24-47`
- 제안:
  - 로딩/빈결과/오류 상태를 분리하고 사용자 액션(재조회) 명확화

3. **탭 내비게이션의 URL 상태 미반영**
- 근거: `ui/src/App.tsx:9-27`
- 제안:
  - React Router 도입으로 딥링크/새로고침 복원/히스토리 이동 지원

---

## Nice to have (다음 단계 개선)

1. **접근성(A11y) 보강**
- 제안: 탭 role/aria-selected, 라이브 리전(로그/상태 변화), 키보드 탐색 강화

2. **모바일 UX 최적화**
- 제안: 하단 탭, 긴 JSON/테이블 카드화, 터치 타겟/간격 재조정

3. **테스트 자동화 기반 구축**
- 제안: 최소 E2E(Playwright)로 FLOW-01/03/04 회귀 체크

---

### 5) Gate 판정
- Must fix: **3건**
- Should fix: 3건
- Nice to have: 3건

## 최종 판정: **FAIL**
- 사유: Must fix가 0이 아님
- PASS 조건: 위 Must 3건 해소 후 재검증

---

### 6) 우선 조치 순서 (권장)
1. mock fallback 정책 분리(개발/운영) + 오류 노출
2. API 경로를 단일 계약(`/api/v1` 또는 합의안)으로 정렬
3. Job 상태/로그를 포함한 실행 플로우 최소 구현
4. 입력 검증/결과 상태 분기/A11y 보강

---

### 7) 인수인계 메모
- 이번 리뷰는 기능 구현 수준이 아닌 **Phase 1 게이트 충족 여부** 기준의 차단 이슈 중심으로 작성함.
- 빌드는 통과했으나, 게이트의 핵심은 "실행 플로우 신뢰성 + 실패 가시성"이므로 현재는 출시/게이트 통과로 보기 어려움.
