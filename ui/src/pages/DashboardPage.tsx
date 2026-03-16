import { useEffect, useMemo, useState } from "react";
import { DashboardMobileBenchmarks, DashboardSummary, fetchDashboardSummary, formatApiError } from "../api/client";
import { MiniSparkline } from "../components/MiniSparkline";
import { useToast } from "../components/Toast";
import { logUiEvent } from "../observability/logging";

type DashboardUiState = "loading" | "loaded" | "empty" | "error";

export function DashboardMobileTelemetrySection({
  mobileBenchmarks,
}: {
  mobileBenchmarks?: DashboardMobileBenchmarks;
}) {
  const mobileLatencyTrend = (mobileBenchmarks?.recentUploads ?? [])
    .slice()
    .reverse()
    .map((item) => item.latencyP95Ms)
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  const mobileSuccessRate = mobileBenchmarks?.successRate;
  const mobileRuntimeCounts = mobileBenchmarks
    ? Object.entries(mobileBenchmarks.runtimeStackCounts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 4)
    : [];
  const mobilePlatformCounts = mobileBenchmarks
    ? Object.entries(mobileBenchmarks.platformCounts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 3)
    : [];

  return (
    <section className="card">
      <div className="card-head-row">
        <h3>Mobile Telemetry</h3>
        <div className="card-head-spark">
          <MiniSparkline
            values={mobileLatencyTrend}
            label="최근 모바일 p95 latency 추세"
            color="#f97316"
            emptyText="모바일 업로드 없음"
          />
        </div>
      </div>
      {!mobileBenchmarks || mobileBenchmarks.totalReceipts === 0 ? (
        <p className="muted">모바일 벤치마크 업로드가 아직 없습니다.</p>
      ) : (
        <>
          <section className="grid-4">
            <article className="card stat stat-compact">
              <h4>Total Receipts</h4>
              <p>{mobileBenchmarks.totalReceipts}</p>
            </article>
            <article className="card stat stat-compact">
              <h4>Success Rate</h4>
              <p>{mobileSuccessRate == null ? "-" : `${(mobileSuccessRate * 100).toFixed(1)}%`}</p>
            </article>
            <article className="card stat stat-compact">
              <h4>Avg P95</h4>
              <p>{mobileBenchmarks.averages.latencyP95Ms === null ? "-" : `${mobileBenchmarks.averages.latencyP95Ms} ms`}</p>
            </article>
            <article className="card stat stat-compact">
              <h4>Avg RMSE</h4>
              <p>{mobileBenchmarks.averages.rmse === null ? "-" : mobileBenchmarks.averages.rmse}</p>
            </article>
          </section>

          <div className="mobile-summary-row">
            <div>
              <p className="muted summary-label">Runtime Mix</p>
              <div className="chip-row">
                {mobileRuntimeCounts.map(([runtime, count]) => (
                  <span key={runtime} className="summary-chip">{runtime} {count}</span>
                ))}
              </div>
            </div>
            <div>
              <p className="muted summary-label">Platform Mix</p>
              <div className="chip-row">
                {mobilePlatformCounts.map(([platform, count]) => (
                  <span key={platform} className="summary-chip">{platform} {count}</span>
                ))}
              </div>
            </div>
          </div>

          <table className="table">
            <thead>
              <tr>
                <th>Receipt</th>
                <th>Run ID</th>
                <th>Profile</th>
                <th>Status</th>
                <th>Runtime</th>
                <th>P95</th>
                <th>RMSE</th>
              </tr>
            </thead>
            <tbody>
              {mobileBenchmarks.recentUploads.map((upload) => (
                <tr key={upload.receiptId}>
                  <td>{upload.receiptId}</td>
                  <td>{upload.runId}</td>
                  <td>{upload.deviceProfile}</td>
                  <td>
                    <span className={`status-badge ${upload.status === "succeeded" ? "status-success" : "status-fail"}`}>
                      {upload.status}
                    </span>
                  </td>
                  <td>{upload.runtimeStack}</td>
                  <td>{upload.latencyP95Ms === null ? "-" : `${upload.latencyP95Ms} ms`}</td>
                  <td>{upload.rmse === null ? "-" : upload.rmse}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  );
}

export function DashboardPage() {
  const { showToast } = useToast();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uiState, setUiState] = useState<DashboardUiState>("loading");

  async function load() {
    setUiState("loading");
    setError(null);

    try {
      const payload = await fetchDashboardSummary();
      setSummary(payload);
      if (payload.recentJobs.length === 0) {
        setUiState("empty");
      } else {
        setUiState("loaded");
      }
    } catch (e) {
      setSummary(null);
      const normalized = formatApiError(e);
      setError(normalized);
      setUiState("error");
      const userMessage = "대시보드 로딩에 실패했습니다.";
      logUiEvent({ key: "ui.dashboard.load_failed", userMessage, detail: normalized });
      showToast(userMessage, "error");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const recentStatusTrend = useMemo(() => {
    const jobs = summary?.recentJobs ?? [];
    const scoreByStatus: Record<string, number> = {
      fail: 0,
      canceled: 0.5,
      queued: 1,
      running: 2,
      success: 3,
    };
    return jobs
      .slice(0, 12)
      .reverse()
      .map((job) => scoreByStatus[job.status] ?? 0);
  }, [summary?.recentJobs]);

  const rmseTrend = useMemo(() => {
    return (summary?.rmseHistory ?? [])
      .map((item) => item.value)
      .filter(Number.isFinite);
  }, [summary?.rmseHistory]);

  if (uiState === "loading") {
    return <section className="card" aria-live="polite"><p className="muted">대시보드 데이터를 불러오는 중...</p></section>;
  }

  if (uiState === "error") {
    return (
      <section className="card" aria-live="assertive">
        <p className="error-text">대시보드 API 오류: {error}</p>
        <button type="button" onClick={load}>재시도</button>
      </section>
    );
  }

  if (!summary) {
    return <section className="card"><p className="muted">표시할 데이터가 없습니다.</p></section>;
  }

  return (
    <>
      <section className="grid-3">
        <article className="card stat"><h4>Service</h4><p>{summary.serviceStatus}</p></article>
        <article className="card stat"><h4>Last Run ID</h4><p>{summary.lastRunId}</p></article>
        <article className="card stat stat-with-spark">
          <h4>Last RMSE</h4>
          <p>{summary.lastRmse}</p>
          <MiniSparkline
            values={rmseTrend}
            label="최근 RMSE 추세"
            color="#7c3aed"
            emptyText="RMSE 히스토리 없음"
          />
        </article>
      </section>

      <section className="card">
        <div className="card-head-row">
          <h3>Recent Jobs</h3>
          <div className="card-head-spark">
            <MiniSparkline
              values={recentStatusTrend}
              label="최근 작업 상태 추세"
              color="#0ea5e9"
              emptyText="작업 히스토리 없음"
              min={0}
              max={3}
            />
          </div>
        </div>
        {uiState === "empty" ? (
          <p className="muted">최근 작업이 아직 없습니다.</p>
        ) : (
          <table className="table">
            <thead>
              <tr><th>Run ID</th><th>Status</th><th>Started At</th><th>Model</th></tr>
            </thead>
            <tbody>
              {summary.recentJobs.map((j) => (
                <tr key={j.runId}><td>{j.runId}</td><td><span className={`status-badge status-${j.status}`}>{j.status}</span></td><td>{j.startedAt}</td><td>{j.model}</td></tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
      <DashboardMobileTelemetrySection mobileBenchmarks={summary.mobileBenchmarks} />
    </>
  );
}
