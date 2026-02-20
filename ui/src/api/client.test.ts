import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { cancelJob, fetchDashboardSummary, fetchJobLogs, fetchResult, postRunJob } from "./client";

function asJsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("api client integration adapters", () => {
  const originalFetch = globalThis.fetch;
  const originalWindow = (globalThis as any).window;

  beforeAll(() => {
    (globalThis as any).window = globalThis;
  });

  afterAll(() => {
    globalThis.fetch = originalFetch;
    (globalThis as any).window = originalWindow;
  });

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("serializes Phase 5 run options when submitting a job", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      asJsonResponse({
        ok: true,
        data: { job_id: "job-1", run_id: "run-1", status: "queued" },
      }),
    );
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const result = await postRunJob({
      runId: "run-1",
      model: "gru",
      epochs: 2,
      synthetic: true,
      featureMode: "multivariate",
      targetCols: "target,target_aux",
      dynamicCovariates: "temp,promo",
      exportFormats: "onnx,tflite",
    });

    expect(result).toEqual({
      jobId: "job-1",
      runId: "run-1",
      status: "queued",
      message: undefined,
    });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(String(init.body));

    expect(body.run_id).toBe("run-1");
    expect(body.model_type).toBe("gru");
    expect(body.feature_mode).toBe("multivariate");
    expect(body.target_cols).toEqual(["target", "target_aux"]);
    expect(body.dynamic_covariates).toEqual(["temp", "promo"]);
    expect(body.export_formats).toEqual(["onnx", "tflite"]);
  });

  it("supports structured log line payloads from backend", async () => {
    globalThis.fetch = vi
      .fn()
      .mockResolvedValue(
        asJsonResponse({
          ok: true,
          data: {
            job_id: "job-logs-1",
            lines: [{ ts: "2026-02-18T21:00:00Z", level: "INFO", message: "training started" }],
          },
        }),
      ) as unknown as typeof fetch;

    const logs = await fetchJobLogs("job-logs-1");
    expect(logs.jobId).toBe("job-logs-1");
    expect(logs.logs).toHaveLength(1);
    expect(logs.logs[0]).toContain("INFO");
    expect(logs.logs[0]).toContain("training started");
  });

  it("aggregates split metrics/report/artifacts endpoints", async () => {
    globalThis.fetch = vi
      .fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/runs/run-split/report")) {
          return Promise.resolve(asJsonResponse({ ok: true, data: "# report markdown" }));
        }
        if (url.includes("/runs/run-split/metrics")) {
          return Promise.resolve(
            asJsonResponse({
              ok: true,
              data: {
                run_id: "run-split",
                metrics: { rmse: 0.11, mae: 0.07, mape: 2.3, r2: 0.91 },
                config: { model_type: "gru", feature_mode: "multivariate" },
              },
            }),
          );
        }
        if (url.includes("/runs/run-split/artifacts")) {
          return Promise.resolve(
            asJsonResponse({
              ok: true,
              data: {
                artifacts: {
                  metrics_json: "artifacts/metrics/run-split.json",
                  report_md: "artifacts/reports/run-split.md",
                },
              },
            }),
          );
        }
        return Promise.reject(new Error(`Unexpected URL: ${url}`));
      }) as unknown as typeof fetch;

    const result = await fetchResult("run-split");

    expect(result.runId).toBe("run-split");
    expect(result.metrics.rmse).toBeCloseTo(0.11);
    expect(result.metrics.r2).toBeCloseTo(0.91);
    expect(result.reportMarkdown).toContain("report markdown");
    expect(result.artifacts?.metrics_json).toContain("run-split");
    expect(result.modelType).toBe("gru");
    expect(result.featureMode).toBe("multivariate");
    expect(result.predictions).toEqual([]);
  });

  it("falls back to legacy /report payload when /metrics is unavailable", async () => {
    globalThis.fetch = vi
      .fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/runs/run-legacy/report")) {
          return Promise.resolve(
            asJsonResponse({
              ok: true,
              data: {
                runId: "run-legacy",
                metrics: { rmse: 0.31, mae: 0.21, mape: 5.1 },
                predictions: [{ ts: "2026-02-18T20:00:00", actual: 10, predicted: 9.6 }],
              },
            }),
          );
        }
        if (url.includes("/runs/run-legacy/metrics") || url.includes("/runs/run-legacy/artifacts")) {
          return Promise.resolve(asJsonResponse({ message: "not found" }, 404));
        }
        return Promise.reject(new Error(`Unexpected URL: ${url}`));
      }) as unknown as typeof fetch;

    const result = await fetchResult("run-legacy");

    expect(result.runId).toBe("run-legacy");
    expect(result.metrics.rmse).toBeCloseTo(0.31);
    expect(result.predictions).toHaveLength(1);
    expect(result.predictions[0].predicted).toBeCloseTo(9.6);
  });

  it("extracts spline info/comparison when payload contains them and keeps fallback-safe undefined", async () => {
    globalThis.fetch = vi
      .fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/runs/run-spline/report")) {
          return Promise.resolve(
            asJsonResponse({
              ok: true,
              data: {
                run_id: "run-spline",
                metrics: { rmse: 0.2, mae: 0.1, mape: 2.1 },
                raw_vs_spline: {
                  raw: [10, 12, 11],
                  spline: [10.5, 11.3, 11.1],
                },
              },
            }),
          );
        }
        if (url.includes("/runs/run-spline/metrics")) {
          return Promise.resolve(
            asJsonResponse({
              ok: true,
              data: {
                run_id: "run-spline",
                metrics: { rmse: 0.2, mae: 0.1, mape: 2.1 },
                spline: { degree: 3, smoothing_factor: 0.5, num_knots: 12 },
              },
            }),
          );
        }
        if (url.includes("/runs/run-spline/artifacts")) {
          return Promise.resolve(asJsonResponse({ ok: true, data: { artifacts: {} } }));
        }
        return Promise.reject(new Error(`Unexpected URL: ${url}`));
      }) as unknown as typeof fetch;

    const result = await fetchResult("run-spline");

    expect(result.splineInfo).toEqual({ degree: 3, smoothingFactor: 0.5, numKnots: 12 });
    expect(result.splineComparison).toHaveLength(3);
    expect(result.splineComparison?.[1]).toMatchObject({ raw: 12, spline: 11.3 });
  });

  it("extracts spline comparison from paired point arrays", async () => {
    globalThis.fetch = vi
      .fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/runs/run-spline-pairs/report")) {
          return Promise.resolve(
            asJsonResponse({
              ok: true,
              data: {
                run_id: "run-spline-pairs",
                metrics: { rmse: 0.2, mae: 0.1, mape: 2.1 },
              },
            }),
          );
        }
        if (url.includes("/runs/run-spline-pairs/metrics")) {
          return Promise.resolve(
            asJsonResponse({
              ok: true,
              data: {
                run_id: "run-spline-pairs",
                metrics: { rmse: 0.2, mae: 0.1, mape: 2.1 },
                spline_comparison: [
                  { ts: "t1", raw: 10, spline: 10.2 },
                  { ts: "t2", before: 11, after: 11.1 },
                ],
              },
            }),
          );
        }
        if (url.includes("/runs/run-spline-pairs/artifacts")) {
          return Promise.resolve(asJsonResponse({ ok: true, data: { artifacts: {} } }));
        }
        return Promise.reject(new Error(`Unexpected URL: ${url}`));
      }) as unknown as typeof fetch;

    const result = await fetchResult("run-spline-pairs");

    expect(result.splineComparison).toEqual([
      { ts: "t1", raw: 10, spline: 10.2 },
      { ts: "t2", raw: 11, spline: 11.1 },
    ]);
  });

  it("maps cancel endpoint response to canceled status", async () => {
    globalThis.fetch = vi
      .fn()
      .mockResolvedValue(
        asJsonResponse({
          ok: true,
          data: {
            job_id: "job-cancel-1",
            run_id: "run-cancel-1",
            status: "canceled",
            message: "cancel accepted",
            step: "canceled",
            progress: 100,
          },
        }),
      ) as unknown as typeof fetch;

    const canceled = await cancelJob("job-cancel-1");
    expect(canceled.status).toBe("canceled");
    expect(canceled.jobId).toBe("job-cancel-1");
    expect(canceled.runId).toBe("run-cancel-1");
  });

  it("normalizes snake_case dashboard summary payload", async () => {
    globalThis.fetch = vi
      .fn()
      .mockResolvedValue(
        asJsonResponse({
          ok: true,
          data: {
            service_status: "healthy",
            last_run_id: "run-100",
            last_rmse: "0.123",
            recent_jobs: [
              { run_id: "run-100", status: "success", started_at: "2026-02-20", model_type: "gru" },
            ],
          },
        }),
      ) as unknown as typeof fetch;

    const summary = await fetchDashboardSummary();
    expect(summary.serviceStatus).toBe("healthy");
    expect(summary.lastRunId).toBe("run-100");
    expect(summary.lastRmse).toBeCloseTo(0.123);
    expect(summary.recentJobs[0].model).toBe("gru");
  });
});
