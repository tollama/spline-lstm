# PHASE 1 리뷰 (Spline-LSTM MVP)

## 범위
- 코드/설계 정적 리뷰: `src/preprocessing/spline.py`, `src/models/lstm.py`, `src/training/trainer.py`, `examples/train_example.py`, `tests/test_models.py`
- 중점 점검: 데이터 누수, shape 일치, 재현성, 파일 로딩 보안

## 결론
- **Must fix 0 여부: 아니오 (Must fix 3건 존재)**

---

## Must fix

1) **정규화 데이터 누수 (Train/Test 분리 이전 전체 데이터로 스케일 계산)**
- 위치: `src/training/trainer.py:155-161`, `78-95`
- 문제: `train()`에서 `normalize(data)`를 전체 시계열에 먼저 적용한 뒤 split 수행.
- 영향: 테스트 구간 통계(min/max, mean/std)가 학습에 유입되어 성능 과대평가 가능.
- 권장 수정:
  - 순서를 `create_sequences -> train_test_split -> train 통계로 fit -> train/test transform`으로 변경
  - 스케일 파라미터는 train 기준만 저장

2) **시계열 검증 누수 가능성 (Keras `validation_split` + 기본 `shuffle=True`)**
- 위치: `src/models/lstm.py:117-125`
- 문제: `model.fit(... validation_split=0.2)` 사용 시 기본 shuffle로 시간 순서가 섞여 미래 정보가 validation에 혼입될 수 있음.
- 영향: early stopping/val_loss 기준이 비현실적으로 좋아짐.
- 권장 수정:
  - `shuffle=False` 명시
  - 또는 Trainer에서 시간순 `X_val, y_val`을 분리해 `validation_data=(X_val, y_val)` 전달

3) **예측 horizon과 모델 output_units 계약 불일치 위험**
- 위치: `src/training/trainer.py:58`, `src/models/lstm.py:64-67`
- 문제: Trainer는 `y`를 `[batch, horizon*features]`로 생성하지만, 모델 기본 `output_units=1`.
- 영향: `prediction_horizon>1` 설정 시 shape mismatch로 학습 실패(런타임 오류).
- 권장 수정:
  - Trainer 초기화 시 `model.output_units == prediction_horizon * n_features` 강제 검증
  - MVP 범위라면 `prediction_horizon=1`만 허용하도록 명시적 assert

---

## Should fix

1) **재현성 미흡 (seed/deterministic 설정 없음)**
- 위치: 전반 (`examples/train_example.py`, `tests/test_models.py`, training/model 전역)
- 문제: numpy/tensorflow seed 고정이 없어 실행마다 결과 변동.
- 권장: `numpy`, `python random`, `tf.random.set_seed` + 가능 시 deterministic 옵션 추가.

2) **설정 파일 확장자/내용 불일치**
- 위치: `src/training/trainer.py:232-244`
- 문제: `config_path`는 `.yaml`인데 실제 저장은 `json.dump`.
- 영향: 운영 혼선/도구 호환성 저하.
- 권장: 확장자를 `.json`으로 변경하거나 YAML 직렬화 사용.

3) **검증 데이터 분리 정책이 Trainer 레벨에서 불명확**
- 위치: `src/training/trainer.py`, `src/models/lstm.py`
- 문제: test split은 Trainer, val split은 Model 내부에서 수행되어 정책이 분산됨.
- 권장: split 책임을 Trainer로 일원화.

---

## Nice to have

1) **파일 로딩 보안 가드 강화**
- 위치: `src/models/lstm.py:150-153`, `src/training/trainer.py:275-277`
- 현황: `load(path)`는 임의 경로 로드 가능(기능상 정상).
- 제안: 신뢰 경로(예: artifacts/checkpoints) 제한, 확장자 화이트리스트, `Path.resolve()` 기반 경로 검증 추가.

2) **MAPE 안정성 개선**
- 위치: `src/training/trainer.py:118-120`
- 제안: 0 근처 분모에 epsilon 적용한 sMAPE 병행 제공.

3) **테스트 보강**
- 제안: 
  - `prediction_horizon>1` shape 계약 테스트
  - 데이터 누수 방지(정규화 split 순서) 회귀 테스트
  - artifact run_id 일치 검사 테스트

---

## 체크 항목별 판정

- 데이터 누수: **이슈 있음 (Must fix 2건)**
- shape 불일치: **이슈 있음 (Must fix 1건)**
- 재현성: **개선 필요 (Should fix)**
- 보안(파일 로딩): **치명 이슈는 아니나 하드닝 권장 (Nice to have)**

---

## 우선 조치 순서 (제안)
1. 누수 2건 수정(정규화 순서, validation 분리/셔플 금지)
2. horizon-output 계약 강제
3. seed/deterministic 도입
4. config 포맷 정합성 정리
