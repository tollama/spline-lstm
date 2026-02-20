# GUI Phase 3 Coder Notes

## Standard Handoff Format

### 1) 요청/목표
- 프로젝트: `~/spline-lstm` (`ui/` 프론트엔드)
- 역할: Coder (GUI Phase 3)
- 목표: UX/안정성 개선 구현
- 필수 작업:
  1. 중복 요청 방지/취소 처리 개선
  2. 로딩/빈 상태/오류 복구 UI 개선
  3. 간단 토스트/알림 컴포넌트 추가
  4. 문서화 (`docs/GUI_PHASE3_CODER_NOTES.md`)

---

### 2) 변경 파일 목록
- `ui/src/api/client.ts`
- `ui/src/App.tsx`
- `ui/src/pages/RunJobPage.tsx`
- `ui/src/pages/ResultsPage.tsx`
- `ui/src/pages/DashboardPage.tsx`
- `ui/src/styles.css`
- `ui/src/components/Toast.tsx` (신규)
- `docs/GUI_PHASE3_CODER_NOTES.md` (신규)

---

### 3) 핵심 구현 내용

#### A. 중복 요청 방지 / 취소 처리
- `client.ts`
  - `ApiRequestOptions`/`RequestPolicy`에 `signal?: AbortSignal` 추가
  - `fetchJson`에서 외부 AbortSignal과 내부 timeout Abort를 동시에 처리
  - `postRunJob`, `fetchJob`, `fetchJobLogs`, `fetchResult`에 signal 전달 경로 추가
- `RunJobPage.tsx`
  - 진행 중(`submitting`/`polling`)일 때 submit 비활성화로 중복 요청 차단
  - `AbortController` + `requestVersionRef`로 stale 응답 무시
  - Cancel 버튼 추가: 제출/폴링 요청 모두 취소, 상태를 `canceled`로 전이
  - 폴링 중 새 요청 시 기존 폴링/요청 정리
- `ResultsPage.tsx`
  - 연속 조회 시 이전 조회 요청 abort
  - request version으로 stale 업데이트 방지

#### B. 로딩 / 빈 상태 / 오류 복구 UI
- `DashboardPage.tsx`
  - `loading | loaded | empty | error` 상태 분리
  - 오류 시 재시도 버튼 제공
  - recentJobs가 비어있을 때 빈 상태 메시지 출력
- `ResultsPage.tsx`
  - `loading | loaded | empty | error` 상태 분리
  - 오류 시 재시도 버튼 제공
  - predictions 빈 배열이면 empty 상태 메시지 출력
- `RunJobPage.tsx`
  - 실행 중 로그 로딩 메시지(`로그 수집 중...`)
  - timeout/fail/canceled 상태 표시 개선

#### C. 토스트/알림 컴포넌트
- 신규 `ToastProvider` / `useToast` 구현 (`ui/src/components/Toast.tsx`)
  - 간단한 `showToast(message, tone, durationMs)` API
  - `info/success/error` 톤 지원
  - 자동 소멸 타이머
- `App.tsx`에서 전역 Provider 적용
- 주요 성공/실패/취소 지점에서 토스트 노출

#### D. 스타일 보강
- 공통 액션 레이아웃(`.action-row`) 추가
- disabled 버튼 시각 상태 추가
- 토스트 viewport/item 스타일 추가

---

### 4) 회귀 방지 관점 체크
- 기존 탭 구조/페이지 진입 흐름 유지 (`Dashboard`, `Run Job`, `Results`)
- 기존 API 호출 계약 유지(기존 파라미터 및 응답 매핑 불변)
- Phase 1/2 핵심 기능(실행 요청/상태 조회/결과 조회) 제거 없이 확장 방식 적용
- abort/중복방지 로직은 additive 방식으로 반영

---

### 5) 검증 결과 (빌드/테스트)

#### 실행 명령
- `cd ui && npm run build`
- `cd ui && npm test`

#### 결과
- Build: **PASS**
  - `tsc -b && vite build` 성공
- Test: **PASS**
  - Vitest: `src/api/errorNormalization.test.ts` 5/5 통과

---

### 6) 알려진 제한 / 후속 권장
- 현재 토스트는 큐 관리/수동 dismiss/애니메이션 없이 경량 구현
- 취소 판별은 오류 메시지 텍스트(`abort`/`cancel`) 기반이므로, 추후 `ApiError.code` 표준화 시 명시 판별로 개선 권장
- Dashboard fetch는 단건 요청이라 별도 cancel 불필요로 유지 (필요 시 signal 확장 가능)

---

### 7) 인수인계 메모
- Phase 3 목표였던 UX/안정성 항목(중복 방지, 취소, 상태 UI, 알림)을 코드 반영 완료
- 리뷰 시에는 다음을 중점 확인 권장:
  1. Run Job에서 빠른 연타/취소 시 상태 일관성
  2. Results/Dashboard 오류 후 재시도 경로
  3. 토스트가 과다 노출되지 않는지 UX 점검
