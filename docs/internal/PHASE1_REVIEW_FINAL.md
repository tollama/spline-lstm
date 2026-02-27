# Spline-LSTM MVP Phase 1 최종 검증 (Gate C)

- 검증 일시: 2026-02-18
- 검증 범위: 이전 Must fix 3건 해소 여부 재확인 (최신 코드 기준)
- 대상 코드: `src/training/trainer.py`, `src/models/lstm.py`, `tests/test_data_contract.py`

---

## 결론 요약

- **Must fix 잔여: 2건**
- **Gate C 판정: FAIL** (기준: Must fix=0일 때만 PASS)

---

## 항목별 검증 결과

### 1) 정규화 데이터 누수 (split 전 normalize)

**판정: 미해결 (Must fix 유지)**

근거:
- `Trainer.train()`에서 여전히 데이터 전체에 대해 정규화를 먼저 수행 후 시퀀스 생성/분할 수행.
- 코드:
  - `src/training/trainer.py:155-158` → `data, norm_params = self.normalize(data)`
  - `src/training/trainer.py:160-161` → 이후 `create_sequences` 및 `train_test_split`

영향:
- test 구간 통계(min/max, mean/std)가 train 전처리에 유입될 수 있어 시계열 평가 편향 가능.

권고:
- 순서를 `create_sequences -> train/test split -> train만 fit -> train/test transform`으로 변경.
- scaler 객체를 학습/저장하여 추론 시 재사용.

---

### 2) validation 누수 가능성 (validation_split + shuffle)

**판정: 미해결 (Must fix 유지)**

근거:
- `LSTMModel.fit_model()`에서 `validation_split` 사용 중이나 `shuffle=False` 명시 없음.
- Keras 기본값은 `shuffle=True`이므로 시계열 순서 교란 위험 존재.
- 코드:
  - `src/models/lstm.py:98` `validation_split=0.2`
  - `src/models/lstm.py:117-125` `model.fit(... validation_split=validation_split, ...)`
  - `shuffle` 인자 미지정

영향:
- 검증셋 구성 시 시간 순서 기반 분리가 깨져 미래 정보 혼입 가능.

권고:
- `shuffle=False` 강제.
- 가능하면 `validation_split` 대신 명시적 시간기반 `X_val/y_val` 분리 후 `validation_data=(X_val, y_val)` 사용.

---

### 3) prediction_horizon vs output_units shape 계약 불일치

**판정: 부분 해소 (Must fix → Should fix)**

근거:
- `create_sequences()`는 `y.shape = [batch, prediction_horizon * features]` 계약 유지.
- `LSTMModel._validate_xy()`가 `y.shape[1] == output_units`를 강제하여 불일치 시 즉시 `ValueError` 발생.
  - `src/training/trainer.py:58`
  - `src/models/lstm.py:64-67`
- 관련 계약 테스트도 존재하며 통과.
  - `tests/test_data_contract.py`
  - 실행 결과: `python3 -m pytest -q tests/test_data_contract.py` → **5 passed**

해석:
- 학습 중 무증상 진행은 방지됨(빠른 실패).
- 다만 Trainer 초기 단계에서 `prediction_horizon`과 `model.output_units`를 직접 대조하는 명시적 사전검증/친절한 오류메시지는 아직 없음.

권고:
- `Trainer.__init__` 또는 `train()` 초반에
  - `expected = prediction_horizon * n_features` 계산
  - `model.output_units == expected` 즉시 검증 및 명확한 에러 제공.

---

## 재분류 (최종)

### Must fix
1. 정규화 데이터 누수 (split 전 normalize)
2. validation 누수 가능성 (`validation_split` + 기본 shuffle)

### Should fix
1. horizon-output 계약을 Trainer 레벨에서 사전검증(현재는 모델 레벨 빠른 실패까지만 보장)

### Nice
- 없음

---

## Gate C 최종 판정

- **FAIL**
- 사유: **Must fix 2건 잔여** (PASS 조건: Must fix 0건)

---

## Fix Pass 업데이트 (Coder, 2026-02-18)

아래 2건 Must fix 반영 완료:

1) 정규화 누수 차단
- `Trainer.train()`에서 split 이전 normalize 제거.
- raw 시계열을 먼저 시간순 `train/val/test` 분리 후,
  - train split에만 normalization parameter fit
  - val/test는 train parameter로 transform만 수행

2) validation 누수 가능성 제거
- `LSTMModel.fit_model()`에서 `validation_split` 제거.
- `validation_data=(X_val, y_val)`를 명시적으로 주입하도록 변경.
- `shuffle=False` 기본/명시 적용.

검증:
- `tests/test_training_leakage.py` 추가
  - train-fit normalization 보장
  - explicit validation_data + shuffle=False 보장
