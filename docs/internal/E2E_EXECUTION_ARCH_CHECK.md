# E2E_EXECUTION_ARCH_CHECK — 실행 직전 계약 검증 및 실행 기준 고정

> 프로젝트: `~/spline-lstm`  
> 목적: E2E 실행 직전 **경로/입출력/아티팩트 계약**을 재확인하고, 실패코드(E2E-F001~F006) 매핑을 고정한다.  
> 기준 소스: `scripts/run_e2e.sh`, `scripts/smoke_test.sh`, `scripts/run_compare.sh`, `src/preprocessing/pipeline.py`, `src/training/runner.py`, `src/training/compare_runner.py`, `docs/E2E_TEST_ARCHITECTURE.md`

---

## 1) Summary
- 본선 경로(MVP): `preprocess(smoke) -> runner(train/eval/infer) -> artifacts`는 스크립트/코드 기준으로 계약이 일치함.
- 확장 경로(Phase5): `covariates/multivariate 전처리 + compare_runner`는 별도 게이트로 분리 운영해야 하며, 본선과 독립적으로 실패 처리 가능.
- 실패는 애플리케이션 고정 exit code가 아니라 예외/셸 실패 중심이므로, 실행/CI 레이어에서 **논리 실패코드(E2E-F001~F006) 정규화**가 필요.

---

## 2) Decisions Locked (실행 기준 고정)
1. **본선 우선 게이트 고정**
   - `bash scripts/run_e2e.sh` 성공 + `bash scripts/smoke_test.sh` 성공이 배포 전 최소 기준.
2. **run_id 무결성 고정**
   - `runner.py`의 run_id 경로/메타/preprocessor 일치 검증 실패 시 즉시 차단(ValueError).
3. **아티팩트 최소 계약 고정**
   - 본선 8종(아래 체크리스트) 누락 시 실패 처리.
4. **확장 경로 분리 고정**
   - `compare_runner`/multivariate 실패는 E2E-F006으로 분류하고, 본선 성공 시 MVP 릴리즈는 유지 가능(확장 배포만 보류).

---

## 3) 본선/확장 경로 계약 확인 체크리스트

## 3.1 본선(MVP) 실행 직전 체크리스트
- [ ] 작업 경로가 `~/spline-lstm`이다.
- [ ] 실행 엔트리포인트 존재:
  - [ ] `scripts/run_e2e.sh`
  - [ ] `scripts/smoke_test.sh`
  - [ ] `src/preprocessing/smoke.py`
  - [ ] `src/training/runner.py`
