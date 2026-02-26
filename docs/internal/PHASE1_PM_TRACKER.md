# PHASE 1 PM TRACKER (데이터 계약/전처리 기반 고정)

> **HISTORICAL NOTE (문서 정합성):** 이 문서는 해당 시점의 진행 스냅샷입니다. 현재 운영/실행 계약의 단일 기준은 `docs/RUNBOOK.md`와 최신 ARCH/FINAL/CLOSEOUT 문서입니다.
> 경로/CLI/게이트 상태가 본문과 다를 수 있으며, 운영 판단 시 현재 기준 문서를 우선합니다.


## 0) 문서 목적
- 목적: Spline-LSTM MVP의 **Phase 1(데이터 계약 + 전처리 기반 고정)** 완료를 위한 실행 관리 기준 제공
- 범위: 설계(Architect) → 구현(Coder) → 검토(Reviewer) → 검증(Tester) Gate를 통합한 완료 판단
- 기준일: 2026-02-18

---

## 1) Phase 1 목표 / 완료 조건

### 목표
1. 데이터 계약(Data Contract) 확정 및 문서화
2. 전처리 파이프라인(검증/보간/평활/스케일/윈도우) 동작 고정
3. 재현 가능한 전처리 산출물(`data/processed`, scaler, split index) 생성 규칙 확정
4. Phase 2(모델 학습 고도화)로 넘길 수 있는 안정적 입력 기반 확보

### Phase 1 Done 조건(요약)
- [ ] 입력/출력/아티팩트 계약 문서 승인
- [ ] 전처리 모듈 구현 완료 + 핵심 단위 테스트 통과
- [ ] 실패 케이스(스키마 오류/시간축 오류)에서 즉시 fail-fast 확인
- [ ] 샘플 데이터 기준 전처리 산출물 재현성 확인
- [ ] Architect/Coder/Reviewer/Tester Gate 모두 `PASS`

---

## 2) WBS (작업분해), 담당(role), 의존성, 완료체크리스트

> 상태 정의: `NS(미착수) / IP(진행중) / RD(검토대기) / DN(완료)`

| WBS ID | 작업 | 담당(Role) | 선행 의존성 | 산출물 | 상태 | 완료 체크리스트 |
|---|---|---|---|---|---|---|
| P1-01 | 데이터 계약 초안 정리(timestamp/target/cov_*) | Architect | 없음 | 계약 초안 문서 | NS | [ ] 필수 컬럼/타입 정의 [ ] 시간축 단조증가 규칙 [ ] 결측 허용정책 |
| P1-02 | 데이터 계약 승인(입력/출력/아티팩트) | Architect + Reviewer | P1-01 | 승인된 계약 섹션 | NS | [ ] shape 정의(X,y) [ ] artifact 경로/run_id 규칙 [ ] 실패 시 중단조건 |
| P1-03 | 입력 검증기 구현(schema/time-index validator) | Coder | P1-02 | `src/preprocessing/validators.py` | NS | [ ] 스키마 불일치 탐지 [ ] 시간축 오류 탐지 [ ] 에러 메시지 표준화 |
| P1-04 | spline 보간/평활 구현 및 파라미터화 | Coder | P1-02 | `src/preprocessing/spline.py` | NS | [ ] 결측 보간 [ ] 평활 강도 파라미터 [ ] 극단값/경계 처리 |
| P1-05 | transform(split/scale) 및 window 생성 고정 | Coder | P1-03, P1-04 | `transform.py`, `window.py` | NS | [ ] train/val/test 시간순 분할 [ ] scaler 저장 [ ] lookback/horizon shape 보장 |
| P1-06 | 전처리 단위 테스트 작성 | Tester | P1-03~P1-05 | `tests/preprocessing/*` | NS | [ ] 정상 케이스 [ ] 결측/불규칙 케이스 [ ] fail-fast 케이스 |
| P1-07 | 코드 리뷰 및 규약 점검 | Reviewer | P1-03~P1-06 | 리뷰 코멘트/수정내역 | NS | [ ] 계약 위반 없음 [ ] 예외처리 일관성 [ ] 로깅/가독성 확인 |
| P1-08 | 샘플 데이터 E2E 전처리 스모크 실행 | Tester | P1-07 | 실행 로그/산출물 | NS | [ ] raw→processed 생성 [ ] scaler/split index 저장 [ ] 재실행 동일성 확인 |
| P1-09 | Phase 1 게이트 통합 판정 및 종료 보고 | PM(메인) | P1-08 | 본 트래커 최종 갱신 | NS | [ ] Gate PASS 4종 [ ] blocker 0 또는 승인된 예외 [ ] 완료 선언 |

