# TEST_RESULTS_PHASE3_FIXPASS

## Standard Handoff Format

### 1) 요청/목표
- 프로젝트: `~/spline-lstm`
- 검증 목표 (Must fix 2건 해소 여부)
  1. baseline 비교 테스트 PASS
  2. metrics payload 내 commit hash 메타데이터 존재 + 정책 일치
  3. phase3 테스트 스위트 회귀 여부
- 조건: synthetic data 우선

### 2) 수행 범위
- synthetic 기반 phase3 검증 테스트 실행
- 전체 pytest 회귀 실행으로 phase3 변경 영향 확인
- metrics payload/metadata 산출물 직접 확인

### 3) 실행 커맨드
```bash
# 1) phase3 핵심 검증(베이스라인/메타데이터)
python3 -m pytest -q tests/test_phase3_repro_baseline.py

# 2) 전체 회귀 확인
python3 -m pytest -q

# 3) payload 직접 확인용 synthetic run
mkdir -p /tmp/phase3fix
python3 -m src.training.runner \
  --run-id phase3-fixpass-check \
  --epochs 2 --batch-size 16 --sequence-length 24 --horizon 1 \
  --test-size 0.2 --val-size 0.2 \
  --synthetic --synthetic-samples 360 --synthetic-noise 0.06 \
  --seed 123 --verbose 0 \
  --artifacts-dir /tmp/phase3fix/artifacts \
  --checkpoints-dir /tmp/phase3fix/checkpoints

# 4) commit hash 정책 확인
git rev-parse --short HEAD
```

### 4) 결과 요약
- 전체 판정: **FAIL (Must fix 2건 미해소)**
- 세부:
  1. baseline 비교 테스트: **FAIL**
  2. metrics payload commit hash 메타데이터: **FAIL**
  3. phase3 스위트 회귀: **FAIL (동일 2건 지속)**

### 5) 테스트 상세 결과
#### [FAIL] 항목 1 — baseline 비교 테스트
- 테스트: `tests/test_phase3_repro_baseline.py::test_phase3_reproducibility_and_baseline_vs_model`
- 실패 메시지:
  - `Model did not beat/track naive baseline within tolerance.`
  - `model_rmse=0.258411, baseline_rmse=0.083772, allowed_factor=1.15`
- 해석:
  - synthetic 조건에서 현재 LSTM이 naive persistence baseline 대비 크게 열위
  - 허용 기준(`model <= baseline * 1.15`) 미충족

#### [FAIL] 항목 2 — commit hash 메타데이터 정책
- 테스트: `tests/test_phase3_repro_baseline.py::test_phase3_metadata_presence_split_config_commit`
- 실패 메시지:
  - `Missing commit hash metadata. Expected one of keys: commit_hash/git_commit/git_sha/commit`
- payload 확인 결과 (`/tmp/phase3fix/artifacts/metrics/phase3-fixpass-check.json`):
  - `split_indices`: 존재 (PASS)
  - `config`: 존재 (PASS)
  - `commit_hash/git_commit/git_sha/commit` top-level 키: **부재 (FAIL)**
- metadata 파일 확인 (`/tmp/phase3fix/artifacts/metadata/phase3-fixpass-check.json`):
  - `git_commit: null`
- 정책 일치성:
  - 테스트 정책은 7~40자리 hex commit hash를 요구
  - 현재 산출물은 commit hash 미기록/null 상태로 불일치

#### [FAIL] 항목 3 — phase3 회귀 여부
- 실행: `python3 -m pytest -q`
- 결과: `2 failed, 27 passed, 2 skipped`
- 실패 테스트는 phase3 Must fix 2건과 동일:
  - `test_phase3_reproducibility_and_baseline_vs_model`
  - `test_phase3_metadata_presence_split_config_commit`

### 6) 실패 원인 정리
1. **Baseline 성능 미충족**
   - 현재 phase3 test 조건(epochs=2, synthetic split)에서 LSTM RMSE가 naive baseline보다 크게 나쁨
2. **Commit hash 주입/스키마 미충족**
   - metrics payload top-level에 허용 키(`commit_hash/git_commit/git_sha/commit`) 없음
   - 별도 metadata 파일의 `git_commit`도 null
   - 저장소 환경에서 `git rev-parse --short HEAD` 실행 시 `not a git repository` 확인됨

### 7) 산출물
- 본 문서: `docs/TEST_RESULTS_PHASE3_FIXPASS.md`
- 참고 실행 산출물:
  - `/tmp/phase3fix/artifacts/metrics/phase3-fixpass-check.json`
  - `/tmp/phase3fix/artifacts/metadata/phase3-fixpass-check.json`

### 8) 권장 후속 조치
1. baseline 게이트 충족을 위한 학습/모델 설정 조정 후 재검증
2. metrics payload에 commit hash 정책 키를 명시적으로 반영하고, git 미존재 환경 fallback 정책(예: 테스트/정책 합의)을 확정
3. 아래 커맨드 green 확인 시 FixPass 종료:
   - `python3 -m pytest -q tests/test_phase3_repro_baseline.py`
   - `python3 -m pytest -q`

### 9) 인수인계 메모
- 모든 검증은 synthetic 데이터 조건으로 수행
- 현 시점 기준 Must fix 2건 모두 해소되지 않음
