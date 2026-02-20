# Spline-LSTM 프로젝트 BLUEPRINT

> **HISTORICAL NOTE (문서 정합성):** 이 문서는 해당 시점의 진행 스냅샷입니다. 현재 운영/실행 계약의 단일 기준은 `docs/RUNBOOK.md`와 최신 ARCH/FINAL/CLOSEOUT 문서입니다.
> 경로/CLI/게이트 상태가 본문과 다를 수 있으며, 운영 판단 시 현재 기준 문서를 우선합니다.


## 1) Project Vision / Scope (MVP vs 확장)

### 비전
- 시계열 데이터의 결측/불규칙 샘플링 문제를 **스플라인 보간/평활**로 완화하고,
- **LSTM 기반 예측 파이프라인**을 재현 가능하게 구축하여,
- 이후 멀티변수·외생변수(covariates)·경량 배포(edge)까지 확장 가능한 기반 마련.

### 범위

#### MVP (필수)
- 단일변수(univariate) 시계열 예측
- 스플라인 보간 + 평활 전처리
- LSTM 학습/평가/추론 파이프라인
- 실험 재현성(시드 고정, 설정 버전관리, 결과 아카이브)

#### 확장 (Phase 2+)
- 모델: GRU, Attention-LSTM
- 데이터: multivariate 입력
- covariates(캘린더/외부요인) 통합
- edge integration(TFLite/ONNX 후보)

### MVP 성공 기준 (요약)
- [ ] E2E 실행(`raw → preprocess → train → eval → infer`) 1회 커맨드로 동작
- [ ] 기준선(naive) 대비 핵심 지표 개선
- [ ] 동일 설정 재실행 시 지표 편차 허용 범위 내 유지

---

## 2) System Architecture (수집→전처리→학습→평가→배포)

```text
[Data Source]
  └─(ingest)→ data/raw/
      └─(validate)→ data/interim/
          └─(spline interpolate/smooth + scale + windowing)→ data/processed/
              └─(train)→ artifacts/models/, artifacts/checkpoints/
                  └─(evaluate)→ artifacts/reports/, artifacts/metrics/
                      └─(package)→ artifacts/deploy/
```

### 단계별 실행 체크리스트
1. 데이터 수집
   - [ ] 원천 데이터 스키마 확인(시간 컬럼, 타깃 컬럼)
   - [ ] `data/raw/`에 버전 태깅(날짜/해시)
2. 전처리
   - [ ] 결측/이상치 규칙 적용
   - [ ] 스플라인 보간 및 평활 적용
   - [ ] 스케일링 및 윈도우 생성
3. 학습
   - [ ] config 기반 하이퍼파라미터 로드
   - [ ] 시드 고정 및 deterministic 옵션 활성화
4. 평가
   - [ ] hold-out 또는 walk-forward 검증
   - [ ] 지표/플롯/오류분석 리포트 생성
5. 배포
   - [ ] 모델 직렬화 및 추론 스크립트 패키징
   - [ ] 모델/전처리 파이프라인 버전 매핑 문서화

---

## 3) Module Design

> 참고: 아래 컴포넌트 목록은 초기 설계안(blueprint) 기준이며, 현재 구현의 실행 엔트리포인트는 `src/preprocessing/smoke.py`, `src/training/runner.py`, `scripts/run_e2e.sh`, `scripts/smoke_test.sh`를 우선 참조한다.

### `src/preprocessing`
- 책임: 입력 정합성 검사, 결측 처리, 스플라인 보간/평활, 스케일링, 시퀀스 윈도우 생성
- 주요 컴포넌트
  - `loader.py`: raw 데이터 로드
  - `validators.py`: schema/시간축 검증
  - `spline.py`: interpolate/smooth 함수
  - `transform.py`: scaling, train/val/test split
  - `window.py`: `(lookback, horizon)` 기반 샘플 생성