---

## 3) Gate 기준 (Architect/Coder/Reviewer/Tester) 통합 완료 판단

## 3.1 Architect Gate (설계 승인)
**PASS 기준**
- [ ] Data Contract 필수 항목 확정: `timestamp`, `target`, (선택) `cov_*`
- [ ] 전처리 I/O shape 확정: `X[batch, lookback, 1]`, `y[batch, horizon]`
- [ ] 아티팩트 규칙(run_id, 경로, 파일명) 확정
- [ ] Phase 1 범위 밖 항목(모델 고도화 등) 명시적으로 제외

**FAIL 트리거**
- 필수 컬럼/타입/shape가 문서 간 불일치

## 3.2 Coder Gate (구현 완료)
**PASS 기준**
- [ ] `validators/spline/transform/window` 구현 완료
- [ ] 설정 기반 파라미터 주입 가능(하드코딩 최소화)
- [ ] 예외 상황 fail-fast 및 명확한 에러 메시지
- [ ] 전처리 산출물 저장 규칙 준수

**FAIL 트리거**
- 계약 문서와 코드 동작 불일치

## 3.3 Reviewer Gate (품질 승인)
**PASS 기준**
- [ ] 계약 준수 여부 리뷰 체크리스트 통과
- [ ] 코드 복잡도/중복/네이밍/로깅 기준 충족
- [ ] 리뷰 지적사항(critical/high) 0건

**FAIL 트리거**
- critical/high 이슈 미해결 상태로 머지 시도

## 3.4 Tester Gate (검증 승인)
**PASS 기준**
- [ ] 전처리 단위 테스트 전부 통과
- [ ] 샘플 데이터 스모크 테스트 통과
- [ ] 동일 입력 재실행 시 산출물 일관성 확인
- [ ] 오류 입력 시 의도된 실패(fail-fast) 확인

**FAIL 트리거**
- 재현성 불안정 또는 실패 케이스 미검증

## 3.5 통합 판정 규칙
- 최종 `PASS` 조건: **Architect + Coder + Reviewer + Tester = 전부 PASS**
- 하나라도 FAIL이면 Phase 1은 `미완료` 유지
- 예외 승인 필요 시 PM이 blocker와 우회계획(기한/담당)을 문서에 명시

---

## 4) 운영 리듬(권장)
- 주 2회 고정 점검: WBS 상태 업데이트(NS/IP/RD/DN)
- Gate 리뷰 순서: Architect → Coder → Reviewer → Tester
- 변경관리: 계약 변경 발생 시 P1-01~P1-02 재오픈 후 하위 WBS 영향 재평가

---

## 5) 리스크/블로커 관리

| 구분 | 내용 | 영향 | 대응 | 오너 | 상태 |
|---|---|---|---|---|---|
| R1 | 원천 데이터 결측/불규칙 과다 | 전처리 실패/왜곡 | 결측률 리포트 + 보간 정책 상한 설정 | Architect/Coder | Open |
| R2 | 스플라인 과평활 | 신호 손실 | 평활 파라미터 범위 제한 + 시각 검증 | Coder/Tester | Open |
| R3 | 계약-구현 불일치 | 재작업/지연 | Gate 강제 + PR 템플릿 체크 | Reviewer | Open |
| R4 | 재현성 불안정 | 신뢰도 저하 | split index/scaler/run_id 고정 저장 | Tester | Open |

---

## 6) 최종 완료 선언 (Completion Declaration)

- Phase: **Phase 1 (데이터 계약/전처리 기반 고정)**
- 현재 완료 여부: **미완료 (IN PROGRESS)**
- Gate 상태:
  - Architect: `PENDING`
  - Coder: `PENDING`
  - Reviewer: `PENDING`
  - Tester: `PENDING`
- 현재 Blocker:
  1. WBS 전 항목 미착수(NS)로 실질 산출물 검증 전
  2. Gate PASS 증빙(테스트 결과/리뷰 승인) 부재

### 완료 선언 기준(체크 후 갱신)
- [ ] WBS P1-01 ~ P1-09 `DN`
- [ ] Gate 4종 `PASS`
- [ ] blocker `0` 또는 승인된 예외만 존재

> 위 3조건 충족 시 본 섹션을 `완료 (DONE)`로 변경하고, 완료일/승인자/근거 링크(PR, 테스트 로그)를 기록한다.
