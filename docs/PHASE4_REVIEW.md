# PHASE 4 REVIEW — 운영 안정성/재현성/실행문서 품질 (Gate C)

- Reviewer: `reviewer-spline-mvp-phase4`
- Date: 2026-02-18
- Scope: `~/spline-lstm` MVP Phase 4 운영 관점 리뷰
- Goal: 원클릭 실행 재현성 / run_id 무결성 / 실패 복구 절차 명확성 점검

---

## 1) 요청/검토 기준

필수 검토 포인트:
1. 원클릭 실행 재현성
2. run_id 무결성 검증
3. 실패 시 복구 절차 명확성

판정 규칙:
- **Must fix = 0 이면 Gate C PASS**

---

## 2) 수행 내역 (증빙 커맨드 + 결과)

### A. 회귀/계약 테스트 검증
- 실행:
  - `python3 -m pytest -q tests/test_training_runner_cli_contract.py tests/test_artifacts.py tests/test_phase3_repro_baseline.py`
- 결과:
  - **11 passed**
- 해석:
  - runner CLI 계약(legacy 포함), artifact/run_id 규칙, 재현성/metadata baseline 계약이 현재 코드 기준 통과.

### B. 원클릭 실행 재현성 스모크
- 실행 1:
  - `python3 -m src.training.runner --run-id phase4-review-a --epochs 5 --batch-size 16 --sequence-length 24 --horizon 1 --test-size 0.2 --val-size 0.2 --synthetic --synthetic-samples 360 --synthetic-noise 0.06 --seed 123 --learning-rate 0.003 --verbose 0 --artifacts-dir artifacts --checkpoints-dir checkpoints`
- 실행 2(동일 config, run_id만 변경):
  - `python3 -m src.training.runner --run-id phase4-review-b ...동일 옵션...`
- 결과:
  - 두 실행 모두 성공
  - `rmse` 동일값 확인: `0.11519002169370651`
  - metrics/baseline/report/checkpoint 산출물 생성 확인
- 해석:
  - 단일 커맨드 재실행 재현성(동일 seed/config)이 현재 환경에서 확보됨.

### C. run_id 무결성 fail-fast 검증
- 준비:
  - `python3 -m src.preprocessing.smoke --run-id phase4-prep-a --artifacts-dir artifacts`
- 불일치 시나리오 실행:
  - `python3 -m src.training.runner --run-id phase4-train-b --processed-npz artifacts/processed/phase4-prep-a/processed.npz --epochs 1 --verbose 0`
- 결과:
  - `ValueError: run_id mismatch: cli run_id=phase4-train-b but processed artifact path run_id=phase4-prep-a`
- 해석:
  - run_id 불일치 시 즉시 실패(fail-fast) 동작 정상.

### D. 실행문서/복구문서 점검
- 점검 대상:
  - `README.md`, `docs/PHASE2_ARCH.md`, `docs/PHASE3_*`
- 결과:
  - 실행 커맨드 예시는 분산되어 존재
  - 실패 유형별 **운영자 복구 절차(runbook)**가 한 문서로 정리되어 있지 않음
  - 예: `run_id mismatch`, backend 미설치, checkpoint 손상, artifact partial write에 대한 단계별 대응 절차 부재

---

## 3) 항목별 판정

### 3-1) 원클릭 실행 재현성
**판정: 충족 (Closed)**
- 근거: runner 단일 커맨드 2회 재실행 성공 + 동일 seed/config에서 동일 RMSE 확인.

### 3-2) run_id 무결성 검증
**판정: 충족 (Closed)**
- 근거: 테스트 스위트 통과 + 실측 mismatch 시 즉시 예외 발생 확인.

### 3-3) 실패 시 복구 절차 명확성
**판정: 부분 충족 (Open-Doc)**
- 근거: 오류 탐지/실패 자체는 구현되어 있으나, 운영 복구 절차 문서가 분산/부재.

---

## 4) Must / Should / Nice

## Must fix
- 없음 (**0건**)

## Should fix
1. **운영 복구 Runbook 문서 신설** (`docs/RUNBOOK.md` 권장)
   - 최소 포함:
     - 증상별 트러블슈팅(backend 미설치, run_id mismatch, artifact 누락/손상)
     - 진단 커맨드
     - 복구 커맨드(재실행/정리/검증)
     - 재발 방지 체크리스트
2. **원클릭 표준 실행 경로 단일화**
   - README에 “표준 1개 커맨드 + 기대 산출물 + 성공/실패 판정 기준”을 명시하고, 상세는 runbook으로 링크.
3. **비정상 종료 후 정합성 체크 절차 추가**
   - checkpoints/metrics/config/metadata 4종 일관성 검증 커맨드 제공 권장.

## Nice to have
1. `make smoke-run` 또는 `scripts/run_smoke.sh` 제공으로 명령 길이 축소
2. CI에서 runbook 커맨드 샘플 정합성(문서-실행 동기화) 점검
3. TensorFlow 경고/환경 의존 메시지에 대한 FAQ 섹션 추가

---

## 5) Gate C 판정

- **Must fix 개수: 0**
- **Gate C: PASS**

판정 규칙(“Must fix=0이면 PASS”) 충족.

---

## 6) Standard Handoff

### Summary
- Phase 4 검토 범위(운영 안정성/재현성/실행문서 품질) 점검 완료.
- 코드/테스트 기준 핵심 운영 기능(원클릭 실행, run_id 무결성)은 충족.
- 복구 절차 문서화는 개선 필요(Should).

### Evidence
- 테스트: `11 passed`
- 재현 실행: `phase4-review-a`, `phase4-review-b`
- run_id mismatch fail-fast: `phase4-prep-a` vs `phase4-train-b` 시나리오 재현

### Risks
- 현재 리스크는 코드 결함보다 **운영 문서 부재 리스크(인수인계/장애 대응 속도 저하)**에 집중.

### Next Actions
1. `docs/RUNBOOK.md` 작성 (복구 절차 표준화)
2. README “원클릭 실행” 섹션을 단일 기준으로 정리
3. 정합성 체크 커맨드(artifact consistency) 운영 절차 추가

### Final Decision
- **Gate C PASS** (Must fix 0)
