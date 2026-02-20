# Spline-LSTM Runbook (Phase 4)

Related docs:
- Project overview: `../README.md`
- GUI/backend production cutover checklist: `./GUI_PROD_CUTOVER_CHECKLIST.md`
- Operator quick map: `../OPERATIONS_QUICKSTART.md`
- Release gate checklist (cutover): `../RELEASE_CHECKLIST.md`
- GUI production hardening closeout: `./GUI_PROD_HARDENING_CLOSEOUT.md`

## 1) 목적
운영/안정화 관점에서 **일관된 run_id 기반 E2E 실행**과 **실패 시 즉시 차단**을 보장한다.

## 2) 표준 실행 절차

빠른 운영 명령 맵은 `../OPERATIONS_QUICKSTART.md`를 참고.


### A. 원클릭 E2E
```bash
bash scripts/run_e2e.sh
```

옵션 예시:
```bash
RUN_ID=phase4-prod-001 EPOCHS=2 LOOKBACK=24 HORIZON=1 bash scripts/run_e2e.sh
```

### B. 스모크 테스트 게이트
```bash
bash scripts/smoke_test.sh
```

## 3) 산출물 위치 (run_id 스코프)
- 전처리: `artifacts/processed/{run_id}/processed.npz`
- 전처리 메타: `artifacts/processed/{run_id}/meta.json`
- 전처리 객체: `artifacts/models/{run_id}/preprocessor.pkl`
- 체크포인트: `artifacts/checkpoints/{run_id}/best.keras`, `last.keras`
- 지표: `artifacts/metrics/{run_id}.json`
- 리포트: `artifacts/reports/{run_id}.md`

## 4) 자동 차단 정책 (run_id mismatch)
`python3 -m src.training.runner` 실행 시 아래가 불일치하면 즉시 실패:
1. CLI `--run-id`
2. `--processed-npz` 경로에서 추출된 run_id (`.../processed/{run_id}/processed.npz`)
3. `processed.npz` 옆 `meta.json`의 `run_id`
4. `--preprocessor-pkl` 내부 payload `run_id` (또는 추론된 preprocessor)

## 5) 지표 용어/키 기준
표시 용어(문서): **MAE, MSE, RMSE, robust MAPE, R2**

현재 `src.training.runner` metrics JSON 키:
- `metrics.mae`
- `metrics.mse`
- `metrics.rmse`
- `metrics.mape` (robust MAPE 구현)
- `metrics.r2`

> 참고: `MASE`는 runner payload에도 포함된다(`metrics.mase`).

## 6) 실패 처리 표준 (Day 3)
- 성공: 종료코드 `0`
- 실패: **표준 error payload(JSON) + 표준 종료코드**
- stderr 템플릿(예):
```json
{"ok": false, "exit_code": 22, "error": {"code": "ARTIFACT_CONTRACT_ERROR", "message": "...", "type": "ValueError"}}
```

### 6.1 종료코드/오류코드 매핑
| exit_code | error.code | 대표 실패 조건 |
|---|---|---|
| 21 | `FILE_NOT_FOUND` | 입력 파일/아티팩트 경로 미존재 |
| 22 | `ARTIFACT_CONTRACT_ERROR` | `processed.npz` 키 누락(`feature_names`,`target_indices`), `split_contract.json` 누락/스키마 불일치, 아티팩트 레이아웃 위반 |
| 23 | `INPUT_SHAPE_ERROR` | X/y shape/배치 불일치 |
| 26 | `INSUFFICIENT_DATA_ERROR` | split 이후 학습/검증/테스트 윈도 부족 |
| 27 | `RUN_ID_MISMATCH` | run_id 계약 불일치 |
| 24 | `RUNNER_EXEC_ERROR` | 기타 런타임 실패(backend 포함) |

### 6.2 소비(consume) 경로 artifact 계약
`--processed-npz` 사용 시 runner는 아래를 fail-fast 검증:
1. `processed.npz` 필수 키: `feature_names`, `target_indices`
2. artifacts 표준 경로(`.../processed/{run_id}/processed.npz`)일 경우 `split_contract.json` 존재
3. `split_contract.json.schema_version == "phase1.split_contract.v1"`

