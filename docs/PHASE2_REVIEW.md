# PHASE 2 Review (Gate C)

## Summary
- Phase 2 코드/설계는 전반적으로 개선되었지만, **데이터 누수 가능 경로 1건(Must)** 이 남아 있어 Gate C는 **FAIL**입니다.

## Changed Files
- `docs/PHASE2_REVIEW.md`

## Commands Run
```bash
cd ~/spline-lstm
python3 -m pytest -q
rg -n "seed|random|np\.random|tf\.random|torch\.manual_seed|determin" src examples tests
```

## Output / Evidence
- 테스트 결과: `20 passed, 2 skipped` (회귀/계약 테스트는 통과)
- 핵심 근거 코드:
  - 누수 관련: `src/preprocessing/pipeline.py:74-78`
  - Trainer 누수 방지 구현: `src/training/trainer.py:184-190`, `204-213`
  - shape 계약 검증: `src/models/lstm.py:43-61`, `tests/test_data_contract.py`
  - run_id 무결성 검증(경로 기반): `src/training/trainer.py:302-317`, `tests/test_artifacts.py`

---

## 1) Must / Should / Nice 분류

### Must fix
1. **전처리 파이프라인의 split 이전 스케일 fit (데이터 누수 위험)**
   - 근거: `run_preprocessing_pipeline()`에서 전체 시계열(`series_smooth`)에 대해 `scaler.fit()` 후 window 생성
     - `src/preprocessing/pipeline.py:74-78`
   - 리스크:
     - 이 산출물(`processed.npz`)을 학습에 직접 사용하면 train/test 경계를 넘는 통계가 유입될 수 있음.
   - 권고:
     - 학습용 파이프라인에서는 반드시 `chronological split -> train에만 fit -> val/test transform` 순서 강제.
     - `pipeline.py`를 "학습 전용(누수-안전)"과 "전체 데이터 전처리(배치 추론용)"로 명시 분리하거나, split 인자를 받아 누수-안전 모드 제공.

### Should fix
1. **재현성 제어(Seed/Determinism) 미흡**
   - 근거:
     - `Trainer`/`LSTMModel`에서 numpy/tensorflow/torch seed 고정 API 부재.
     - 예제/스모크에서 랜덤 생성 사용(`examples/train_example.py`, `src/preprocessing/smoke.py`)하나 seed 고정 없음.
   - 권고:
     - 전역 `set_seed(seed)` 유틸 추가(np/tf/torch), 실행 config/아티팩트에 seed 기록.

2. **체크포인트 무결성 검증이 경로 규칙 수준에 한정**
   - 근거:
     - `validate_artifact_run_id_match()`는 경로 내 run_id 일치만 확인 (`src/training/trainer.py:302-317`).
     - 모델-전처리기 내용 일치(해시, 스키마 버전, config fingerprint) 검증 없음.
   - 권고:
     - `meta.json` 또는 별도 manifest에 파일 해시(SHA256), schema_version, config hash를 저장/검증.

3. **horizon-output 계약의 사전검증 부재**
   - 현황:
     - 모델 레벨 `_validate_xy`에서 mismatch를 탐지해 fail-fast는 가능.
   - 보완:
     - `Trainer.train()` 시작 시 `prediction_horizon`과 `model.output_units` 계약을 명시 점검하여 오류 메시지 명확화.

### Nice to have
1. **config 파일 확장자/포맷 일치화**
   - 근거: `config_path`는 `.yaml`인데 실제 저장은 `json.dump` 사용 (`src/training/trainer.py:276-288`).
   - 권고: `.json`으로 변경하거나 실제 YAML serializer 사용.

2. **아티팩트 저장 시 UTF-8/스키마 버전 필드 통일**
   - 장기 유지보수성과 파서 호환성 개선.

---

## 2) 체크리스트 결과 (요청 항목별)

### A. 데이터 누수 점검
- **부분 통과 / 미해결 1건**
- `Trainer.train()`은 split 후 train-fit 정규화로 안전 (`src/training/trainer.py:184-190`).
- 그러나 `preprocessing.pipeline` 경로는 전체 데이터 fit 수행(위 Must).

### B. Shape 계약 점검
- **통과(현행 기준)**
- `make_windows`/`to_supervised`/`LSTMModel._validate_xy`가 입력/출력 shape를 강하게 검증.
- 관련 테스트 통과: `tests/test_data_contract.py`.

### C. 재현성 점검
- **미흡 (Should)**
- 고정 seed, deterministic 옵션, 런타임 환경 캡처(라이브러리 버전/백엔드) 체계가 문서/코드에서 일관되게 제공되지 않음.

### D. 체크포인트 무결성 점검
- **기본 통과 + 보강 필요 (Should)**
- run_id 경로 일치성 검증은 존재/테스트됨.
- 내용 무결성(해시/서명/manifest) 검증은 부재.

---

## 3) Gate C Decision
- **Must fix 잔여: 1건**
- **Gate C: FAIL**
- 판정 기준: Must fix = 0 일 때만 PASS

## 4) Risks / Known Issues
- 전처리 파이프라인 산출물을 학습 데이터로 재사용 시, 실수로 누수된 스케일 통계를 사용할 가능성.
- 실험 재실행 시 결과 변동(특히 초기화/노이즈 데이터 생성 구간)으로 디버깅/회귀판정 비용 증가.

## 5) Next Input for Next Role (Coder Fix Pass)
1. `src/preprocessing/pipeline.py`에 누수-안전 모드 추가(분할 후 train-fit scaler 강제) 또는 학습 경로 분리.
2. `src/training` 또는 `src/utils`에 `set_seed(seed, deterministic=False)` 도입 + config 기록.
3. 아티팩트 manifest(`run_id`, file hashes, schema_version, config hash) 저장/검증 로직 추가.
4. `Trainer.train()`에서 horizon-output 계약 사전 검증 및 명확한 에러 메시지 제공.
5. 수정 후 `python3 -m pytest -q` 및 누수/무결성 회귀 테스트 추가 제출.
