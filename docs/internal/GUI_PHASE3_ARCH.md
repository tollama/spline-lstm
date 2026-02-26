# GUI_PHASE3_ARCH — GUI Phase 3 설계 고정 (실연동 안정화 + UX 개선)

## Standard Handoff Format

### 1) 요청/목표
- 역할: Architect
- 프로젝트: `~/spline-lstm`
- 목표: **Phase 2 실연동 기반을 안정화하고, Phase 3에서 사용자 체감 품질(로딩/빈상태/오류복구/토스트)을 제품 수준으로 끌어올리기 위한 아키텍처 기준선 고정**
- 핵심 산출물 범위:
  1. API 실연동 안정화 전략(캐시/재시도/중복요청 방지)
  2. UX 개선 항목(로딩/빈상태/오류복구/토스트)
  3. 성능 목표(초기 로딩/상호작용 응답성)
  4. Phase 3 DoD
- 비범위:
  - 인증/권한(RBAC), 멀티테넌시
  - WebSocket/SSE 전면 도입(Phase 4+ 후보)
  - 백엔드 도메인 로직 자체 변경(본 문서는 GUI 클라이언트/표현 계층 중심)

---

### 2) Phase 3 결정 요약 (Locked)
1. **요청 안정화 계층 신설**: `ui/src/api/client.ts` 위에 `Request Orchestrator`(캐시 + in-flight dedupe + retry policy)를 고정 적용한다.
2. **읽기 API는 SWR 패턴으로 통일**: stale-while-revalidate 방식으로 즉시 표시 + 백그라운드 갱신.
3. **재시도 정책을 메서드/에러별로 분리**: GET은 적극 재시도, POST는 기본 무재시도(단 idempotency key가 있을 때만 제한 재시도).
4. **중복 요청 방지 규칙 고정**: 동일 Query Key의 동시 요청은 Promise 공유(단일 네트워크 호출).
5. **UX 상태 표준화**: 페이지별 산발 상태를 `loading | empty | error | ready` + `recovering` 서브상태로 정규화.
6. **토스트 정책 고정**: 성공/경고/오류/정보 유형과 노출 시간, 중복 억제(동일 key) 규칙을 공통 훅으로 관리.

---

### 3) API 실연동 안정화 전략 (캐시/재시도/중복요청 방지)

#### 3.1 목표 지향 원칙
- **안정성 우선**: 일시적 네트워크 문제는 자동 복구하되, 영구 오류(입력 오류/권한 오류)는 즉시 사용자 조치로 전환
- **일관성 우선**: 페이지마다 다른 재시도/에러 처리 금지
- **관측 가능성 우선**: request_id, retry 횟수, 실패 사유를 로그/토스트에서 추적 가능하게 유지

#### 3.2 아키텍처 레이어
1. **Transport Layer** (`fetchJson`)  
   - timeout, HTTP 파싱, 공통 에러 정규화 담당
2. **Orchestrator Layer** (Phase 3 신규)
   - query key 생성, 캐시 조회/저장, in-flight dedupe, 정책 기반 retry 수행
3. **UI Data Hook Layer** (Phase 3 신규)
   - `useDashboardSummary`, `useJobStatus`, `useRunResult` 등 화면 의존 훅 제공
4. **Presentation Layer**
   - 로딩/빈상태/오류/토스트 및 복구 CTA 렌더링

#### 3.3 캐시 전략 (권장 TTL/정합성)
- 캐시 단위: `method + normalizedPath + serializedParams`
- 기본 정책:
  - `GET /dashboard/summary`: TTL 15s, SWR 활성화
  - `GET /jobs/{job_id}`: TTL 2s (짧은 라이브 캐시)
  - `GET /jobs/{job_id}/logs`: TTL 1s, append-merge
  - `GET /runs/{run_id}/report|metrics|artifacts`: TTL 60s
- 무효화 이벤트:
  - `POST /pipelines/*:run` 성공 시 관련 dashboard/job 캐시 invalidate
  - Job terminal(`success|fail|canceled`) 진입 시 해당 job 상태 캐시 freeze 후 결과 캐시 prefetch
- 정합성 규칙:
  - 캐시가 있어도 백그라운드 재검증 수행(SWR)
  - 최신 응답 우선(last-write-wins), 단 로그는 `offset` 기준 append only

#### 3.4 재시도 전략
- 공통 백오프: `baseDelay * 2^(attempt-1)` + jitter(±20%)
- 최대 시도:
  - GET: 기본 2회 재시도(총 3회)
  - POST(run submit): 기본 0회, 단 `Idempotency-Key` 존재 시 1회 허용
- 재시도 대상:
  - HTTP: 408/425/429/500/502/503/504
  - 네트워크 단절, timeout, DNS 임시 오류