- 완료 기준
  - [ ] 단위 테스트: 결측/불규칙 타임스탬프 케이스 통과
  - [ ] 전처리 결과 artifact 저장(`processed.parquet`, scaler)

### `src/models`
- 책임: 예측 모델 정의 및 registry
- 주요 컴포넌트
  - `lstm.py` (MVP 기본)
  - `gru.py` (확장)
  - `attention_lstm.py` (확장)
  - `registry.py`: 모델 이름→클래스 매핑
- 완료 기준
  - [ ] 모델 생성이 config 기반으로 통일
  - [ ] 입력/출력 shape assert 포함

### `src/training`
- 책임: 학습 루프, 평가 루프, 체크포인트, early stopping
- 주요 컴포넌트
  - `train.py`: optimizer/loss/scheduler
  - `evaluate.py`: metric 계산 및 리포트
  - `callbacks.py`: early stopping, ckpt saver
  - `runner.py`: CLI 엔트리포인트
- 완료 기준
  - [ ] best/last 체크포인트 저장
  - [ ] 학습 로그(손실/지표) 파일 출력

### `src/utils`
- 책임: 공통 유틸리티
- 주요 컴포넌트
  - `config.py`: YAML/JSON 로더
  - `seed.py`: 재현성 유틸
  - `io.py`: artifact 입출력
  - `logging.py`: 통합 로깅
- 완료 기준
  - [ ] 모든 실행 커맨드에서 동일 로거 포맷 사용

---

## 4) Data Contract (입력/출력/artifact)

### 입력 데이터 계약
- 최소 컬럼(MVP)
  - `timestamp` (datetime, 단조 증가)
  - `target` (float)
- 확장 컬럼
  - `cov_*` (float/int/category)
- 전처리 후 텐서 shape (MVP)
  - `X`: `[batch, lookback, 1]`
  - `y`: `[batch, horizon]` (또는 `[batch, horizon, 1]`로 통일 가능)

### 출력 데이터 계약
- 추론 출력
  - `y_pred`: `[batch, horizon]`
- 평가 산출
  - 시점별 예측값/실측값 테이블
  - 오차 통계(JSON/CSV)

### Artifact 포맷
- (historical draft) 모델: `artifacts/models/{run_id}/model.pt`
- (historical draft) 체크포인트: `artifacts/checkpoints/{run_id}/epoch_{n}.pt`
- (current) 체크포인트: `artifacts/checkpoints/{run_id}/best.keras`, `last.keras`
- 스케일러/전처리 객체: `artifacts/models/{run_id}/preprocessor.pkl`
- 설정 스냅샷: `artifacts/configs/{run_id}.yaml`
- 지표: `artifacts/metrics/{run_id}.json`
- 리포트: `artifacts/reports/{run_id}.md`

### 계약 준수 체크
- [ ] 컬럼/타입 자동 검증 실패 시 즉시 중단
- [ ] 모델 파일과 전처리 파일 run_id 일치 검증

---

## 5) Training / Evaluation Strategy

### Metrics
- 기본: MAE, RMSE
- 보조: MAPE(0 근처 값 주의), sMAPE
- 기준선 비교: Naive(last value), Moving Average

### Validation 전략
- MVP: 시간순 hold-out (train/val/test)
- 권장: walk-forward backtesting(확장 단계)

### 재현성 전략
- [ ] Python/NumPy/Framework 시드 고정
- [ ] 데이터 split 인덱스 저장
- [ ] config + 코드 커밋 해시 저장
- [ ] 동일 환경 의존성 lock(`requirements.txt`/`poetry.lock`)

### 평가 체크리스트
- [ ] 지표가 기준선 대비 개선되는가?
- [ ] 과적합 신호(train↘, val↗) 감지/기록
- [ ] 실패 실험도 로그 보존

---

## 6) Experiment Workflow (notebooks + versioning)

### 운영 원칙
- Notebook은 탐색/시각화 중심
- 재현 실행은 반드시 `src/training/runner.py` CLI로 수행

