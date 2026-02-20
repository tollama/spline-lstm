# PHASE4_ARCH — Spline-LSTM MVP Phase 4 설계 고정

> 기준 문서: `docs/PHASE3_ARCH.md`, `docs/BLUEPRINT.md`  
> 범위: **운영 재현성 / 원클릭 실행 / 복구(runbook) 계약 고정**

---

## 0) 목표와 비목표

### 목표
- 신규 인원이 **한 줄 명령(one-click)** 으로 E2E(전처리→학습/평가) 실행 가능해야 한다.
- run 실패 시 운영자가 **원인-조치-재실행**을 runbook으로 즉시 수행 가능해야 한다.
- model/preprocessor 간 `run_id` 일치 검증을 **운영 게이트**로 강제한다.
- smoke test / health check 규칙을 고정해 배포 전 최소 품질을 보장한다.

### 비목표
- 모델 구조 개선(성능 고도화)
- 분산학습/서빙 인프라 도입
- 대규모 모니터링 스택 구축

---

## 1) Phase 4 운영 아키텍처(고정)

```text
[One-click E2E command]
  ├─ Step A: Preprocess smoke/real input
  │    ├─ artifacts/processed/{run_id}/processed.npz
  │    ├─ artifacts/processed/{run_id}/meta.json
  │    └─ artifacts/models/{run_id}/preprocessor.pkl
  ├─ Step B: Train/Eval runner
  │    ├─ artifacts/checkpoints/{run_id}/best.keras
  │    ├─ artifacts/checkpoints/{run_id}/last.keras
  │    ├─ artifacts/metrics/{run_id}.json
  │    ├─ artifacts/reports/{run_id}.md
  │    └─ artifacts/metadata/{run_id}.json
  └─ Step C: Health check gate
       ├─ 파일 존재/파싱/필수필드 확인
       └─ run_id consistency(model↔preprocessor↔metrics)
```

핵심 규칙:
1. 동일 실행은 단일 `run_id`를 end-to-end로 공유한다.
2. Step C 실패 시 전체 실행은 실패로 간주한다(부분 성공 불인정).
3. 운영 판단은 리포트가 아니라 **체크 규칙 결과(0/비0)** 기준으로 한다.

---

## 2) 원클릭 E2E 실행 계약 (Run Contract)

## 2.1 표준 실행 커맨드 (고정)

기본(합성 데이터 smoke):

```bash
RUN_ID=phase4-smoke-$(date +%Y%m%d-%H%M%S) && \
python3 -m src.preprocessing.smoke \
  --run-id "$RUN_ID" \
  --artifacts-dir artifacts && \
python3 -m src.training.runner \
  --run-id "$RUN_ID" \
  --processed-npz "artifacts/processed/$RUN_ID/processed.npz" \
  --artifacts-dir artifacts \
  --epochs 3 \
  --batch-size 16 \
  --seed 42
```

실데이터 입력 시(전처리 입력 경로만 교체):

```bash
RUN_ID=phase4-real-$(date +%Y%m%d-%H%M%S) && \
python3 -m src.preprocessing.smoke \
  --input data/raw/your_series.csv \
  --run-id "$RUN_ID" \
  --lookback 24 --horizon 1 --scaling standard \
  --artifacts-dir artifacts && \
python3 -m src.training.runner \
  --run-id "$RUN_ID" \
  --processed-npz "artifacts/processed/$RUN_ID/processed.npz" \
  --artifacts-dir artifacts \
  --epochs 10 --batch-size 32 --seed 42
```

## 2.2 입력/출력 계약

### 입력
- `run_id`(필수): 공백/경로 구분자 금지
- 전처리 입력: `--input` CSV/Parquet (생략 시 synthetic)
- 학습 입력: `--processed-npz artifacts/processed/{run_id}/processed.npz`

### 출력(성공 시 필수)
- `artifacts/processed/{run_id}/processed.npz`
- `artifacts/processed/{run_id}/meta.json`
- `artifacts/models/{run_id}/preprocessor.pkl`
- `artifacts/checkpoints/{run_id}/best.keras`
- `artifacts/checkpoints/{run_id}/last.keras`
- `artifacts/metrics/{run_id}.json`
- `artifacts/reports/{run_id}.md`
- `artifacts/metadata/{run_id}.json`

## 2.3 실패 처리 계약 (현재 구현 기준)

현재 `scripts/run_e2e.sh`/`src.training.runner`는 상세 실패 코드 표준을 별도로 매핑하지 않는다.

- 성공: 종료코드 `0`
- 실패: 비0 종료코드(주로 `1`), 상세 원인은 stderr/log 메시지 확인
- 운영 분류는 코드값보다는 실패 메시지(예: run_id mismatch, backend 오류, artifact 누락) 기준으로 수행

---

## 3) model-preprocessor run_id 일치 검증 규칙 (고정)

