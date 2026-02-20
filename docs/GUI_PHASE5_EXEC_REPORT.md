# GUI_PHASE5_EXEC_REPORT

## 1) Scope
- 기준 문서:
  - `docs/GUI_PHASE5_PM_TRACKER.md`
  - `docs/GUI_PHASE4_FINAL.md`
  - `docs/GUI_PHASE4_TEST_RESULTS.md`
  - `docs/GUI_PHASE2_ARCH.md` (미연동 API 계약 항목 확인)
- 목표:
  1. Phase5 관점에서 남아 있던 UI↔Backend 계약 미연동 구간 보완
  2. 최소 변경으로 기존 UI 플로우를 유지하면서 확장 계약 반영
  3. 테스트/빌드 검증 및 PM 트래커 상태 갱신

## 2) Implemented Work

### 2.1 UI/API 계약 확장
- `ui/src/api/client.ts`
  - 신규 연동:
    - `POST /api/v1/jobs/{job_id}:cancel`
    - `GET /api/v1/runs/{run_id}/metrics`
    - `GET /api/v1/runs/{run_id}/artifacts`
  - `fetchResult`를 split 계약(`metrics+artifacts+report`)과 legacy report 단일 페이로드 모두 지원하도록 확장
  - 구조화 로그(`lines[]`) 응답을 문자열 로그로 정규화
  - Run submit payload에 Phase5 옵션 필드(`feature_mode`, `target_cols`, `dynamic_covariates`, `export_formats`) 포함

### 2.2 Run/Results 화면 반영
- `ui/src/pages/RunJobPage.tsx`
  - Cancel 버튼이 active job 존재 시 backend cancel API 호출
  - 로컬 abort fallback 유지(아직 job_id 없는 제출 단계)
  - Run 폼에 Phase5 옵션 입력 항목 추가
- `ui/src/pages/ResultsPage.tsx`
  - metrics 카드 + artifacts 경로 + report raw 출력 통합
  - 예측 샘플 미제공 시 안내 문구로 graceful fallback

### 2.3 테스트 보강
- `ui/src/api/client.test.ts` (신규)
  - Phase5 run payload 직렬화 검증
  - 구조화 로그 파싱 검증
  - split 결과 엔드포인트 병합 검증
  - legacy report fallback 검증
  - cancel endpoint 매핑 검증

### 2.4 문서 갱신
- `docs/GUI_PHASE5_PM_TRACKER.md`
  - Phase5 실행 항목 상태(DN/NS) 업데이트
- `docs/GUI_QUICKSTART.md`
  - 실제 연동 엔드포인트 목록(`cancel`, `metrics`, `artifacts`) 반영
- `docs/GUI_PHASE5_EXEC_REPORT.md`
  - 본 실행 보고서 추가

## 3) Changed Files
- `ui/src/api/client.ts`
- `ui/src/pages/RunJobPage.tsx`
- `ui/src/pages/ResultsPage.tsx`
- `ui/src/api/client.test.ts`
- `docs/GUI_QUICKSTART.md`
- `docs/GUI_PHASE5_PM_TRACKER.md`
- `docs/GUI_PHASE5_EXEC_REPORT.md`

## 4) Commands Run

### UI
1. `cd /Users/ychoi/spline-lstm/ui && npm run test`
2. `cd /Users/ychoi/spline-lstm/ui && npm run build`

### Python (영향 확인)
3. `cd /Users/ychoi/spline-lstm && python3 -m pytest -q tests/test_phase5_runner_contract_alignment.py`

## 5) Test Results
- `npm run test`: PASS
  - `3 files`, `13 tests` 통과
- `npm run build`: PASS
  - `vite build` 성공
  - 산출물: `dist/assets/index-2JFQbdms.js` (gzip 53.20 kB)
- `pytest -q tests/test_phase5_runner_contract_alignment.py`: PASS
  - `4 passed`
  - 환경 경고(urllib3/matplotlib deprecation)는 있었으나 실패 없음

## 6) Remaining Blockers
- Blocker: 없음
- 남은 운영 과제(Phase5 Exit Gate 관점):
  1. 실제 파일럿 사용자 결과 수집 및 Go/No-Go 문서 확정
  2. 릴리즈 노트/운영 승인 서명 완료
