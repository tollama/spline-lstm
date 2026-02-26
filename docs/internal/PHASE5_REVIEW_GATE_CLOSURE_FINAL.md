# PHASE5_REVIEW_GATE_CLOSURE_FINAL — Gate C 최종 종료 판정

## 1) Summary
- 프로젝트: `~/spline-lstm`
- 목적: mustfix-final 반영 이후 Gate C 종료 가능 여부 최종 판정
- 검토 입력:
  - `docs/PHASE5_ARCH.md`
  - coder 변경사항(코드/스크립트/산출물)
  - 테스트 결과 문서
- 참고: 요청된 `docs/TEST_RESULTS_PHASE5_MUSTFIX_FINAL.md` 파일은 저장소에 없어서, 최신 게이트 결과 문서 `docs/TEST_RESULTS_PHASE5_GATE_FINAL.md`를 대체 근거로 사용함.

---

## 2) Evidence Snapshot

### A. 아키텍처 계약(Phase5 ARCH)
`docs/PHASE5_ARCH.md`는 다음 핵심 계약을 명시:
- 러너 확장 인자: `--model-type`, `--feature-mode`, `--target-cols`, `--covariate-spec`
- 입출력 계약: `X=[B,L,F_total]`, `y=[B,H*F_target]`
- 산출물 확장 키: `feature_names`, `target_indices` 등

### B. 실제 코드 반영 상태
- `src/models/lstm.py`
  - ✅ `input_features` 일반화 반영
  - ✅ `GRUModel` 추가 반영
- `src/training/compare_runner.py`
  - ✅ LSTM/GRU 비교 PoC 경로 존재
  - ⚠️ `input_features=1` 고정(univariate 중심)
- `src/preprocessing/pipeline.py`
  - ✅ `X_mv`, `y_mv`, `features_scaled` 생성/저장 PoC 반영
- `src/training/runner.py`
  - ❌ `--model-type`, `--feature-mode`, `--target-cols`, `--covariate-spec` 미구현
  - ❌ 확장 입력 계약 기반 통합 러너 분기 부재

### C. 테스트/실행 증빙
- `docs/TEST_RESULTS_PHASE5_GATE_FINAL.md`:
  - 신규 확장 테스트 PASS
  - MVP 회귀 테스트 PASS
  - `run_compare.sh` smoke PASS
- `artifacts/comparisons/phase5-gate-final-smoke.json` 생성 확인

해석:
- 테스트 스모크/회귀 안정성은 긍정적이나,
- **Gate C 차단 Must 항목(ARCH-Runner 정합성)**은 여전히 해소되지 않음.

---

## 3) Must / Should / Nice

### Must fix (Gate 차단)
1. **`runner.py`의 ARCH 계약 정합화**
   - 문서 계약 인자(`--model-type`, `--feature-mode`, `--target-cols`, `--covariate-spec`)를 `src/training/runner.py`에 반영
   - 단일 LSTM 경로를 모델 타입/feature mode 분기 가능한 구조로 확장

### Should fix
1. `compare_runner`의 multivariate(`F_total>1`) 직접 수용
2. `processed.npz`에 `feature_names`, `target_indices` 저장(ARCH 계약 일치)
3. 테스트 결과 문서에 “ARCH 계약 대비 구현 커버리지” 섹션 추가

### Nice to have
1. Phase5 전용 CI 게이트(compare + multivariate smoke + core regression)
2. 환경 warning(SSL/pyparsing/TensorFlow runtime warning) 정리 가이드 추가

---

## 4) Gate C 최종 판정
- 판정 규칙: **Must fix = 0 이면 PASS**
- 현재 상태: **Must fix 1건**

## ✅/❌ Decision: **Gate C = FAIL**

---

## 5) 최종 한 줄 판정
**핵심 테스트는 통과했지만 ARCH-Runner 계약 불일치(Must 1건) 미해소로 Gate C는 최종 FAIL입니다.**
