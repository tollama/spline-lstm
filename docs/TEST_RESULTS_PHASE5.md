# TEST_RESULTS_PHASE5

## Standard Handoff Format

### 1) 요청/목표
- 프로젝트: `~/spline-lstm`
- 목표: **Phase 5 확장 PoC 테스트 + 기존 MVP 핵심 경로 회귀 확인**
- 필수 작업:
  1. `tests/test_phase5_extension.py` 작성
  2. 새 확장 경로 smoke 검증
  3. 기존 MVP 핵심 테스트 회귀 확인
  4. 결과 문서화

### 2) 수행 범위
- synthetic data 우선 원칙으로 테스트 설계
- Phase5 확장 경로(전처리 산출물 기반 runner 실행, preprocessor 자동 추론) 테스트 추가
- 기존 MVP 핵심 테스트군(데이터 계약/전처리/학습 runner 계약/아티팩트/run_id 가드) 회귀 실행

### 3) 실행 커맨드
```bash
# A. Phase5 신규 테스트 + MVP 핵심 일부
python3 -m pytest -q \
  tests/test_phase5_extension.py \
  tests/test_phase2_pipeline.py \
  tests/test_preprocessing_pipeline.py \
  tests/test_data_contract.py \
  tests/test_models.py

# B. 추가 회귀(아티팩트/런너 계약/누수/run_id 가드)
python3 -m pytest -q \
  tests/test_artifacts.py \
  tests/test_phase4_run_id_guard.py \
  tests/test_training_runner_cli_contract.py \
  tests/test_training_leakage.py
```

### 4) 결과 요약 (Gate)
- 최종 판정: **PASS**
- blocker: **없음**
- 항목별:
  1. `tests/test_phase5_extension.py` 작성: **완료**
  2. 새 확장 경로 smoke: **PASS**
  3. 기존 MVP 핵심 회귀: **PASS**

### 5) 상세 결과

#### [PASS] 항목 1 — 신규 테스트 파일 작성
- 파일: `tests/test_phase5_extension.py`
- 추가된 테스트:
  - `test_phase5_extension_infers_preprocessor_from_processed_layout`
    - `processed/{run_id}/processed.npz` 기반으로 `models/{run_id}/preprocessor.pkl` 자동 추론 확인
  - `test_phase5_extension_load_series_accepts_raw_target_only_npz`
    - `raw_target`만 포함된 `.npz` 입력 경로 허용 확인
  - `test_phase5_extension_smoke_processed_only_path`
    - synthetic preprocessing -> runner(`--processed-npz`만 전달) smoke 검증

#### [PASS] 항목 2 — 새 확장 경로 smoke
- 핵심 검증 포인트:
  - preprocessor 명시 인자 없이도 runner가 경로를 자동 추론해 실행 성공
  - metrics/report/checkpoint 산출 및 metrics schema(예: `mae`, `rmse`, `mape`, `r2`) 확인

#### [PASS] 항목 3 — 기존 MVP 핵심 테스트 회귀
- 실행 결과 1:
  - `17 passed, 2 skipped` (11.18s)
- 실행 결과 2:
  - `13 passed` (2.22s)
- 총합:
  - **30 passed, 2 skipped**
- skip 사유:
  - 기존 테스트 내부의 환경/백엔드 조건부 skip (비차단)

### 6) 실패 원인 / 재현법
- 이번 검증 실행에서 **실패 케이스는 재현되지 않음**.
- 참고(비차단):
  - 공통 warning: `NotOpenSSLWarning`, `PyparsingDeprecationWarning`
  - 재현: 위 3) 실행 커맨드 그대로 실행 시 동일 warning 확인 가능

### 7) 리스크/메모
- 현재 smoke/회귀 관점에서 blocker 없음.
- 다만 CI 환경 Python/SSL/패키지 버전에 따라 warning 노이즈는 지속될 수 있음(성공/실패 판정 영향 없음).

### 8) 최종 결론
- Phase5 확장 PoC 테스트(신규 경로 + smoke) 및 기존 MVP 핵심 회귀 검증 모두 통과.
- **Phase5 테스트 기준 충족(PASS)**.

### 9) 산출물
- 신규 테스트: `tests/test_phase5_extension.py`
- 결과 문서: `docs/TEST_RESULTS_PHASE5.md`