## 3.1 검증 시점
- 학습 종료 직후(운영 게이트)
- 추론 시작 직전(실행 전 게이트)

## 3.2 검증 규칙
1. 경로 규칙 일치
   - model: `.../models/{run_id}/...` 또는 checkpoint run_id
   - preprocessor: `.../models/{run_id}/preprocessor.pkl`
2. payload 규칙 일치
   - `preprocessor.pkl` 내부 `payload['run_id'] == run_id`
3. metrics 규칙 일치
   - `artifacts/metrics/{run_id}.json` 내부 `run_id == run_id`
4. 불일치 시 runner 예외로 즉시 실패(비0 종료)

## 3.3 운영 권장 구현
- 경로 일치: `Trainer.validate_artifact_run_id_match(...)` 사용
- payload 일치: pickle load 후 `run_id` 키 필수 검사
- metrics 일치: JSON 파싱 후 루트 `run_id` 검사

---

## 4) Smoke Test 규칙 (고정)

## 4.1 목적
- 변경사항이 E2E 실행 계약을 깨지 않았는지 2~5분 내 확인

## 4.2 실행 규칙
- 명령: 2.1의 synthetic one-click 사용
- 파라미터: `epochs<=3`, `seed=42`, 고정 run_id prefix(`phase4-smoke-*`)
- 결과:
  - 종료코드 0
  - 필수 산출물 8종 존재
  - `metrics.run_id == RUN_ID`
  - `rmse` 필드 존재 및 finite 값

## 4.3 실패 판단
아래 중 하나면 smoke 실패(비0 종료):
- 커맨드 비정상 종료
- 필수 산출물 누락
- run_id 불일치
- metrics JSON 파싱 실패

---

## 5) Health Check 규칙 (고정)

## 5.1 체크 항목
1. 파일 시스템
   - artifacts 디렉터리 writable
   - 실행 run_id 경로 중복 오염 없음
2. 아티팩트 무결성
   - processed/meta/preprocessor/checkpoint/metrics/report/metadata 존재
3. 내용 무결성
   - JSON 파싱 가능(`metrics`, `meta`, `metadata`)
   - `metrics` 필수 키: `run_id`, `metrics`, `checkpoints`
4. run_id 일관성
   - 경로 run_id == preprocessor payload run_id == metrics run_id

## 5.2 상태 판정
- PASS: 전 항목 통과(코드 0)
- FAIL: 하나라도 실패(비0 종료)

---

## 6) 최소 운영 절차 연결 (runbook 연계)

운영 절차는 `runbook/README.md`를 단일 기준으로 사용한다.
- 실행(정상 경로)
- 장애 분류(로그 메시지 기반)
- 복구(정리→재실행→검증)
- 증적 보관(실행 커맨드, run_id, 로그 경로)

---

## 7) Acceptance Criteria (Phase 4)

- AC-1: 원클릭 명령 1회로 전처리+학습/평가 완료 가능
- AC-2: 실패 시 비0 종료 + 로그 기반 분류 절차 문서화 완료
- AC-3: run_id 일치 검증 규칙(경로+payload+metrics) 고정
- AC-4: smoke/health 규칙 문서화 및 운영자가 재현 가능
- AC-5: 최소 runbook으로 신규 인원이 30분 내 복구 절차 수행 가능

---

## 8) Standard Handoff Format

### 8.1 Summary
- Phase 4는 운영 관점 계약(원클릭 실행/실패코드/복구/run_id 무결성/smoke-health)을 고정했다.
- “실행 성공”의 정의를 산출물 생성이 아닌 health gate 통과로 상향했다.

### 8.2 Decisions Locked
- One-click E2E 표준 명령 고정(전처리→runner 순차 실행)
- 실패 메시지 분류표 정리(운영 조치 매핑 포함)
- run_id 검증은 경로+payload+metrics 3중 검증으로 고정
- smoke/health를 배포 전 필수 게이트로 고정

### 8.3 Deliverables
- [x] `docs/PHASE4_ARCH.md`
- [x] 원클릭 E2E 실행 계약(커맨드/입력/출력/실패코드)
- [x] model-preprocessor run_id 일치 검증 규칙
- [x] smoke test/health check 규칙
- [x] runbook 최소 절차 연계

### 8.4 Immediate Next Actions
1. (선택) wrapper 단계 상세 실패코드 정규화가 필요하면 별도 구현
2. `scripts/health_check.py` 작성(run_id 3중 검증 포함)
3. CI에 smoke 단계 추가(Phase4 계약 게이트)

### 8.5 Risks / Open Points
- TensorFlow 백엔드 미설치 환경에서 runner 실패 가능(로그 기반 분류 필요)
- 현행 CLI는 종료코드 정규화가 없어 wrapper 구현 전까지 계약 완전 준수 어려움
- `best.keras` 미생성 fallback 로직은 있으나 파일 시스템 오류 시 복구 절차 강제 필요
