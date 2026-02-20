# E2E_TEST_PLAN — Spline-LSTM E2E 테스트 마스터 플랜

## Standard Handoff Format

### 1) 요청/목표
- 역할: Project Manager (E2E 테스트 마스터 플랜 수립)
- 프로젝트: `~/spline-lstm`
- 목표: **실행 가능한 Phase1~5 통합 E2E 테스트 계획**을 정의하고, Go/No-Go 의사결정 기준을 고정한다.
- 적용 범위:
  - 문서 기준: `docs/PHASE1_ARCH.md` ~ `docs/PHASE5_ARCH.md`, `docs/RUNBOOK.md`
  - 실행 경로 기준: `scripts/run_e2e.sh`, `scripts/smoke_test.sh`, `scripts/run_compare.sh`
  - 테스트 자산 기준: `tests/test_*.py`

---

### 2) E2E 범위 정의 (Phase1~5 중 E2E 대상)

#### 2.1 Phase별 E2E 대상

| Phase | E2E 대상 | 포함 범위 | 제외 범위 |
|---|---|---|---|
| Phase1 | 전처리 E2E | 입력 스키마 검증 → 보간/평활 → 스케일링 → 윈도우 → `processed.npz/meta.json/preprocessor.pkl` 생성 | 모델 학습/평가 |
| Phase2 | 학습/평가 E2E | Phase1 산출물 입력 → LSTM 학습/평가 → `best/last checkpoint`, `metrics`, `report` 생성 | 확장 모델 비교 |
| Phase3 | 재현성/베이스라인 E2E | 동일 seed 재실행 편차 검증, baseline(naive/MA) 비교, run metadata 검증 | edge 변환 |
| Phase4 | 운영 E2E | one-click 실행, smoke/health gate, run_id mismatch 차단, runbook 복구 절차 | 모델 고도화 |
| Phase5 | 확장 E2E | 모델 비교(LSTM/GRU/Attention), multivariate/covariates 경로, 비교 리포트 생성 | 대규모 HPO/실서비스 배포 |

#### 2.2 End-to-End 시나리오 세트
- **E2E-S1 (Core Smoke)**: synthetic one-click 실행 성공 여부
- **E2E-S2 (Data Contract)**: 스키마/결측/shape fail-fast 검증
- **E2E-S3 (Train-Eval)**: LSTM 기준 학습/평가 산출물 무결성 검증
- **E2E-S4 (Repro/Baseline)**: seed 고정 2회 재실행 + baseline 비교 유효성 검증
- **E2E-S5 (Ops Guard)**: run_id mismatch 의도 주입 시 차단(실패 코드) 검증
- **E2E-S6 (Extension)**: run_compare 기반 확장 비교 결과 파일 생성 검증

---

### 3) 우선순위/일정 (Day Plan, 10일)

#### 3.1 우선순위
- **P0 (필수 게이트)**: S1~S5
- **P1 (확장 게이트)**: S6
- **P2 (고도화)**: 성능 회귀 추세 모니터링 자동화(후속)

#### 3.2 Day Plan

| Day | 목표 | 주요 작업 | 산출물 |
|---|---|---|---|
| D1 | 계획/환경 고정 | 테스트 브랜치, 의존성 설치, 실행 변수(run_id prefix) 규칙 고정 | 실행 체크리스트 v1 |
| D2 | Phase1 E2E | S2 수행(정상/실패 케이스), 전처리 artifact 검증 | 데이터 계약 결과 로그 |
| D3 | Phase2 E2E | S3 수행, metrics/report/checkpoint 계약 검증 | 학습/평가 결과 로그 |
| D4 | Phase3 E2E | S4 수행(동일 seed 2회), 편차 허용치 점검 | 재현성 검증 로그 |
| D5 | Phase4 E2E-1 | S1 수행(one-click smoke), health 항목 체크 | 스모크 PASS/FAIL 기록 |
| D6 | Phase4 E2E-2 | S5 수행(run_id mismatch 주입), 차단 동작 검증 | 가드 테스트 로그 |
| D7 | 결함 수정 버퍼 | D2~D6 Fail 항목 수정/재검증 | Fixpass 로그 |
| D8 | Phase5 E2E | S6 수행(`scripts/run_compare.sh`), 비교 리포트 생성 검증 | 비교 결과 파일 |
| D9 | 통합 회귀 | S1~S6 축약 재실행(회귀 확인) | 통합 회귀 리포트 |
| D10 | 최종 게이트 | Go/No-Go 판정 회의용 문서 정리 | 최종 판정서 |

---

### 4) 필요 리소스 (환경/데이터/의존성)

#### 4.1 환경
- OS: macOS/Linux (Python 3.10+ 권장)
- 런타임: `python3`, `pytest`, TensorFlow/Keras 실행 가능 환경
- 디렉터리 권한: `artifacts/`, `checkpoints/`, `data/` 쓰기 가능

#### 4.2 데이터
- 기본 스모크: synthetic 데이터(`src.preprocessing.smoke` 기본 경로)
- 실데이터 검증(선택): `data/raw/*.csv` (필수 컬럼: `timestamp`, `target`)
- 확장 검증(Phase5): covariate 포함 샘플(`data/raw/phase5_covariate_input.csv` 또는 동등 샘플)

