# PHASE 1 Review Fix Pass Verification (Gate C)

## Standard Handoff Format

### 1) Request / Scope
- 역할: Reviewer (Fix Pass 재검증)
- 프로젝트: `~/spline-lstm`
- 목표: coder fixpass 반영 기준으로 Must fix 2건 재검증
- 검증 포인트:
  1. split 이전 normalize 제거 여부
  2. `validation_split` 제거 + 명시적 val split + `shuffle=False` 여부

### 2) What I Checked (latest code)
- `src/training/trainer.py`
- `src/models/lstm.py`
- 기존 리뷰 문서: `docs/PHASE1_REVIEW_FINAL.md`

### 3) Verification Results

#### Checkpoint A — split 이전 normalize 제거 여부
- **Result: FAIL (미해결)**
- Evidence:
  - `src/training/trainer.py:155-158`에서 `normalize=True` 시 전체 `data`에 먼저 정규화 수행
  - `src/training/trainer.py:160-161`에서 그 이후 `create_sequences` 및 `train_test_split` 수행
- 판단:
  - 여전히 split 전에 normalize가 수행되어 train/test 경계 기준 데이터 누수 가능성 존재

#### Checkpoint B — validation_split 제거 + 명시적 val split + shuffle=False 여부
- **Result: FAIL (미해결)**
- Evidence:
  - `src/models/lstm.py:98` `validation_split: float = 0.2` 기본 인자 유지
  - `src/models/lstm.py:117-125` `model.fit(... validation_split=validation_split, ...)` 사용
  - 동일 호출에서 `shuffle=False` 인자 미지정 (Keras 기본 `shuffle=True`)
- 판단:
  - 명시적 시간기반 val split(`validation_data=(X_val, y_val)`)로 전환되지 않았고,
  - `shuffle=False`도 강제되지 않아 시계열 검증 누수 리스크가 남아 있음

### 4) Gate Decision
- **Must fix 잔여 수: 2**
- **Gate C: FAIL**
- 판정 기준: Must fix = 0 일 때만 PASS

### 5) Recommended Next Actions (for coder)
1. `Trainer.train()`에서 전처리 순서를 변경:
   - split(또는 train-only 통계 fit 가능 구조) 이후 normalize 적용
   - train 통계로만 scaler fit, val/test에는 transform만 적용
2. `LSTMModel.fit_model()` 학습 입력 정책 변경:
   - `validation_split` 제거
   - Trainer에서 시간순 `X_val/y_val`을 명시 분리해 `validation_data=(X_val, y_val)` 전달
   - `shuffle=False` 명시

### 6) Deliverable
- 생성 문서: `docs/PHASE1_REVIEW_FIXPASS.md`
- 상태 요약: Gate C **FAIL** (Must fix 2건 미해결)
