# E2E_WITH_SYNTHETIC_REVIEW

## 전제/입력 확인
- 요청 입력 파일 `docs/E2E_WITH_SYNTHETIC_RESULTS.md`는 현재 저장소에서 확인되지 않음.
- 본 리뷰는 가장 근접한 결과 문서인 `docs/TEST_RESULTS_SYNTHETIC_DATA.md`와 설계 기준 `docs/SYNTHETIC_DATA_DESIGN.md`를 기준으로 수행함.

---

## 시나리오별 품질/안정성 검토

### S1 (기본형)
**판정: 양호 (PASS 수준)**
- 생성 성공(S1 포함) 확인됨.
- 필수 컬럼/shape/type, timestamp monotonic/unique 계약 확인됨.
- seed 재현성(동일 seed 동일 출력, 다른 seed 변화) 확인됨.

**리스크**
- 현재는 생성기 단위 테스트 중심이며, E2E 학습/리포트 아티팩트까지의 연계 검증 증거는 부족.

---

### S2 (현실형)
**판정: 부분 충족 (조건부 PASS)**
- 결측 + 이상치 주입 검증 존재.
- 불규칙 샘플링 검증은 S3 테스트에서 확인되며, S2 자체의 불규칙 샘플링 주입률/안정성 근거는 약함.

**리스크**
- 설계 수용 기준(주입률 ±10%p, seed 배치 성공률 ≥95%, 이벤트 구간 성능 분리)에 대한 정량 검증 부재.
- E2E 관점(전처리→학습→평가) 품질 근거가 부족.

---

### S3 (가혹형)
**판정: 미충족 (FAIL)**
- 결과 문서상 S3는 결측/이상치/불규칙 샘플링 중심으로 검증됨.
- 그러나 설계 기준상 S3 핵심은 **drift 감지, covariate 누락 처리, schema 오류 fail-fast/원인 메시지**임.
- 즉, S3의 본질적 가드레일(정상 실패) 검증 증거가 부족함.

**핵심 결함**
1. drift 주입 후 성능 저하 감지/리포팅 검증 없음
2. covariate 누락 fallback 또는 명시적 에러 처리 검증 없음
3. schema 오류(필수 컬럼/타입/timestamp disorder/duplicate) fail-fast 검증 없음

---

## Must / Should / Nice 분류

### Must (게이트 통과 필수)
1. `S3` 전용 테스트 추가: drift 감지/리포팅 assert
2. `S3` 전용 테스트 추가: covariate 누락 처리(fallback 또는 명시적 에러) assert
3. `S3` 전용 테스트 추가: schema 오류 fail-fast + 원인 메시지(컬럼/타입/timestamp) assert
4. 시나리오별 결과 문서에 run_id/seed/scenario_id 및 pass/fail 근거를 분리 기록

### Should (단기 품질 강화)
1. `S2` 주입률(결측/이상치/불규칙 샘플링) 정량 검증(설정 대비 허용 오차) 추가
2. seed 배치 실행 기반 안정성 지표(성공률, flakiness) 리포트 추가
3. 단위 테스트 외 E2E 스모크(전처리→학습→리포트) 1개 이상 시나리오별 연결

### Nice (중장기 개선)
1. scenario preset(기본/스트레스) 이원화 및 자동 리포트 템플릿화
2. 이벤트 구간/비이벤트 구간 성능 분리 리포트 자동 생성
3. CI에서 S3-schema를 독립 잡으로 분리(정상 실패 기대값 관리)

---

## Gate 판정
**최종 Gate: FAIL**

사유: S1은 양호하고 S2는 부분 충족이나, S3의 필수 가드레일 검증(drift/covariate/schema fail-fast) 증거가 부족하여 전체 synthetic 기반 E2E 게이트 기준을 충족하지 못함.

---

## 최종 한 줄 판정
**판정: FAIL — S3 핵심 요구사항(드리프트 감지·공변량 누락 처리·스키마 fail-fast) 검증 부재로 게이트 미통과.**
