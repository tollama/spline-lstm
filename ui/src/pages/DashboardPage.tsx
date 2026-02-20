import { useEffect, useMemo, useState } from "react";
import { DashboardSummary, fetchDashboardSummary, formatApiError } from "../api/client";
import { MiniSparkline } from "../components/MiniSparkline";
import { useToast } from "../components/Toast";
import { logUiEvent } from "../observability/logging";

type DashboardUiState = "loading" | "loaded" | "empty" | "error";

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
    </>
  );
}
