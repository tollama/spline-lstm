# GUI_PHASE4_ARCH — GUI Phase 4 설계 고정 (운영/관측/릴리즈 기준선)

## Standard Handoff Format

### 1) 요청/목표
- 역할: Architect
- 프로젝트: `~/spline-lstm`
- 목표: **GUI Phase4에서 운영(배포), 관측(모니터링/로그/에러 추적), 릴리즈(성능/접근성 게이트), 복구(롤백/장애 대응) 기준을 고정하여 운영 가능한 릴리즈 체계 확립**
- 필수 산출물 범위:
  1. 배포 전략(dev/stage/prod) 및 config profile
  2. 모니터링/로그/에러 추적 기준
  3. 성능/접근성 릴리즈 기준
  4. 롤백/장애 대응 절차
  5. Phase4 DoD
- 비범위:
  - 신규 핵심 기능 대규모 추가
  - 인증/권한 모델 전면 재설계
  - 인프라 플랫폼 교체(K8s 전환 등)

---

### 2) Phase 4 결정 요약 (Locked)
1. **3단계 배포 체계(dev → stage → prod)를 고정**하고, 환경별 profile 기반 설정 주입을 표준화한다.
2. **관측성 최소 세트(SLI/SLO + 구조화 로그 + 에러 이벤트)를 릴리즈 필수 조건으로 고정**한다.
3. **성능/접근성 릴리즈 게이트를 수치 기준으로 강제**한다(기준 미달 시 배포 보류).
4. **롤백은 “이전 안정 버전 즉시 복귀 + 데이터 스키마 호환 확인”을 원칙**으로 한다.
5. **장애 대응은 탐지→분류→완화→복구→사후분석(Postmortem) 5단계 Runbook으로 고정**한다.

---

### 3) 배포 전략 (dev/stage/prod) 및 Config Profile

#### 3.1 배포 파이프라인 원칙
- 단일 trunk 기반(짧은 feature branch), 환경 승격형 배포:
  - `dev`: 빠른 통합/검증
  - `stage`: 운영 유사 조건 사전 검증
  - `prod`: 승인된 릴리즈만 반영
- 배포 단위: `ui` 정적 빌드 + `api` 서비스 버전 태그(동일 release id)
- 릴리즈 식별자: `release_id = gui-YYYYMMDD-HHMM-<git_sha7>`

#### 3.2 환경별 목적/정책
- **dev**
  - 목적: 개발자 통합 및 기능 검증
  - 배포: 자동(merge 시)
  - 데이터: 샘플/비식별 데이터
  - 관측: 디버그 로그 허용, 에러 추적 샘플링 완화
- **stage**
  - 목적: 릴리즈 후보(RC) 검증
  - 배포: 수동 승격(승인 필요)
  - 데이터: prod 유사 마스킹 데이터
  - 관측: prod 동등 지표/알람 정책 예행
- **prod**
  - 목적: 실제 사용자 서비스
  - 배포: Change 승인 + 배포 윈도우 준수
  - 데이터: 실제 운영 데이터
  - 관측: 경고/장애 알람 필수, 고위험 로그 마스킹 강제

#### 3.3 Config Profile 고정 규칙
- Profile 파일 구조(예시):
  - `ui/.env.dev`, `ui/.env.stage`, `ui/.env.prod`
  - `backend/config/dev.yaml`, `backend/config/stage.yaml`, `backend/config/prod.yaml`
- 설정 주입 우선순위:
  1) 런타임 Secret/Env
  2) profile 파일
  3) 코드 기본값(최후 fallback)
- 필수 profile 키(예시):
  - `API_BASE_URL`
  - `LOG_LEVEL`
  - `ERROR_TRACKING_DSN`
  - `METRICS_EXPORT_ENABLED`
  - `FEATURE_FLAGS` (JSON 문자열)
  - `RELEASE_ID`
- 금지 규칙:
  - prod secret를 저장소에 평문 커밋 금지
  - 환경별 API endpoint 하드코딩 금지
  - profile 미지정 상태에서 prod 배포 금지