- 재시도 금지:
  - 400/401/403/404/409(업무 충돌), validation error
- UI 반영:
  - 재시도 발생 시 `recovering` 뱃지 + “자동 복구 중” 토스트(중복 억제)
  - 최종 실패 시 오류 카드 + 복구 버튼(재시도/새로고침/입력수정)

#### 3.5 중복요청 방지 (In-flight Dedupe)
- 동일 query key 요청 동시 발생 시:
  - 첫 요청 Promise를 registry에 저장
  - 후속 요청은 동일 Promise를 await
  - 완료/실패 시 registry에서 제거
- dedupe window: 요청 시작~종료 전 구간(하드 10초 cap)
- 예외:
  - 강제 갱신(`force: true`)은 dedupe 우회 가능
  - mutation(POST/DELETE)은 dedupe 기본 비활성(의미론적 중복 방지를 위해 idempotency key로 통제)

#### 3.6 권장 인터페이스 (예시)
```ts
// ui/src/api/orchestrator.ts
export type QueryPolicy = {
  ttlMs: number;
  swr?: boolean;
  retries?: number;
  retryDelayMs?: number;
  dedupe?: boolean;
};

export async function query<T>(key: string, fn: () => Promise<T>, policy: QueryPolicy): Promise<T>;
export function invalidate(prefix: string): void;
```

---

### 4) UX 개선 항목 (로딩/빈상태/오류복구/토스트)

#### 4.1 로딩 UX
- 전역 스피너 최소화, **스켈레톤 우선**
- 페이지별 규칙:
  - Dashboard: 카드 3개 + 테이블 스켈레톤
  - RunJob: 제출 버튼 로딩 + 상태 패널 shimmer
  - Results: 메트릭 카드/테이블 스켈레톤
- 지연 표시 기준:
  - 300ms 미만: 로딩 UI 생략 가능(깜빡임 방지)
  - 300ms 이상: 스켈레톤 표시
  - 3s 초과: “응답이 지연되고 있습니다” 보조문구

#### 4.2 빈 상태(Empty State)
- 데이터가 0건일 때 단순 공백 금지
- 표준 구성:
  - 원인 설명(예: “아직 실행 이력이 없습니다”)
  - 다음 행동 CTA(“첫 실행 시작”, “필터 초기화”, “샘플 run_id 불러오기”)
  - 보조 링크(문서/가이드)

#### 4.3 오류 복구 UX
- 오류 등급:
  - Recoverable: 네트워크/일시 장애 → 자동 재시도 + 수동 재시도 버튼
  - Actionable: validation/user input 오류 → 필드 포커스 + 가이드 문구
  - Terminal: 서버 내부/권한/계약 불일치 → request_id 포함 오류 카드 + 문의 안내
- 공통 복구 컴포넌트:
  - `ErrorRecoveryPanel`(오류 요약, request_id, [다시 시도], [입력 수정], [홈 이동])
- Job 화면 특화:
  - `timeout` 상태에서 “폴링 재개”와 “새 작업 시작” 분리 제공

#### 4.4 토스트 정책
- 타입: `success | info | warning | error`
- 기본 지속시간:
  - success/info: 2.5s
  - warning: 4s
  - error: 수동 닫기(최소 6s 후 auto-dismiss 허용 옵션)
- 중복 억제:
  - 동일 `toastKey` 10초 내 1회만 노출
- 사용 규칙:
  - 성공 토스트는 조용히(1회)
  - 자동 재시도 중에는 info/warning만 사용
  - 치명 오류는 반드시 오류 카드 + 토스트 병행

---

### 5) 성능 목표 (Phase 3 SLO)

#### 5.1 초기 로딩 목표
- `ui` 첫 화면 기준(개발환경 제외, 프로덕션 빌드):
  - **FCP ≤ 1.8s (P75)**
  - **LCP ≤ 2.5s (P75)**
  - JS 초기 번들(압축) **≤ 250KB** 목표
- 전략:
  - 라우트 단위 코드 스플리팅
  - Results 페이지 테이블/차트 지연 로드
  - API 응답 캐시로 최초 재진입 시간 단축

#### 5.2 상호작용 응답성 목표
- 버튼 클릭→시각적 피드백: **100ms 이내**
- 탭/페이지 전환 입력 지연(INP 대응): **P75 200ms 이하**
- RunJob 상태 갱신 주기:
  - 기본 poll 1.2~2.5s, 백오프 최대 3s
  - 화면 렌더 block 없이 비동기 반영