### 권장 구조
- `notebooks/01_eda.ipynb`
- `notebooks/02_spline_sanity_check.ipynb`
- `notebooks/03_error_analysis.ipynb`
- `configs/` (실험별 yaml)
- `artifacts/` (run_id 기준 저장)

### 버전 관리 체크리스트
- [ ] 실험 시작 전 config 고정 및 커밋
- [ ] run_id와 git commit hash 매핑
- [ ] 최종 실험만이 아니라 대표 실패 케이스도 기록

---

## 7) Milestones (4~6주 로드맵)

### Week 1 — 데이터/전처리 기반
- [ ] 데이터 계약 확정
- [ ] spline 보간/평활 모듈 구현
- [ ] 전처리 단위 테스트 구축

### Week 2 — MVP LSTM 학습 파이프라인
- [ ] LSTM 모델 + 학습 루프 구현
- [ ] 기본 지표/리포트 출력
- [ ] 재현성(시드/설정 스냅샷) 적용

### Week 3 — 평가 고도화
- [ ] 기준선 모델 비교 자동화
- [ ] 에러 분석 notebook 정리
- [ ] 하이퍼파라미터 1차 튜닝

### Week 4 — 안정화 + 배포 준비
- [ ] E2E 스크립트(원클릭) 제공
- [ ] 모델/전처리 패키징
- [ ] 운영 문서(실행/복구 가이드) 작성

### Week 5 (옵션) — 확장 1차
- [ ] GRU/Attention-LSTM 프로토타입
- [ ] multivariate 입력 파이프라인 초안

### Week 6 (옵션) — 확장 2차
- [ ] covariates 통합
- [ ] edge 배포 후보(ONNX/TFLite) 벤치마크

---

## 8) Risk & Mitigation

1. 데이터 품질 불량(결측/드리프트)
- 대응
  - [ ] 스키마/결측률 자동 리포트
  - [ ] 드리프트 감지(통계량 비교) 경고

2. 스플라인 과평활로 신호 손실
- 대응
  - [ ] 평활 강도 하이퍼파라미터화
  - [ ] 원신호 vs 평활신호 비교 플롯 의무화

3. 과적합/일반화 실패
- 대응
  - [ ] early stopping, dropout, weight decay
  - [ ] walk-forward 검증으로 재평가

4. 재현성 붕괴(환경/코드 차이)
- 대응
  - [ ] lockfile + run metadata 강제
  - [ ] CI에서 스모크 학습 테스트

5. 확장 단계 복잡도 급증
- 대응
  - [ ] 모델 registry/데이터 계약 선행 고정
  - [ ] MVP 성능 기준 통과 후 확장 착수

---

## 9) Definition of Done

### MVP DoD
- [ ] 단일변수 + spline + LSTM E2E 파이프라인 동작
- [ ] 재현 가능한 학습 결과(동일 config 재실행 편차 관리)
- [ ] 기준선 대비 성능 개선 리포트 확보
- [ ] 모델/전처리/artifact 버전 매핑 완료
- [ ] 실행 문서(README or runbook)로 신규 인원이 재현 가능

### 확장 DoD (Phase 2+)
- [ ] GRU/Attention 모델 비교표 완성
- [ ] multivariate + covariates 데이터 계약 확정
- [ ] edge 추론 PoC(지연/메모리/정확도) 결과 확보

---

## 즉시 실행 TODO (우선순위)
1. [P0] `src/preprocessing/spline.py`와 데이터 계약 테스트 먼저 고정
2. [P0] `src/models/lstm.py` + `src/training/runner.py`로 MVP 학습 루프 완성
3. [P0] run_id 기준 artifact 저장 규칙 적용
4. [P1] naive baseline 및 자동 비교 리포트 추가
5. [P1] notebook 3종(EDA/스플라인 검증/오류분석) 템플릿 생성
6. [P2] GRU/Attention 분기 및 multivariate 입력 스키마 초안 작성