#### 3.4 배포 게이트(환경 승격 조건)
- dev → stage:
  - 단위/통합 테스트 PASS
  - UI 핵심 흐름 회귀 PASS
- stage → prod:
  - 성능/접근성 릴리즈 기준 PASS(5장)
  - 장애 복구 리허설(롤백 dry-run) PASS
  - Reviewer/PM 최종 승인

---

### 4) 모니터링 / 로그 / 에러 추적 기준

#### 4.1 SLI/SLO 기준선
- 가용성(Availability): 월간 **99.5% 이상**
- API 성공률(2xx/3xx): **99.0% 이상**
- 핵심 사용자 플로우 성공률(실행 제출→결과 조회): **98.0% 이상**
- p95 API 응답시간:
  - 조회 API: **≤ 500ms**
  - 실행 제출 API: **≤ 1200ms**

#### 4.2 모니터링 지표(필수)
- 백엔드:
  - `http_requests_total{route,status}`
  - `http_request_duration_ms{route,p50,p95}`
  - `job_submit_total`, `job_fail_total`, `job_timeout_total`
- 프론트엔드:
  - `ui_page_load_ms`(FCP/LCP 보조)
  - `ui_action_latency_ms`(클릭→피드백)
  - `ui_error_boundary_total`
- 데이터 계층:
  - `api_retry_total`
  - `cache_hit_ratio`
  - `dedupe_suppressed_total`

#### 4.3 로그 표준(구조화 로그 JSON)
- 공통 필드(필수):
  - `ts`, `level`, `service`, `env`, `release_id`
  - `request_id`, `job_id`(있을 경우), `run_id`(있을 경우)
  - `event`, `message`, `error_code`(오류 시)
- 레벨 정책:
  - dev: `debug/info/warn/error`
  - stage/prod: 기본 `info/warn/error` (`debug`는 한시적 토글)
- 개인정보/민감정보 정책:
  - 사용자 입력 원문/토큰/secret 로그 기록 금지
  - 경로/쿼리 파라미터는 allowlist 기준 마스킹

#### 4.4 에러 추적 기준
- FE/BE 공통: 모든 unhandled exception은 에러 추적 시스템으로 전송
- 에러 이벤트 최소 필드:
  - `error_type`, `error_message`, `stack`, `request_id`, `release_id`, `env`
- 알람 임계치(초기안):
  - 동일 에러 5분 내 20회 이상 → 경고
  - API 5xx 비율 5분 평균 2% 초과 → 장애 선언 후보
- 배포 연계:
  - 신규 release 이후 30분 에러 급증 시 자동 롤백 검토 트리거

---

### 5) 성능/접근성 릴리즈 기준 (Release Gate)

#### 5.1 성능 기준 (prod 유사 stage 측정)
- Core Web Vitals(주요 페이지 p75):
  - **LCP ≤ 2.5s**
  - **INP ≤ 200ms**
  - **CLS ≤ 0.1**
- 초기 번들 예산:
  - 메인 JS gzip 기준 **≤ 280KB**
- API 체감 기준:
  - 사용자 액션 후 로딩 피드백 시작 **100ms 이내**

#### 5.2 접근성 기준
- WCAG 2.1 AA 핵심 항목 준수:
  - 색 대비(텍스트 대비비) 충족
  - 키보드 내비게이션 100% 가능
  - 포커스 표시 누락 0건
  - 폼 입력 라벨/에러 메시지 연결
- 자동 점검:
  - axe/Lighthouse 접근성 점수 **90점 이상**
- 수동 점검:
  - 핵심 플로우(대시보드, 실행 제출, 결과 조회) 키보드-only 시나리오 PASS

#### 5.3 릴리즈 차단 조건 (Blockers)
- Core Web Vitals 기준 1개 이상 미달
- 접근성 중대 결함(키보드 불가/스크린리더 핵심 정보 누락) 존재
- 장애/에러 추적 미연결 상태

---

### 6) 롤백 / 장애 대응 절차

