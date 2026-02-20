# PHASE 3 REVIEW — GATE C FINAL (Post fixpass)

- Reviewer: `reviewer-spline-mvp-phase3-gate-final`
- Date: 2026-02-18
- Scope: fixpass 반영 후 Gate C 최종 판정
- Project: `~/spline-lstm`

## 1) 검증 목표
- Must fix 2건 해소 여부 확인
  1. naive baseline 대비 성능 이슈
  2. commit hash 메타데이터 누락 이슈
- Must / Should / Nice 재분류
- Gate C PASS/FAIL 판정

---

## 2) 검증 결과 (핵심)

### Must fix #1 — naive baseline 성능
**판정: 미해결 (Must 유지)**

- 실행 테스트:
  - `python3 -m pytest -q tests/test_phase3_repro_baseline.py`
- 실패 근거:
  - `tests/test_phase3_repro_baseline.py::test_phase3_reproducibility_and_baseline_vs_model`
  - `model_rmse=0.258411`, `baseline_rmse=0.083772`, 허용계수 `1.15`
  - 단언식: `rmse1 <= baseline_rmse * 1.15` 불충족
- 코드 근거:
  - 학습 설정이 여전히 짧은 학습 중심(`--epochs 2`)으로 baseline 대비 열위가 재현됨
  - `src/training/runner.py:114-125`

### Must fix #2 — commit hash 메타데이터
**판정: 미해결 (Must 유지)**

- 실행 테스트:
  - `python3 -m pytest -q tests/test_phase3_repro_baseline.py`
- 실패 근거:
  - `tests/test_phase3_repro_baseline.py::test_phase3_metadata_presence_split_config_commit`
  - 에러: `Missing commit hash metadata. Expected one of keys: commit_hash/git_commit/git_sha/commit`
- 코드 근거:
  - run metadata 파일에는 `git_commit`를 생성하나,
    메인 metrics payload 루트에는 commit key를 주입하지 않음
  - `src/utils/repro.py:61-69`
  - `src/training/runner.py:165-187` (payload 루트에 commit 관련 키 없음)

---

## 3) 회귀/테스트 상태 요약
- 실행: `python3 -m pytest -q tests/test_phase3_repro_baseline.py`
- 결과: **2 failed**
  - baseline 성능 비교 실패 1건
  - commit hash 메타데이터 검증 실패 1건

---

## 4) Must / Should / Nice 재분류

## Must fix
1. **M1. baseline 성능 기준 충족**
   - 최소 조건: `test_phase3_reproducibility_and_baseline_vs_model` 통과
   - 모델 RMSE가 naive baseline 허용 범위(1.15x) 이내로 들어오도록 학습/모델 설정 또는 기준 계약 정합 필요
2. **M2. commit hash를 metrics payload 루트에 포함**
   - 허용 키 중 하나(`commit_hash/git_commit/git_sha/commit`)를 `artifacts/metrics/<run_id>.json` 루트에 기록
   - `.git` 부재 환경에서도 포맷 계약(7~40 hex) 만족하도록 fallback 정책 정합 필요

## Should fix
1. commit 정보의 단일 소스화
   - metadata 파일과 metrics payload 간 commit 값 불일치 방지(공통 함수/주입 경로 일원화)
2. baseline 비교 실패 원인 가시화
   - report에 baseline 대비 열위 시 원인 힌트(학습 epoch/모델 용량/seed) 자동 기록

## Nice to have
1. Gate C 스모크 자동화
   - `tests/test_phase3_repro_baseline.py`를 CI 필수 게이트로 승격
2. commit 수집 실패 정책 문서화
   - git 미존재/Detached 환경에서의 표준 처리 규칙 명시

---

## 5) Gate C 최종 판정
- **Must fix 개수: 2**
- **Gate C: FAIL**

판정 규칙(“Must fix = 0이면 PASS”) 미충족.

---

## 6) 실행 로그 요약
1. Phase 3 최종 게이트 대상 테스트 재실행
   - `python3 -m pytest -q tests/test_phase3_repro_baseline.py`
2. Must fix #1 재검증
   - naive baseline 대비 성능 실패 재현
3. Must fix #2 재검증
   - commit hash 메타데이터 루트 키 누락 재현
4. 결론
   - fixpass 반영 기준에서도 Must fix 2건 잔존 → Gate C FAIL