#### 5.3 관측/측정 지표
- FE 메트릭:
  - `api_request_total`, `api_retry_total`, `api_error_total`
  - `cache_hit_ratio`(목표 40%+ for dashboard/results)
  - `dedupe_suppressed_total`
  - `ui_state_error_rate`, `toast_error_rate`
- 측정 도구:
  - 브라우저 Performance + Lighthouse CI(주요 페이지)
  - QA 수동 시나리오에서 체감 지연 체크리스트 병행

---

### 6) 구현 우선순위 / 워크패키지
1. **P0 — 데이터 계층 안정화**
   - orchestrator/cache/dedupe/retry 정책 모듈화
   - 기존 `client.ts`를 transport 중심으로 축소
2. **P0 — 상태 모델 통합**
   - 페이지별 상태 enum 통일(`loading|empty|error|ready|recovering`)
3. **P1 — UX 컴포넌트 표준화**
   - Skeleton, EmptyState, ErrorRecoveryPanel, ToastProvider 공통 컴포넌트
4. **P1 — 성능 개선**
   - 라우트 코드 스플리팅 + 결과 테이블 렌더 최적화
5. **P2 — 계측/품질 게이트 연동**
   - retry/cache/dedupe 메트릭 로그와 테스트 리포트 템플릿 반영

---

### 7) 리스크 및 대응
- 리스크 A: 캐시 stale 데이터 노출
  - 대응: SWR + invalidate 이벤트 명시 + force refresh 제공
- 리스크 B: 과도한 재시도로 서버 부하 증가
  - 대응: 재시도 횟수 상한, jitter, 429 시 추가 백오프
- 리스크 C: 토스트 남발로 UX 피로
  - 대응: dedupe key/우선순위 큐/동일 이벤트 병합
- 리스크 D: 페이지별 예외 처리 분산 유지
  - 대응: 공통 훅과 에러 패널을 강제 사용(코드리뷰 체크 항목)

---

### 8) Phase 3 DoD (Definition of Done)

#### 8.1 기능/아키텍처 DoD
- [ ] `Request Orchestrator`(cache + retry + dedupe) 구현 및 `Dashboard/RunJob/Results` 3페이지 적용
- [ ] 읽기 API 최소 4개 엔드포인트에 TTL + SWR 정책 반영
- [ ] in-flight dedupe 동작 검증(동일 요청 동시 5회 시 실제 네트워크 1회)
- [ ] 재시도 정책이 에러 타입별로 분기 적용(GET/POST 차등)

#### 8.2 UX DoD
- [ ] 3페이지 모두 로딩 스켈레톤 적용(로딩 텍스트 단독 노출 제거)
- [ ] 빈 상태 화면 + CTA 제공(테이블 공백 방치 금지)
- [ ] 오류 복구 패널 공통 적용(request_id, 재시도/수정 CTA)
- [ ] 토스트 시스템 도입(중복 억제 포함) 및 주요 성공/실패 흐름 연결

#### 8.3 성능 DoD
- [ ] Lighthouse 기준 FCP/LCP 목표치 충족(P75 환경에서 측정 리포트 첨부)
- [ ] 주요 사용자 액션(실행 버튼, 결과 로드)의 피드백 100ms 이내 확인
- [ ] cache hit ratio, retry count, error rate 측정 로그 확보

#### 8.4 품질/검증 DoD
- [ ] 단위 테스트: error normalization/retry/dedupe/cache 로직 커버
- [ ] 통합 테스트: 네트워크 실패→자동복구→최종 상태 전이 시나리오 PASS
- [ ] 회귀 테스트: 기존 Phase2 핵심 흐름(실행→상태→결과→로그) 무손상 확인
- [ ] 산출물 문서 갱신: 본 문서 + Tester 결과 문서 + Reviewer gate 문서 링크 정합

**Phase 3 Exit 조건:** 위 체크리스트 Must 항목(기능/UX/성능/품질) 모두 PASS, Reviewer Must-fix 0건.

---

### 9) 인수인계 메모 (Handoff)
- 본 문서는 GUI Phase 3의 **실연동 안정화 + UX 개선 기준선**을 고정한다.
- 구현팀(Coder)은 우선 `orchestrator` 계층부터 도입 후 페이지별 점진 치환한다.
- 테스트팀(Tester)은 dedupe/retry/cache 시나리오를 별도 케이스로 분리해 수치 기반 검증을 수행한다.
- 리뷰팀(Reviewer)은 “페이지별 임의 예외 처리” 재도입 여부를 Must-fix 관점으로 중점 점검한다.

---

### 10) 산출물
- [x] `docs/GUI_PHASE3_ARCH.md`
- [x] API 안정화 전략 / UX 개선 / 성능 목표 / DoD 포함

**최종 상태:** `ARCH BASELINE LOCKED (Phase 3)`