#### 6.1 롤백 전략
- 기본 전략: **Blue-Green 또는 이전 안정 릴리즈 즉시 재배포**
- 롤백 트리거:
  - 배포 후 30분 내 5xx 급증, 핵심 플로우 실패율 급등, 치명 UI 장애
- 롤백 절차:
  1. Incident Commander 지정
  2. 신규 트래픽 차단/가중치 축소
  3. 직전 안정 release_id로 복귀
  4. 헬스체크/핵심 플로우 확인
  5. 사용자 영향 공지(내부 채널)

#### 6.2 장애 대응 Runbook (5단계)
1. **탐지(Detect)**: 알람 수신 및 최초 영향 범위 확인
2. **분류(Triage)**: Sev 분류
   - Sev1: 전체/핵심 기능 장애
   - Sev2: 부분 기능 중단
   - Sev3: 우회 가능한 경미 장애
3. **완화(Mitigate)**: 기능 플래그 off, 트래픽 우회, 임시 제한
4. **복구(Recover)**: 핫픽스 또는 롤백 적용 후 지표 정상화 확인
5. **사후분석(Learn)**: 24시간 내 Postmortem 초안

#### 6.3 커뮤니케이션 규칙
- Sev1/Sev2는 10분 내 내부 공유 시작
- 상태 업데이트 주기:
  - Sev1: 15분
  - Sev2: 30분
- 종료 조건: 지표 정상 + 재발 방지 액션오너 지정

---

### 7) Phase 4 DoD (Definition of Done)

#### 7.1 배포/환경 DoD
- [ ] dev/stage/prod 3환경 배포 경로 문서화 및 실제 배포 검증 완료
- [ ] config profile(`dev/stage/prod`) 키셋 표준화 및 누락 검증 스크립트 적용
- [ ] stage→prod 승격 승인 체크리스트 운영 시작

#### 7.2 관측성 DoD
- [ ] SLI/SLO 대시보드(가용성/응답시간/실패율) 구성 완료
- [ ] 구조화 로그 필수 필드(`request_id`, `release_id`, `env`) 100% 포함
- [ ] FE/BE unhandled error 추적 연동 및 알람 임계치 적용

#### 7.3 품질 게이트 DoD (성능/접근성)
- [ ] Core Web Vitals(LCP/INP/CLS) 목표 충족 리포트 첨부
- [ ] 접근성 자동 점검 90점 이상 + 수동 시나리오 PASS
- [ ] 릴리즈 차단 조건 검증 절차를 CI 또는 배포 체크리스트에 반영

#### 7.4 복구/운영 DoD
- [ ] 롤백 절차 문서 + stage dry-run 성공 증빙
- [ ] Sev1/Sev2 장애 대응 Runbook 리허설 1회 이상 수행
- [ ] Postmortem 템플릿 및 책임자 체계 명시

**Phase 4 Exit 조건:** 배포/관측/릴리즈/복구 4개 축의 Must 항목 전부 PASS, Reviewer Must-fix 0건.

---

### 8) 인수인계 메모 (Handoff)
- 본 문서는 GUI Phase4의 운영 기준선을 “환경 분리 + 관측성 + 릴리즈 게이트 + 복구 절차”로 고정한다.
- 구현팀은 config/profile 표준화와 로그/에러 추적 공통 모듈을 우선 적용한다.
- 테스트팀은 성능/접근성/롤백 리허설 증빙을 릴리즈 승인 입력물로 관리한다.
- 리뷰팀은 “측정 가능한 기준 존재 여부”와 “롤백 실효성”을 Must-fix 관점으로 검증한다.

---

### 9) 산출물
- [x] `docs/GUI_PHASE4_ARCH.md`
- [x] 배포 전략(dev/stage/prod) 및 config profile
- [x] 모니터링/로그/에러 추적 기준
- [x] 성능/접근성 릴리즈 기준
- [x] 롤백/장애 대응 절차
- [x] Phase4 DoD

**최종 상태:** `ARCH BASELINE LOCKED (GUI Phase 4)`
