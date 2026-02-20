import { useEffect, useId, useMemo, useRef, useState } from "react";
import { ResultPayload, fetchResult, formatApiError } from "../api/client";
import { useToast } from "../components/Toast";
import { SimpleLineChart } from "../components/SimpleLineChart";
import { logUiEvent } from "../observability/logging";
import { toArtifactItems } from "./presentation";

type ResultsUiState = "idle" | "loading" | "loaded" | "empty" | "error";

type SyncedRangeOption = 24 | 72 | 168 | "all";

const SYNCED_RANGE_OPTIONS: SyncedRangeOption[] = [24, 72, 168, "all"];

function sliceByRange<T>(points: T[], range: SyncedRangeOption): T[] {
  if (range === "all") return points;
  if (points.length === 0) return points;
  const capped = Math.max(1, Math.min(range, points.length));
  return points.slice(-capped);
}

export function ResultsPage() {
  const { showToast } = useToast();

  const [runId, setRunId] = useState("local-quick-20260218-191832");
  const [data, setData] = useState<ResultPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uiState, setUiState] = useState<ResultsUiState>("idle");
  const [isSplineHelpOpen, setIsSplineHelpOpen] = useState(false);
  const [syncedRange, setSyncedRange] = useState<SyncedRangeOption>(168);

  const controllerRef = useRef<AbortController | null>(null);
  const requestVersionRef = useRef(0);
  const splineHelpRef = useRef<HTMLDivElement | null>(null);
  const splineHelpButtonId = useId();
  const splineHelpPanelId = useId();

  async function load() {
    controllerRef.current?.abort("replace-request");
    const controller = new AbortController();
    controllerRef.current = controller;
    const version = requestVersionRef.current + 1;
    requestVersionRef.current = version;

    setUiState("loading");
    setError(null);

    try {
      const result = await fetchResult(runId.trim(), { signal: controller.signal });
      if (requestVersionRef.current !== version) return;

      setData(result);
      setUiState("loaded");
      if (!result.predictions || result.predictions.length === 0) {
        showToast("조회 결과가 비어 있습니다.", "info");
      }
    } catch (e) {
      if (requestVersionRef.current !== version) return;
      const normalized = formatApiError(e);
      if (normalized.toLowerCase().includes("abort") || normalized.toLowerCase().includes("cancel")) {
        return;
      }

      setData(null);
      setError(normalized);
      setUiState("error");
      const userMessage = "결과 조회에 실패했습니다.";
      logUiEvent({ key: "ui.results.load_failed", userMessage, detail: normalized });
      showToast(userMessage, "error");
    }
  }

  useEffect(() => {
    void load();
    return () => {
      controllerRef.current?.abort("unmount");
    };
  }, []);

  useEffect(() => {
    if (!isSplineHelpOpen) return;

    function handlePointerDown(event: PointerEvent) {
      if (!splineHelpRef.current?.contains(event.target as Node)) {
        setIsSplineHelpOpen(false);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsSplineHelpOpen(false);
      }
    }

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isSplineHelpOpen]);

  const artifactItems = toArtifactItems(data?.artifacts);
  const artifactSummary = artifactItems.reduce<Record<string, number>>((acc, item) => {
    acc[item.group] = (acc[item.group] ?? 0) + 1;
    return acc;
  }, {});

  const fullInputChartPoints = useMemo(
    () => (data?.inputSeries ?? []).map((p, index) => ({ x: p.ts || `t-${index + 1}`, y: p.value })),
    [data?.inputSeries],
  );
  const fullOutputChartPoints = useMemo(
    () =>
      (data?.predictions ?? []).map((p, index) => ({
        x: p.ts || `t-${index + 1}`,
        y: p.actual,
        y2: p.predicted,
      })),
    [data?.predictions],
  );
  const fullSplineComparisonPoints = useMemo(
    () =>
      (data?.splineComparison ?? []).map((p, index) => ({
        x: p.ts || `t-${index + 1}`,
        y: p.raw,
        y2: p.spline,
      })),
    [data?.splineComparison],
  );

  const inputChartPoints = useMemo(() => sliceByRange(fullInputChartPoints, syncedRange), [fullInputChartPoints, syncedRange]);
  const outputChartPoints = useMemo(() => sliceByRange(fullOutputChartPoints, syncedRange), [fullOutputChartPoints, syncedRange]);
  const splineComparisonPoints = useMemo(
    () => sliceByRange(fullSplineComparisonPoints, syncedRange),
    [fullSplineComparisonPoints, syncedRange],
  );

  const syncedRangeLabel = useMemo(() => {
    const lengths = [fullInputChartPoints.length, fullOutputChartPoints.length, fullSplineComparisonPoints.length].filter((v) => v > 0);
    if (lengths.length === 0) return "";

    const shortestAvailable = Math.min(...lengths);
    if (syncedRange === "all") return `동기화 범위: 전체 (차트별 최대 ${shortestAvailable}개 이상 데이터 사용)`;
    if (shortestAvailable < syncedRange) {
      return `동기화 범위: ${syncedRange}개 요청 · 일부 차트는 데이터가 짧아 ${shortestAvailable}개까지만 표시`;
    }
    return `동기화 범위: 최근 ${syncedRange}개 포인트 (모든 차트 동일 적용)`;
  }, [fullInputChartPoints.length, fullOutputChartPoints.length, fullSplineComparisonPoints.length, syncedRange]);

  const splineDegree = data?.splineInfo?.degree;
  const splineSmoothing = data?.splineInfo?.smoothingFactor;
  const splineNumKnots = data?.splineInfo?.numKnots;
  const hasSplineInfo = typeof splineDegree === "number" || typeof splineSmoothing === "number" || typeof splineNumKnots === "number";
  const hasSplineComparison = splineComparisonPoints.length > 0;
  const splineApplied = hasSplineInfo && hasSplineComparison;

  return (
    <>
      <section className="card">
        <label>
          Run ID
          <input value={runId} onChange={(e) => setRunId(e.target.value)} />
        </label>
        <div className="action-row">
          <button className="primary" onClick={load} disabled={uiState === "loading" || !runId.trim()}>
            {uiState === "loading" ? "Loading..." : "Load Results"}
          </button>
          <span className="muted">State: {uiState}</span>
        </div>
      </section>

      {uiState === "loading" && <section className="card" aria-live="polite"><p className="muted">결과를 불러오는 중입니다...</p></section>}

      {error && (
        <section className="card" aria-live="assertive">
          <p className="error-text">Results API 오류: {error}</p>
          <div className="action-row">
            <button type="button" onClick={load}>다시 불러오기</button>
            <p className="muted">일시적인 네트워크 오류일 수 있습니다. 잠시 후 다시 시도해 주세요.</p>
          </div>
        </section>
      )}

      {data && uiState === "loaded" && (
        <>
          <section className="card">
            <h3>결과 요약</h3>
            <div className="status-grid">
              <div><strong>Run ID</strong><p>{data.runId}</p></div>
              <div><strong>Model Type</strong><p>{data.modelType ?? "-"}</p></div>
              <div><strong>Feature Mode</strong><p>{data.featureMode ?? "-"}</p></div>
              <div><strong>MASE</strong><p>{typeof data.metrics.mase === "number" ? data.metrics.mase.toFixed(4) : "-"}</p></div>
            </div>
          </section>

          <section className="grid-4">
            <article className="card stat"><h4>RMSE</h4><p>{data.metrics.rmse}</p></article>
            <article className="card stat"><h4>MAE</h4><p>{data.metrics.mae}</p></article>
            <article className="card stat"><h4>MAPE</h4><p>{data.metrics.mape}</p></article>
            <article className="card stat">
              <h4>MASE</h4>
              <p>{typeof data.metrics.mase === "number" ? data.metrics.mase : "-"}</p>
              {typeof data.metrics.mase !== "number" && <p className="muted">지표 미제공</p>}
            </article>
          </section>

          <section className="card">
            <div className="card-head-row">
              <h3>차트 동기화 범위</h3>
              <div className="context-range-controls" role="group" aria-label="모든 차트 공통 표시 범위">
                {SYNCED_RANGE_OPTIONS.map((option) => {
                  const isActive = syncedRange === option;
                  return (
                    <button
                      key={option}
                      type="button"
                      className={`range-chip ${isActive ? "is-active" : ""}`}
                      onClick={() => setSyncedRange(option)}
                    >
                      {option === "all" ? "전체" : option}
                    </button>
                  );
                })}
              </div>
            </div>
            <p className="muted">입력 / 출력(Actual vs Predicted) / Raw vs Spline 비교 차트에 동일한 범위를 적용합니다.</p>
            {syncedRangeLabel && <p className="muted">{syncedRangeLabel}</p>}
          </section>

          <section className="card spline-info-card">
            <div className="card-head-row">
              <h3>Spline 적용 정보</h3>
              <div className="spline-status-help-wrap" ref={splineHelpRef}>
                <span className={`status-badge spline-status-badge ${splineApplied ? "status-success" : "status-queued"}`}>
                  {splineApplied ? "Applied ✅" : "Unknown ⚠️"}
                </span>
                <button
                  id={splineHelpButtonId}
                  type="button"
                  className="spline-help-button"
                  aria-label="Spline status meaning help"
                  aria-haspopup="dialog"
                  aria-expanded={isSplineHelpOpen}
                  aria-controls={splineHelpPanelId}
                  onClick={() => setIsSplineHelpOpen((prev) => !prev)}
                >
                  ?
                </button>
                {isSplineHelpOpen && (
                  <div
                    id={splineHelpPanelId}
                    role="dialog"
                    aria-modal="false"
                    aria-labelledby={splineHelpButtonId}
                    className="spline-help-popover"
                  >
                    <p><strong>Applied ✅</strong> means spline meta + comparison evidence found.</p>
                    <p><strong>Unknown ⚠️</strong> means insufficient evidence data in current payload (not necessarily not applied).</p>
                  </div>
                )}
              </div>
            </div>
            <div className="status-grid">
              <div><strong>degree</strong><p>{typeof splineDegree === "number" ? splineDegree : "정보 없음"}</p></div>
              <div><strong>smoothing_factor</strong><p>{typeof splineSmoothing === "number" ? splineSmoothing : "정보 없음"}</p></div>
              <div><strong>num_knots</strong><p>{typeof splineNumKnots === "number" ? splineNumKnots : "정보 없음"}</p></div>
            </div>
            {!hasSplineInfo && <p className="muted">백엔드 payload에서 spline 설정 정보를 찾지 못했습니다.</p>}
          </section>

          <section className="card">
            <div className="card-head-row">
              <h3>Raw vs Spline 적용 비교</h3>
              <span className="muted">동기화 범위 적용</span>
            </div>
            {splineComparisonPoints.length > 0 ? (
              <SimpleLineChart
                title="Raw vs Spline Applied"
                points={splineComparisonPoints}
                seriesAName="Raw"
                seriesBName="Spline"
                yLabel="값"
              />
            ) : (
              <p className="muted">비교 가능한 raw/spline 시계열 데이터가 없어 표시할 수 없습니다.</p>
            )}
          </section>

          <section className="card">
            <div className="card-head-row">
              <h3>입력 데이터 그래프</h3>
              <span className="muted">동기화 범위 적용</span>
            </div>
            {inputChartPoints.length > 0 ? (
              <SimpleLineChart
                title="입력 시계열 (Input)"
                points={inputChartPoints}
                seriesAName="Input"
                yLabel="입력값"
                editable
                persistKey={`${data.runId}:input-series:${syncedRange}`}
                height={280}
              />
            ) : (
              <p className="muted">입력 시계열 데이터가 제공되지 않아 그래프를 표시할 수 없습니다.</p>
            )}
          </section>

          <section className="card">
            <div className="card-head-row">
              <h3>출력 데이터 그래프</h3>
              <span className="muted">동기화 범위 적용</span>
            </div>
            {outputChartPoints.length > 0 ? (
              <>
                <SimpleLineChart
                  title="실측값 vs 예측값 (Output)"
                  points={outputChartPoints}
                  seriesAName="Actual"
                  seriesBName="Predicted"
                  yLabel="출력값"
                />
                <p className="muted">오차는 아래 표의 Error 컬럼에서 확인할 수 있습니다.</p>
              </>
            ) : (
              <p className="muted">예측 데이터가 제공되지 않아 출력 그래프를 표시할 수 없습니다.</p>
            )}
          </section>

          <section className="card">
            <h3>Artifacts</h3>
            {artifactItems.length > 0 ? (
              <>
                <p className="muted">총 {artifactItems.length}개 · {Object.entries(artifactSummary).map(([k, v]) => `${k}:${v}`).join(", ")}</p>
                <table className="table">
                  <thead><tr><th>Type</th><th>Key</th><th>File</th><th>Path</th></tr></thead>
                  <tbody>
                    {artifactItems.map((item) => (
                      <tr key={item.key}>
                        <td><span className={`pill pill-${item.group}`}>{item.group}</span></td>
                        <td>{item.key}</td>
                        <td>{item.fileName}</td>
                        <td><code>{item.path}</code></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            ) : (
              <p className="muted">아티팩트 경로 정보가 없습니다.</p>
            )}
          </section>

          {data.reportMarkdown && (
            <section className="card">
              <h3>Report (Raw)</h3>
              <pre>{data.reportMarkdown}</pre>
            </section>
          )}

          <section className="card">
            <h3>Predictions (Sample)</h3>
            {data.predictions.length > 0 ? (
              <table className="table">
                <thead><tr><th>Timestamp</th><th>Actual</th><th>Predicted</th><th>Error</th></tr></thead>
                <tbody>
                  {data.predictions.map((p, i) => (
                    <tr key={i}>
                      <td>{p.ts}</td><td>{p.actual}</td><td>{p.predicted}</td><td>{(p.actual - p.predicted).toFixed(3)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="muted">예측 샘플이 제공되지 않았습니다. 메트릭/리포트 중심 결과만 확인 가능합니다.</p>
            )}
          </section>
        </>
      )}
    </>
  );
}
