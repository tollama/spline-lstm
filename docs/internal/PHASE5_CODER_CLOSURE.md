# PHASE5_CODER_CLOSURE

## 1) Summary
- Phase5 최종 클로저 목표(ARCH ↔ runner 계약 정합)를 위해 **최소 수정**으로 계약 누락 1건(`export_formats` 유효성)을 코드에 보완했습니다.
- `docs/PHASE5_ARCH.md`를 현재 구현 상태와 1:1로 맞추도록 문구를 정정했습니다.
- 계약 검증 테스트(기존 + 최소 추가) 포함 전체 테스트를 재실행하여 통과를 확인했습니다.

## 2) What I changed
### 2.1 `src/training/runner.py`
- 추가: `_parse_export_formats(raw)`
  - 허용값: `none | onnx | tflite | onnx,tflite`
  - 빈값/None → `["none"]`
  - `none`과 타 포맷 동시 지정 금지
  - 중복 제거 및 순서 보존
- 반영: `run()`에서 `args.export_formats`를 검증/정규화 후 config snapshot에 기록
  - 기존: 문자열 그대로 저장
  - 변경: 정규화된 list 저장 (`["none"]`, `["onnx", "tflite"]` 등)

### 2.2 `docs/PHASE5_ARCH.md`
- `--export-formats` 계약 문구를 실제 구현과 정합화:
  - runner에서 값 유효성 검증 수행
  - config snapshot 기록까지만 지원
  - 실제 ONNX/TFLite export 실행은 미구현
- 호환성 메모에 `export_formats`가 정규화된 list로 저장됨을 명시

### 2.3 테스트
- 수정: `tests/test_phase5_runner_contract_alignment.py`
  - `_parse_export_formats` 계약 검증 테스트 추가
    - 정상 케이스: None/빈값/단일/복수/중복
    - 실패 케이스: `none,onnx`, `coreml`

## 3) Validation
- 실행: `python3 -m pytest -q`
- 결과: `43 passed, 2 skipped`

## 4) Contract alignment status (ARCH vs runner)
- Covariate usage: specify `--covariate-spec` to include dynamic/static covariates; these are preprocessed into X_mv/y_mv, stored in processed.npz, and referenced in run_id metadata with `covariate_cols`, `X_mv_shape`, `y_mv_shape`.
- `processed.npz` 로딩 우선순위(`X/y` → `X_mv/y_mv` → legacy series): 구현/테스트 정합 ✅
- `run_id` 무결성 검증(processed/meta/preprocessor): 구현/테스트 정합 ✅
- `export_formats` 값 계약: 이번 수정으로 정합 ✅
  - 단, export 실행 자체는 아직 PoC 범위(별도 스크립트/후속 작업)로 유지

## 5) Changed files
- `src/training/runner.py`
- `tests/test_phase5_runner_contract_alignment.py`
- `docs/PHASE5_ARCH.md`
- `docs/PHASE5_CODER_CLOSURE.md` (신규)

## 6) Risks / Notes
- 이번 변경으로 `config.export_formats` 타입이 문자열에서 list로 정규화되었습니다.
  - 현재 테스트/러너 동작에는 영향 없음
  - 외부 소비자가 문자열을 가정했다면 list 처리로 맞춰야 합니다.

## 7) Immediate next (optional)
- 실제 export(onnx/tflite) 실행 경로를 runner 혹은 별도 스크립트로 고정하고,
  parity/latency/size 게이트를 자동 검증하도록 연결하면 Phase5 문서의 Edge PoC 섹션까지 완전 폐쇄 가능합니다.