#### 4.3 의존성/도구
- `pip install -r requirements.txt`
- 실행 스크립트:
  - `bash scripts/run_e2e.sh`
  - `bash scripts/smoke_test.sh`
  - `bash scripts/run_compare.sh`
- 테스트 스위트(핵심):
  - `tests/test_data_contract.py`
  - `tests/test_training_runner_cli_contract.py`
  - `tests/test_phase3_repro_baseline.py`
  - `tests/test_phase4_run_id_guard.py`
  - `tests/test_phase5_extension.py`

#### 4.4 인력/역할
- PM: 일정/게이트 관리, Go/No-Go 선언
- Coder: 실패 케이스 수정 및 재실행
- Reviewer: 계약 일치성 검토
- Tester: 실행/증적 수집/결과 문서화

---

### 5) Gate/완료 기준 (Go/No-Go)

#### 5.1 Gate 정의

| Gate | 통과 조건 (PASS) | 실패 조건 (FAIL) |
|---|---|---|
| G1 Data Contract | 전처리 정상 케이스 성공 + 실패 케이스 fail-fast 정상 동작 | 스키마 위반 미차단, shape 불일치 |
| G2 Train/Eval | checkpoint(best/last), metrics, report 생성 및 파싱 성공 | 필수 산출물 누락/파싱 실패 |
| G3 Repro/Baseline | 동일 seed 2회 편차 허용 범위 내 + baseline 비교 필드 유효 | 편차 과다, baseline 누락 |
| G4 Ops Guard | one-click smoke PASS + run_id mismatch 차단 PASS | smoke 실패, mismatch 미차단 |
| G5 Extension | run_compare 실행 및 비교 산출물 생성/검증 PASS | 확장 경로 실행 불가/산출물 무효 |

#### 5.2 최종 Go/No-Go 규칙
- **GO**: G1~G4 전부 PASS, G5는 최소 1회 PASS(Phase5 릴리즈 후보 시 필수)
- **NO-GO**: G1~G4 중 하나라도 FAIL
- **조건부 GO**: G1~G4 PASS + G5 FAIL인 경우, “MVP 운영 릴리즈만 허용 / 확장 기능 배포 보류”

#### 5.3 완료(Definition of Done)
- [ ] S1~S5 실행 로그 및 산출물 경로가 문서화됨
- [ ] 실패 케이스 재현 절차와 복구 절차가 `docs/RUNBOOK.md`와 정합
- [ ] 최종 Gate 표(PASS/FAIL)와 책임자 서명(역할 기준)이 남음

---

### 6) 리스크 및 롤백 전략

#### 6.1 주요 리스크
1. **환경 의존성 리스크**: TF/keras 버전 차이로 학습 실패 또는 편차 확대
2. **데이터 계약 리스크**: timestamp/target 품질 이슈로 전처리 단계 실패
3. **아티팩트 오염 리스크**: run_id 혼선으로 잘못된 전처리-모델 조합
4. **확장 경로 리스크**: Phase5 비교/멀티변수 경로 미완성으로 E2E 중단

#### 6.2 롤백 전략
- **R1 (실행 롤백)**: 실패 run_id 폐기 후 신규 run_id로 전체 파이프라인 재실행
- **R2 (기능 롤백)**: 확장 기능(Phase5) 실패 시 `model_type=lstm`, univariate 경로로 고정
- **R3 (배포 롤백)**: G5 FAIL 시 확장 배포 중단, Phase4 운영 경로만 유지
- **R4 (품질 롤백)**: 재현성 편차 초과 시 직전 PASS 커밋/requirements 조합으로 복귀

#### 6.3 에스컬레이션 트리거
- 동일 원인으로 Gate FAIL 2회 반복
- run_id mismatch 차단 실패(안전 게이트 붕괴)
- smoke 테스트 연속 2회 FAIL

---

### 7) 즉시 실행 체크리스트 (Execution Checklist)
- [ ] `python3 -m pip install -r requirements.txt`
- [ ] `bash scripts/smoke_test.sh` 1회 실행
- [ ] `bash scripts/run_e2e.sh` 실행 후 필수 산출물 8종 확인
- [ ] `pytest -q tests/test_phase4_run_id_guard.py` 실행
- [ ] `pytest -q tests/test_phase3_repro_baseline.py` 실행
- [ ] `bash scripts/run_compare.sh` 실행(Phase5 후보 게이트)
- [ ] Gate 표 업데이트 후 Go/No-Go 선언

---

### 8) PM 핸드오프 메모
- 본 계획은 **MVP 운영 안정성(G1~G4) 우선**, 확장 기능(G5)은 별도 게이트로 분리해 릴리즈 리스크를 낮춘다.
- 판정 원칙은 “실행 로그/산출물 증적 기반”이며, 문서 주장만으로 PASS 처리하지 않는다.
- 최종 릴리즈 회의에는 최소한 최근 48시간 내 수행한 S1~S5 증적(run_id, 로그, metrics 경로)을 첨부한다.