### 6.3 Covariate spec 계약 (`--covariate-spec`, optional)
기본 동작은 **backward-compatible** 이다.
- `--covariate-spec` 미사용 시: 기존 경로 유지(선언된 covariate만 사용, spec 강제 없음)

`--covariate-spec` 사용 시(`schema_version=covariate_spec.v1`) 아래를 fail-fast 검증:
1. 루트 타입
   - JSON object
   - `schema_version == "covariate_spec.v1"`
   - `dynamic_covariates/static_covariates`는 list(생략 가능)
   - `imputation_policy`는 object(생략 가능)
2. covariate item 타입
   - 각 item은 object
   - `name`: non-empty string
   - `type`: `numeric|categorical|boolean`
   - `required`: boolean
3. 이름 규칙
   - 그룹 내 중복 금지
   - dynamic/static 간 overlap 금지
4. 선언 정합성
   - `required=true` 항목은 CLI/config 선언(dynamic/static)에서 누락 금지
   - CLI/config 선언 covariate는 spec에 반드시 존재
5. 데이터셋 정합성
   - dynamic covariate는 실제 입력 컬럼에 존재해야 함

운영자용 오류 메시지는 누락/미정의 항목과 함께 declared/spec/available 컬럼 스냅샷을 포함해 즉시 조치 가능하도록 고정.

## 7) 장애 대응
- `run_id mismatch` 발생 시:
  1) 입력 인자 `--run-id` 확인
  2) `processed.npz` 경로 run_id 확인
  3) `meta.json` run_id 확인
  4) `preprocessor.pkl` 생성 run_id 확인
- 동일 run_id로 preprocessing부터 재생성 권장:
```bash
python3 -m src.preprocessing.smoke --run-id <RUN_ID>
```

## 7) 최소 운영 점검 체크리스트
- [ ] E2E 명령 1회 성공
- [ ] metrics/report/checkpoint/preprocessor 생성 확인
- [ ] metrics JSON 내 주요 키(`mae/mse/rmse/mape/r2`) 확인
- [ ] run_id mismatch 테스트(의도적 불일치) 시 실패 확인

## 8) Backend API 보안 기본값 (GUI backend)

### 8.1 인증 모드
- `SPLINE_DEV_MODE=1` (기본 dev): API 인증 **선택**(backward-compatible)
- `SPLINE_DEV_MODE=0` (prod-like): API 인증 **필수**
  - `SPLINE_API_TOKEN` 미설정 시 서버 시작 실패(fail-closed)
  - 보호 엔드포인트 호출 시 헤더 필요: `X-API-Token: <SPLINE_API_TOKEN>`

헬스체크(`/api/v1/health`)는 무인증으로 유지.

### 8.2 CORS / Host / 기본 헤더
- CORS 허용 origin: `SPLINE_CORS_ORIGINS`(comma-separated)
  - dev 기본: `http://localhost,http://127.0.0.1,http://localhost:3000,http://127.0.0.1:3000`
  - prod 권장: 운영 UI 도메인만 명시
- Trusted hosts: `SPLINE_TRUSTED_HOSTS` (기본 `localhost,127.0.0.1,testserver`)
- 기본 보안 헤더 자동 추가:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: no-referrer`
  - `Cache-Control: no-store`

### 8.3 오류 응답 정책
- 내부 예외(5xx): 클라이언트에는 `{"ok": false, "error": "internal server error"}`만 반환
- 상세 스택/민감정보는 서버 로그에만 기록

## 9) 현재 상태 (Phase 매핑)
- Phase 1: 전처리 파이프라인(스키마/스플라인/스케일/윈도잉) 운영 가능
- Phase 2: 학습/평가 기본 플로우 및 아티팩트 저장 적용
- Phase 3: 단일 CLI runner(`src.training.runner`) 운영 가능
- Phase 4: E2E 스크립트 + 스모크 게이트 + run_id 불일치 차단 적용
- Phase 5(PoC): GRU 비교 및 covariate/multivariate 전처리 경로 제공