- [ ] 입력/실행 파라미터 계약:
  - [ ] `RUN_ID` 비어있지 않고 path separator(`/`,`\`) 미포함
  - [ ] `artifacts/` 쓰기 가능
  - [ ] (외부입력 사용 시) 입력 파일 존재 + timestamp/target 스키마 유효
- [ ] 본선 필수 산출물(8종) 계약:
  - [ ] `artifacts/processed/<RUN_ID>/processed.npz`
  - [ ] `artifacts/processed/<RUN_ID>/meta.json`
  - [ ] `artifacts/models/<RUN_ID>/preprocessor.pkl`
  - [ ] `artifacts/checkpoints/<RUN_ID>/best.keras`
  - [ ] `artifacts/checkpoints/<RUN_ID>/last.keras`
  - [ ] `artifacts/metrics/<RUN_ID>.json`
  - [ ] `artifacts/reports/<RUN_ID>.md`
  - [ ] `artifacts/metadata/<RUN_ID>.json`
- [ ] metrics 최소 키 계약:
  - [ ] `run_id`
  - [ ] `metrics.mae`, `metrics.rmse`, `metrics.mape`, `metrics.r2`
  - [ ] `checkpoints.best`, `checkpoints.last`
  - [ ] `inference.y_true_last`, `inference.y_pred_last`
- [ ] run_id 일치 계약:
  - [ ] CLI `--run-id` == `artifacts/processed/<run_id>/...` 경로 run_id
  - [ ] CLI `--run-id` == `meta.json.run_id`
  - [ ] CLI `--run-id` == `preprocessor.pkl` 내 `run_id`

## 3.2 확장(Phase5) 실행 직전 체크리스트
- [ ] 실행 엔트리포인트 존재:
  - [ ] `scripts/run_compare.sh`
  - [ ] `src/training/compare_runner.py`
- [ ] multivariate/covariates 전처리 계약(`pipeline.py`):
  - [ ] `covariate_cols` 지정 시 `processed.npz`에 `covariates_raw`, `features_scaled`, `X_mv`, `y_mv` 저장
  - [ ] `meta.json`에 `covariate_cols`, `X_mv_shape`, `y_mv_shape` 반영
- [ ] compare_runner 산출물 계약:
  - [ ] `artifacts/comparisons/<RUN_ID>.json`
  - [ ] `artifacts/comparisons/<RUN_ID>.md`
  - [ ] JSON에 `models.lstm.metrics`, `models.gru.metrics`, `summary.winner_by_rmse`
- [ ] 회귀 방지 계약:
  - [ ] 확장 실패 시에도 본선(`run_e2e.sh`) 성공 경로는 유지되어야 함

---

## 4) 실패코드(E2E-F001~F006) 매핑표 (검증 고정)

| 코드 | 분류 | 검출 신호(대표) | 주 발생 지점 | 1차 조치 |
|---|---|---|---|---|
| E2E-F001 | Input Contract | `FileNotFoundError`, 스키마 검증 실패 | `pipeline.py` 입력 로딩/검증 | 입력 경로, 컬럼(timestamp/target/covariate), 파일 권한 점검 |
| E2E-F002 | RunID Contract | `run_id mismatch`, invalid run_id(`path separator`) | `runner.py::_validate_run_id_consistency`, `pipeline.py::_validate_run_id` | 새 run_id 발급 후 preprocess~runner 전 구간 재실행 |
| E2E-F003 | Artifact Contract | 필수 파일 누락(`smoke_test.sh` 파일 존재검사 실패) | `smoke_test.sh`, 결과 디렉터리 | 누락 단계 재실행, 디스크/권한 확인 |
| E2E-F004 | Metrics Contract | metrics 키(`mae/rmse/mape/r2`) 누락 | `smoke_test.sh` JSON assert, post-check | 러너 결과 payload 스키마 점검, 손상 run 폐기 |
| E2E-F005 | Backend/Runtime | `TensorFlow backend is required` 또는 학습 런타임 실패 | `runner.py`, `compare_runner.py` | TensorFlow/의존성 설치 확인, 실행환경 고정 |
| E2E-F006 | Extension Path | `X_mv/y_mv` 미생성, compare payload 누락/실패 | `pipeline.py` multivariate 경로, `compare_runner.py` | 확장 입력/스키마 재검증, 확장 게이트만 보류 후 본선 분리 운영 |

> 운영 메모: 현재 코드는 고정 숫자 exit code보다 예외 기반 실패가 많다. 따라서 CI/운영 스크립트에서 stderr 패턴 + 실패 단계로 E2E-F 코드를 정규화해 기록한다.

---

## 5) 실행 중 준수할 Acceptance Criteria (재확정)

### AC-1. 본선 E2E 성공
- `scripts/run_e2e.sh` 1회 성공(exit=0)
- 본선 필수 산출물 8종 모두 존재

### AC-2. Smoke Gate 통과
- `scripts/smoke_test.sh` 성공
- metrics 필수 키(`mae/rmse/mape/r2`) 검증 통과

### AC-3. run_id 무결성 유지
- run_id 불일치 유도 시 반드시 실패(E2E-F002)
- 일치 run에서는 metrics/preprocessor/meta run_id 동일

### AC-4. 확장 경로 최소 유효성
- covariate 사용 시 `X_mv/y_mv` 및 meta 확장 키 생성
- `compare_runner` 결과 JSON/MD 생성 + winner 계산 가능

### AC-5. 본선/확장 분리 운영
- 확장 실패(E2E-F006)가 본선 성공 경로를 차단하지 않음
- 릴리즈 판정은 "본선 GO, 확장 조건부" 규칙 유지

### AC-6. 실패 추적 가능성
- 실패 시 최소 3종 기록: 실행 커맨드, stdout/stderr, run_id
- 실패 케이스를 E2E-F001~F006 중 하나로 귀속 가능

---

## 6) Immediate Next Actions
1. CI 후처리 단계에 E2E-F 코드 정규화(에러 패턴 매핑) 추가.
2. `smoke_test.sh` 실패 메시지에 E2E-F 코드 직접 출력하도록 개선.
3. 확장 게이트(`run_compare.sh`)를 본선 게이트와 분리된 optional/conditional job으로 운영.

---

## 7) Risks / Open Points
- TensorFlow 의존 환경 차이로 F005 발생 가능성이 높음(로컬/CI 이미지 편차).
- 확장 경로는 PoC 성격이 남아 있어, 입력 스키마 강제 수준(특히 covariate 타입/결측 처리) 추가 고도화 필요.
- 실패코드가 앱 레벨 exit code로 고정되어 있지 않아, 운영 표준화는 CI/스크립트 계층 의존.

---

## 8) Standard Handoff Format

### 8.1 What was verified
- 코드/스크립트 기준으로 본선/확장 E2E 경로 계약, 필수 입출력/아티팩트 계약, run_id 무결성 검증 지점을 재확인했다.
- E2E-F001~F006 실패코드가 현재 구현 신호와 매핑 가능함을 검증했다.

### 8.2 Deliverables
- [x] `docs/E2E_EXECUTION_ARCH_CHECK.md`
- [x] 본선/확장 경로 계약 확인 체크리스트
- [x] 실패코드(E2E-F001~F006) 매핑표
- [x] 실행 중 준수 Acceptance Criteria 재확정

### 8.3 Handoff note
- 본 문서는 “실행 직전 체크” 관점 문서다. 상세 아키텍처/배경은 `docs/E2E_TEST_ARCHITECTURE.md`를 기준으로 참조한다.
- 운영 자동화 시, 본 문서 3~5장을 체크리스트/게이트 기준으로 그대로 전개하면 된다.
