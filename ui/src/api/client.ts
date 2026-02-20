import { ApiError } from "./errors";
import { normalizeRequestError } from "./errorNormalization";
import { API_BASE, API_PREFIX, APP_PROFILE } from "../config/env";

export { ApiError } from "./errors";

export type JobStatus = "queued" | "running" | "success" | "fail" | "canceled";

export type DashboardSummary = {
  serviceStatus: string;
  lastRunId: string;
  lastRmse: number;
  recentJobs: Array<{ runId: string; status: string; startedAt: string; model: string }>;
  rmseHistory?: Array<{ label: string; value: number }>;
};

export type ResultMetrics = {
  rmse: number;
  mae: number;
  mape: number;
  mase?: number;
  [key: string]: number | undefined;
};

export type ResultPrediction = {
  ts: string;
  actual: number;
  predicted: number;
};

export type RunArtifactMap = Record<string, string>;

export type ResultInputPoint = {
  ts: string;
  value: number;
};

export type SplineInfo = {
  degree?: number;
  smoothingFactor?: number;
  numKnots?: number;
};

export type SplineComparisonPoint = {
  ts: string;
  raw: number;
  spline: number;
};

export type ResultPayload = {
  runId: string;
  metrics: ResultMetrics;
  predictions: ResultPrediction[];
  inputSeries?: ResultInputPoint[];
  reportMarkdown?: string;
  artifacts?: RunArtifactMap;
  modelType?: string;
  featureMode?: string;
  splineInfo?: SplineInfo;
  splineComparison?: SplineComparisonPoint[];
};

export type RunJobPayload = {
  runId: string;
  model: string;
  epochs: number;
  synthetic: boolean;
  featureMode?: "univariate" | "multivariate";
  targetCols?: string;
  dynamicCovariates?: string;
  exportFormats?: string;
};

export type RunJobResponse = {
  jobId: string;
  runId: string;
  status: JobStatus;
  message?: string;
};

export type JobDetail = {
  jobId: string;
  runId: string;
  status: JobStatus;
  message?: string;
  errorMessage?: string;
  step?: string;
  progress?: number;
  updatedAt?: string;
};

export type JobLogResponse = {
  jobId: string;
  logs: string[];
};

const timerApi: Pick<typeof globalThis, "setTimeout" | "clearTimeout"> =
  typeof window !== "undefined" ? window : globalThis;

// Mock fallback is explicitly opt-in only in dev mode.
const USE_MOCK = import.meta.env.DEV && import.meta.env.VITE_USE_MOCK === "true";

const DEFAULT_TIMEOUT_MS = 10_000;
const TRANSIENT_STATUS = new Set([408, 425, 429, 500, 502, 503, 504]);

export type RetryEvent = {
  path: string;
  attempt: number;
  maxAttempts: number;
  retryCount: number;
  nextDelayMs: number;
  reason: string;
};

type RequestPolicy = {
  timeoutMs?: number;
  retries?: number;
  retryDelayMs?: number;
  onRetry?: (event: RetryEvent) => void;
  signal?: AbortSignal;
};

type ApiEnvelope<T> = {
  ok?: boolean;
  data?: T;
  message?: string;
  code?: string;
};

export type ApiRequestOptions = {
  timeoutMs?: number;
  retries?: number;
  retryDelayMs?: number;
  onRetry?: (event: RetryEvent) => void;
  signal?: AbortSignal;
};

function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  if (error instanceof Error) return new ApiError(error.message);
  return new ApiError("알 수 없는 API 오류가 발생했습니다.");
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => timerApi.setTimeout(resolve, ms));
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function toNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function parseCsv(raw: string | undefined): string[] {
  if (!raw) return [];
  return raw
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

function unwrapEnvelope<T>(body: unknown): T {
  if (isPlainObject(body) && ("data" in body || "ok" in body)) {
    const envelope = body as ApiEnvelope<T>;
    if (envelope.data !== undefined) return envelope.data;
  }
  return body as T;
}

function getBodyMessage(body: unknown, fallback: string): string {
  if (isPlainObject(body)) {
    if (typeof body.message === "string" && body.message.trim()) return body.message;
    if (typeof body.error_message === "string" && body.error_message.trim()) return body.error_message;
    if (typeof body.detail === "string" && body.detail.trim()) return body.detail;
  }
  return fallback;
}

function getBodyCode(body: unknown): string | undefined {
  if (!isPlainObject(body)) return undefined;
  if (typeof body.code === "string" && body.code.trim()) return body.code;
  if (typeof body.error_code === "string" && body.error_code.trim()) return body.error_code;
  return undefined;
}

async function parseJsonSafe(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function shouldRetry(error: unknown): boolean {
  if (!(error instanceof ApiError)) return false;
  if (!error.status) return true; // network/timeout type
  return TRANSIENT_STATUS.has(error.status);
}

async function fetchJson<T>(path: string, init?: RequestInit, policy?: RequestPolicy): Promise<T> {
  const timeoutMs = policy?.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const retries = Math.max(0, policy?.retries ?? 0);
  const retryDelayMs = Math.max(100, policy?.retryDelayMs ?? 500);

  let attempt = 0;
  while (true) {
    attempt += 1;

    const controller = new AbortController();
    const timeout = timerApi.setTimeout(() => controller.abort(`timeout:${timeoutMs}`), timeoutMs);
    const externalSignal = policy?.signal;
    const abortByExternalSignal = () => {
      controller.abort(externalSignal?.reason ?? "aborted");
    };

    if (externalSignal?.aborted) {
      abortByExternalSignal();
    } else if (externalSignal) {
      externalSignal.addEventListener("abort", abortByExternalSignal, { once: true });
    }

    try {
      const res = await fetch(`${API_BASE}${API_PREFIX}${path}`, {
        ...init,
        signal: controller.signal,
      });
      const body = await parseJsonSafe(res);

      if (!res.ok) {
        throw new ApiError(getBodyMessage(body, `HTTP ${res.status}`), res.status, body, getBodyCode(body));
      }

      return unwrapEnvelope<T>(body);
    } catch (error) {
      const normalized = normalizeRequestError(error, timeoutMs);

      if (attempt <= retries && shouldRetry(normalized)) {
        const nextDelayMs = retryDelayMs * attempt;
        policy?.onRetry?.({
          path,
          attempt,
          maxAttempts: retries + 1,
          retryCount: attempt,
          nextDelayMs,
          reason: normalized.message,
        });
        await sleep(nextDelayMs);
        continue;
      }

      throw normalized;
    } finally {
      timerApi.clearTimeout(timeout);
      externalSignal?.removeEventListener("abort", abortByExternalSignal);
    }
  }
}

function buildRunRequestBody(payload: RunJobPayload): Record<string, unknown> {
  const featureMode = payload.featureMode ?? "univariate";
  const targetCols = parseCsv(payload.targetCols);
  const dynamicCovariates = parseCsv(payload.dynamicCovariates);
  const exportFormats = parseCsv(payload.exportFormats);
  const normalizedExportFormats = exportFormats.length > 0 ? exportFormats : ["none"];

  return {
    // Legacy compatibility fields
    runId: payload.runId,
    model: payload.model,
    epochs: payload.epochs,
    synthetic: payload.synthetic,
    // Canonical snake_case fields
    run_id: payload.runId,
    model_type: payload.model,
    feature_mode: featureMode,
    target_cols: targetCols,
    dynamic_covariates: dynamicCovariates,
    export_formats: normalizedExportFormats,
    // Contract-style grouped fields
    mode: "train_eval",
    input: {
      target_cols: targetCols,
      dynamic_covariates: dynamicCovariates,
      feature_mode: featureMode,
    },
    model_config: {
      model_type: payload.model,
      epochs: payload.epochs,
    },
    runtime: {
      synthetic: payload.synthetic,
      export_formats: normalizedExportFormats,
    },
  };
}

function normalizeMetrics(payload: unknown): ResultMetrics | null {
  if (!isPlainObject(payload)) return null;

  const source = isPlainObject(payload.metrics) ? payload.metrics : payload;
  const rmse = toNumber(source.rmse);
  const mae = toNumber(source.mae);
  const mape = toNumber(source.mape);

  if (rmse === null || mae === null || mape === null) return null;

  const metrics: ResultMetrics = { rmse, mae, mape };
  for (const [key, value] of Object.entries(source)) {
    const numberValue = toNumber(value);
    if (numberValue !== null) {
      metrics[key] = numberValue;
    }
  }
  return metrics;
}

function normalizePredictions(payload: unknown): ResultPrediction[] {
  if (!isPlainObject(payload) || !Array.isArray(payload.predictions)) return [];

  const rows: ResultPrediction[] = [];
  for (const item of payload.predictions) {
    if (!isPlainObject(item)) continue;
    const actual = toNumber(item.actual);
    const predicted = toNumber(item.predicted);
    if (actual === null || predicted === null) continue;

    rows.push({
      ts: typeof item.ts === "string" ? item.ts : "",
      actual,
      predicted,
    });
  }
  return rows;
}

function normalizeInputSeries(payload: unknown, predictions: ResultPrediction[]): ResultInputPoint[] {
  if (isPlainObject(payload)) {
    const raw = Array.isArray(payload.input_series)
      ? payload.input_series
      : Array.isArray(payload.inputSeries)
        ? payload.inputSeries
        : null;

    if (raw) {
      const rows: ResultInputPoint[] = [];
      for (const item of raw) {
        if (!isPlainObject(item)) continue;
        const value = toNumber(item.value ?? item.actual ?? item.y);
        if (value === null) continue;
        rows.push({
          ts: typeof item.ts === "string" ? item.ts : "",
          value,
        });
      }
      if (rows.length > 0) return rows;
    }
  }

  if (predictions.length > 0) {
    return predictions.map((p) => ({ ts: p.ts, value: p.actual }));
  }

  return [];
}

function normalizeReportMarkdown(payload: unknown): string | undefined {
  if (typeof payload === "string" && payload.trim()) return payload;
  if (!isPlainObject(payload)) return undefined;

  const candidates = ["report", "report_md", "markdown", "content", "text"];
  for (const key of candidates) {
    const value = payload[key];
    if (typeof value === "string" && value.trim()) return value;
  }
  return undefined;
}

function normalizeArtifacts(payload: unknown): RunArtifactMap {
  if (!isPlainObject(payload)) return {};

  const artifacts: RunArtifactMap = {};

  const mergeRecord = (source: Record<string, unknown>, prefix = "") => {
    for (const [key, value] of Object.entries(source)) {
      if (typeof value !== "string" || !value.trim()) continue;
      artifacts[`${prefix}${key}`] = value;
    }
  };

  if (isPlainObject(payload.artifacts)) {
    mergeRecord(payload.artifacts);
  }

  const directKeys = [
    "metrics",
    "report",
    "model",
    "preprocessor",
    "metadata_path",
    "metrics_json",
    "report_md",
    "checkpoint",
    "processed_npz",
    "preprocessor_pkl",
  ] as const;
  for (const key of directKeys) {
    const value = payload[key];
    if (typeof value === "string" && value.trim()) {
      artifacts[key] = value;
    }
  }

  if (isPlainObject(payload.checkpoints)) {
    mergeRecord(payload.checkpoints, "checkpoint_");
  }

  return artifacts;
}

function normalizeRunId(payload: unknown, fallback: string): string {
  if (!isPlainObject(payload)) return fallback;
  if (typeof payload.run_id === "string" && payload.run_id.trim()) return payload.run_id;
  if (typeof payload.runId === "string" && payload.runId.trim()) return payload.runId;
  return fallback;
}

function normalizeModelType(payload: unknown): string | undefined {
  if (!isPlainObject(payload)) return undefined;
  if (typeof payload.model_type === "string" && payload.model_type.trim()) return payload.model_type;
  if (isPlainObject(payload.config) && typeof payload.config.model_type === "string" && payload.config.model_type.trim()) {
    return payload.config.model_type;
  }
  return undefined;
}

function normalizeFeatureMode(payload: unknown): string | undefined {
  if (!isPlainObject(payload)) return undefined;
  if (typeof payload.feature_mode === "string" && payload.feature_mode.trim()) return payload.feature_mode;
  if (isPlainObject(payload.config) && typeof payload.config.feature_mode === "string" && payload.config.feature_mode.trim()) {
    return payload.config.feature_mode;
  }
  return undefined;
}

function normalizeSplineInfoFromSource(payload: unknown): SplineInfo | null {
  if (!isPlainObject(payload)) return null;

  const rawSpline = isPlainObject(payload.spline)
    ? payload.spline
    : isPlainObject(payload.preprocessing) && isPlainObject(payload.preprocessing.spline)
      ? payload.preprocessing.spline
      : isPlainObject(payload.config) && isPlainObject(payload.config.spline)
        ? payload.config.spline
        : payload;

  const degree = toNumber(rawSpline.degree ?? rawSpline.spline_degree);
  const smoothingFactor = toNumber(rawSpline.smoothing_factor ?? rawSpline.smoothingFactor ?? rawSpline.spline_smoothing_factor);
  const numKnots = toNumber(rawSpline.num_knots ?? rawSpline.numKnots ?? rawSpline.spline_num_knots);

  if (degree === null && smoothingFactor === null && numKnots === null) return null;

  return {
    degree: degree ?? undefined,
    smoothingFactor: smoothingFactor ?? undefined,
    numKnots: numKnots ?? undefined,
  };
}

function normalizeSplineInfo(...sources: Array<unknown>): SplineInfo | undefined {
  for (const source of sources) {
    const info = normalizeSplineInfoFromSource(source);
    if (info) return info;
  }
  return undefined;
}

type IndexedPoint = { ts: string; value: number };

function normalizeIndexedSeries(raw: unknown): IndexedPoint[] {
  if (!Array.isArray(raw)) return [];

  const points: IndexedPoint[] = [];
  for (let i = 0; i < raw.length; i += 1) {
    const item = raw[i];
    if (isPlainObject(item)) {
      const value = toNumber(item.value ?? item.y ?? item.actual ?? item.predicted ?? item.spline);
      if (value === null) continue;
      points.push({ ts: typeof item.ts === "string" ? item.ts : `t-${i + 1}`, value });
      continue;
    }
    const value = toNumber(item);
    if (value === null) continue;
    points.push({ ts: `t-${i + 1}`, value });
  }

  return points;
}

function normalizeSplineComparisonPairs(raw: unknown): SplineComparisonPoint[] {
  if (!Array.isArray(raw)) return [];

  const points: SplineComparisonPoint[] = [];
  for (let i = 0; i < raw.length; i += 1) {
    const item = raw[i];
    if (!isPlainObject(item)) continue;

    const rawValue = toNumber(item.raw ?? item.raw_value ?? item.before ?? item.original);
    const splineValue = toNumber(item.spline ?? item.spline_value ?? item.after ?? item.smoothed);
    if (rawValue === null || splineValue === null) continue;

    points.push({
      ts: typeof item.ts === "string" ? item.ts : `t-${i + 1}`,
      raw: rawValue,
      spline: splineValue,
    });
  }

  return points;
}

function normalizeSplineComparisonFromSource(payload: unknown): SplineComparisonPoint[] {
  if (!isPlainObject(payload)) return [];

  const directPairCandidates: unknown[] = [
    payload.raw_vs_spline,
    payload.spline_comparison,
    payload.splineComparison,
    payload.raw_spline_comparison,
  ];

  for (const candidate of directPairCandidates) {
    const points = normalizeSplineComparisonPairs(candidate);
    if (points.length > 0) return points;
  }

  const candidates: Array<{ raw: unknown; spline: unknown }> = [
    { raw: payload.raw_series, spline: payload.spline_series },
    { raw: payload.rawSeries, spline: payload.splineSeries },
    { raw: payload.input_raw, spline: payload.input_spline },
    { raw: payload.raw_values, spline: payload.spline_values },
  ];

  if (isPlainObject(payload.raw_vs_spline)) {
    candidates.unshift({ raw: payload.raw_vs_spline.raw, spline: payload.raw_vs_spline.spline });
  }

  for (const candidate of candidates) {
    const rawPoints = normalizeIndexedSeries(candidate.raw);
    const splinePoints = normalizeIndexedSeries(candidate.spline);
    if (rawPoints.length === 0 || splinePoints.length === 0) continue;

    const size = Math.min(rawPoints.length, splinePoints.length);
    return Array.from({ length: size }, (_, index) => ({
      ts: rawPoints[index]?.ts || splinePoints[index]?.ts || `t-${index + 1}`,
      raw: rawPoints[index]?.value ?? 0,
      spline: splinePoints[index]?.value ?? 0,
    }));
  }

  return [];
}

function normalizeSplineComparison(...sources: Array<unknown>): SplineComparisonPoint[] | undefined {
  for (const source of sources) {
    const points = normalizeSplineComparisonFromSource(source);
    if (points.length > 0) return points;
  }
  return undefined;
}

function normalizeJobLogs(payload: unknown): string[] {
  if (Array.isArray(payload)) {
    return payload
      .filter((item): item is string => typeof item === "string")
      .map((item) => item.trim())
      .filter((item) => item.length > 0);
  }
  return [];
}

function normalizeStructuredLogLines(payload: unknown): string[] {
  if (!Array.isArray(payload)) return [];

  const lines: string[] = [];
  for (const item of payload) {
    if (typeof item === "string") {
      const trimmed = item.trim();
      if (trimmed) lines.push(trimmed);
      continue;
    }
    if (!isPlainObject(item)) continue;

    const ts = typeof item.ts === "string" && item.ts.trim() ? `[${item.ts}] ` : "";
    const level = typeof item.level === "string" && item.level.trim() ? `${item.level}: ` : "";
    const message = typeof item.message === "string" ? item.message : "";
    const line = `${ts}${level}${message}`.trim();
    if (line) lines.push(line);
  }
  return lines;
}

// ----------------------------
// Mock store (dev-only, explicit)
// ----------------------------
type MockJob = {
  jobId: string;
  runId: string;
  createdAt: number;
  shouldFail: boolean;
  forcedStatus?: JobStatus;
};

const mockJobs = new Map<string, MockJob>();

function buildMockDashboard(): DashboardSummary {
  return {
    serviceStatus: "MOCK: healthy",
    lastRunId: "local-quick-20260218-191832",
    lastRmse: 0.1234,
    recentJobs: [
      { runId: "local-quick-20260218-191832", status: "success", startedAt: "2026-02-18 19:18", model: "lstm" },
      { runId: "local-e2e-20260218-192200", status: "running", startedAt: "2026-02-18 19:22", model: "gru" },
      { runId: "local-exp-20260218-193010", status: "fail", startedAt: "2026-02-18 19:30", model: "lstm" },
      { runId: "local-exp-20260218-193540", status: "success", startedAt: "2026-02-18 19:35", model: "transformer" },
    ],
    rmseHistory: [
      { label: "t-3", value: 0.1712 },
      { label: "t-2", value: 0.1544 },
      { label: "t-1", value: 0.1429 },
      { label: "now", value: 0.1234 },
    ],
  };
}


function buildMockInputSeries(points = 240): IndexedPoint[] {
  const start = new Date("2026-02-08T00:00:00").getTime();
  return Array.from({ length: points }, (_, index) => {
    const ts = new Date(start + index * 60 * 60 * 1000).toISOString().slice(0, 19);
    const dailyWave = Math.sin((index / 24) * Math.PI * 2) * 2.4;
    const trend = index * 0.015;
    const jitter = Math.cos(index * 0.61) * 0.45;
    return {
      ts,
      value: Number((118 + trend + dailyWave + jitter).toFixed(3)),
    };
  });
}

function buildMockSplineComparison(inputSeries: IndexedPoint[]): SplineComparisonPoint[] {
  return inputSeries.map((point, index) => ({
    ts: point.ts,
    raw: Number((point.value + Math.sin(index * 0.7) * 0.6).toFixed(3)),
    spline: Number((point.value + Math.cos(index * 0.23) * 0.2).toFixed(3)),
  }));
}

function buildMockResult(runId: string): ResultPayload {
  const inputSeries = buildMockInputSeries(240);
  const predictionsBase = inputSeries.slice(-24);

  return {
    runId,
    metrics: { rmse: 0.1198, mae: 0.0851, mape: 4.37, mase: 0.62 },
    inputSeries,
    predictions: predictionsBase.slice(-12).map((point, index) => ({
      ts: point.ts,
      actual: point.value,
      predicted: Number((point.value + Math.sin(index * 0.9) * 0.8).toFixed(3)),
    })),
    reportMarkdown: "# Mock Report\n\nThis is a mock report payload.",
    artifacts: {
      metrics_json: `artifacts/metrics/${runId}.json`,
      report_md: `artifacts/reports/${runId}.md`,
      checkpoint_best: `artifacts/checkpoints/${runId}/best.keras`,
    },
    modelType: "lstm",
    featureMode: "univariate",
    splineInfo: { degree: 3, smoothingFactor: 0.5, numKnots: 10 },
    splineComparison: buildMockSplineComparison(inputSeries),
  };
}

function mockJobStatus(job: MockJob): JobStatus {
  if (job.forcedStatus) return job.forcedStatus;
  const elapsed = Date.now() - job.createdAt;
  if (elapsed < 1500) return "queued";
  if (elapsed < 4000) return "running";
  return job.shouldFail ? "fail" : "success";
}

function mapRawStatus(raw: string): JobStatus {
  if (raw === "queued") return "queued";
  if (raw === "running") return "running";
  if (raw === "succeeded" || raw === "success") return "success";
  if (raw === "canceled") return "canceled";
  return "fail";
}

function normalizeDashboardSummary(payload: unknown): DashboardSummary {
  if (!isPlainObject(payload)) {
    return { serviceStatus: "unknown", lastRunId: "-", lastRmse: 0, recentJobs: [] };
  }

  const serviceStatus =
    typeof payload.serviceStatus === "string"
      ? payload.serviceStatus
      : typeof payload.service_status === "string"
        ? payload.service_status
        : "unknown";

  const lastRunId =
    typeof payload.lastRunId === "string"
      ? payload.lastRunId
      : typeof payload.last_run_id === "string"
        ? payload.last_run_id
        : "-";

  const lastRmse = toNumber(payload.lastRmse ?? payload.last_rmse) ?? 0;

  const rawJobs = Array.isArray(payload.recentJobs)
    ? payload.recentJobs
    : Array.isArray(payload.recent_jobs)
      ? payload.recent_jobs
      : [];

  const recentJobs = rawJobs
    .filter(isPlainObject)
    .map((job) => ({
      runId: typeof job.runId === "string" ? job.runId : typeof job.run_id === "string" ? job.run_id : "-",
      status: typeof job.status === "string" ? job.status : "unknown",
      startedAt:
        typeof job.startedAt === "string"
          ? job.startedAt
          : typeof job.started_at === "string"
            ? job.started_at
            : "-",
      model: typeof job.model === "string" ? job.model : typeof job.model_type === "string" ? job.model_type : "-",
    }));

  const rawRmseHistory = Array.isArray(payload.rmseHistory)
    ? payload.rmseHistory
    : Array.isArray(payload.rmse_history)
      ? payload.rmse_history
      : [];

  const rmseHistory = rawRmseHistory
    .filter(isPlainObject)
    .map((item, index) => {
      const value = toNumber(item.value ?? item.rmse);
      if (value === null) return null;
      return {
        label: typeof item.label === "string" ? item.label : `#${index + 1}`,
        value,
      };
    })
    .filter((item): item is { label: string; value: number } => !!item);

  return { serviceStatus, lastRunId, lastRmse, recentJobs, rmseHistory };
}

export function isMockMode(): boolean {
  return USE_MOCK;
}

export function getApiBaseInfo(): string {
  return `${APP_PROFILE} · ${API_BASE}${API_PREFIX}`;
}

export function formatApiError(error: unknown): string {
  const apiError = toApiError(error);
  const parts: string[] = [];
  if (apiError.status) parts.push(`[${apiError.status}]`);
  if (apiError.code) parts.push(`(${apiError.code})`);
  parts.push(apiError.message);
  return parts.join(" ");
}

export async function fetchDashboardSummary(): Promise<DashboardSummary> {
  if (USE_MOCK) return buildMockDashboard();
  const payload = await fetchJson<unknown>("/dashboard/summary", undefined, { timeoutMs: 6000, retries: 1, retryDelayMs: 350 });
  return normalizeDashboardSummary(payload);
}

export async function postRunJob(payload: RunJobPayload, options?: ApiRequestOptions): Promise<RunJobResponse> {
  if (USE_MOCK) {
    const jobId = `job-mock-${Date.now()}`;
    const shouldFail = payload.runId.toLowerCase().includes("fail");
    mockJobs.set(jobId, { jobId, runId: payload.runId, createdAt: Date.now(), shouldFail });
    return {
      jobId,
      runId: payload.runId,
      status: "queued",
      message: "MOCK: job accepted",
    };
  }

  const res = await fetchJson<{
    job_id?: string;
    jobId?: string;
    run_id?: string;
    runId?: string;
    status: string;
    message?: string;
  }>("/pipelines/spline-tsfm:run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(buildRunRequestBody(payload)),
  }, {
    timeoutMs: options?.timeoutMs ?? 12_000,
    retries: options?.retries ?? 1,
    retryDelayMs: options?.retryDelayMs ?? 500,
    onRetry: options?.onRetry,
    signal: options?.signal,
  });

  const jobId = res.job_id ?? res.jobId;
  if (!jobId) {
    throw new ApiError("응답에 job_id가 없습니다.", 502, res);
  }

  return {
    jobId,
    runId: res.run_id ?? res.runId ?? payload.runId,
    status: mapRawStatus(res.status),
    message: res.message,
  };
}

export async function cancelJob(jobId: string, options?: ApiRequestOptions): Promise<JobDetail> {
  if (USE_MOCK) {
    const job = mockJobs.get(jobId);
    if (!job) throw new ApiError(`MOCK job not found: ${jobId}`, 404);
    job.forcedStatus = "canceled";
    mockJobs.set(jobId, job);
    return {
      jobId: job.jobId,
      runId: job.runId,
      status: "canceled",
      message: "MOCK: cancel accepted",
      errorMessage: "사용자 요청으로 작업이 취소되었습니다.",
      step: "canceled",
      progress: 100,
      updatedAt: new Date().toISOString(),
    };
  }

  const res = await fetchJson<{
    job_id?: string;
    jobId?: string;
    run_id?: string;
    runId?: string;
    status: string;
    message?: string;
    error_message?: string;
    step?: string;
    progress?: number;
    updated_at?: string;
  }>(`/jobs/${encodeURIComponent(jobId)}:cancel`, {
    method: "POST",
  }, {
    timeoutMs: options?.timeoutMs ?? 8000,
    retries: options?.retries ?? 1,
    retryDelayMs: options?.retryDelayMs ?? 400,
    onRetry: options?.onRetry,
    signal: options?.signal,
  });

  return {
    jobId: res.job_id ?? res.jobId ?? jobId,
    runId: res.run_id ?? res.runId ?? "",
    status: mapRawStatus(res.status),
    message: res.message,
    errorMessage: res.error_message,
    step: res.step,
    progress: res.progress,
    updatedAt: res.updated_at,
  };
}

export async function fetchJob(jobId: string, options?: ApiRequestOptions): Promise<JobDetail> {
  if (USE_MOCK) {
    const job = mockJobs.get(jobId);
    if (!job) throw new ApiError(`MOCK job not found: ${jobId}`, 404);
    const status = mockJobStatus(job);
    return {
      jobId: job.jobId,
      runId: job.runId,
      status,
      message: status === "fail" ? "MOCK: execution failed" : "MOCK: execution progressing",
      errorMessage: status === "fail" ? "MOCK failure: simulated runtime exception" : undefined,
      step: status === "queued" ? "queued" : status === "running" ? "training" : "finished",
      progress: status === "queued" ? 0 : status === "running" ? 52 : 100,
      updatedAt: new Date().toISOString(),
    };
  }

  const res = await fetchJson<{
    job_id?: string;
    jobId?: string;
    run_id?: string;
    runId?: string;
    status: "queued" | "running" | "succeeded" | "failed" | "canceled";
    message?: string;
    error_message?: string;
    step?: string;
    progress?: number;
    updated_at?: string;
  }>(`/jobs/${encodeURIComponent(jobId)}`, undefined, {
    timeoutMs: options?.timeoutMs ?? 8000,
    retries: options?.retries ?? 2,
    retryDelayMs: options?.retryDelayMs ?? 400,
    onRetry: options?.onRetry,
    signal: options?.signal,
  });

  return {
    jobId: res.job_id ?? res.jobId ?? jobId,
    runId: res.run_id ?? res.runId ?? "",
    status: mapRawStatus(res.status),
    message: res.message,
    errorMessage: res.error_message,
    step: res.step,
    progress: res.progress,
    updatedAt: res.updated_at,
  };
}

export async function fetchJobLogs(jobId: string, options?: ApiRequestOptions): Promise<JobLogResponse> {
  if (USE_MOCK) {
    const job = mockJobs.get(jobId);
    if (!job) throw new ApiError(`MOCK job not found: ${jobId}`, 404);
    const status = mockJobStatus(job);
    const logs = [
      `[${new Date(job.createdAt).toISOString()}] queued: job accepted`,
      `[${new Date(job.createdAt + 1000).toISOString()}] running: preprocessing`,
      `[${new Date(job.createdAt + 2200).toISOString()}] running: training`,
    ];
    if (status === "success") logs.push(`[${new Date().toISOString()}] success: completed`);
    if (status === "fail") logs.push(`[${new Date().toISOString()}] fail: simulated runtime exception`);
    if (status === "canceled") logs.push(`[${new Date().toISOString()}] canceled: user request`);
    return { jobId, logs };
  }

  const res = await fetchJson<{
    job_id?: string;
    jobId?: string;
    logs?: string[];
    lines?: Array<{ ts?: string; level?: string; message?: string }>;
  }>(
    `/jobs/${encodeURIComponent(jobId)}/logs?offset=0&limit=200`,
    undefined,
    {
      timeoutMs: options?.timeoutMs ?? 8000,
      retries: options?.retries ?? 1,
      retryDelayMs: options?.retryDelayMs ?? 350,
      onRetry: options?.onRetry,
      signal: options?.signal,
    },
  );
  const logs = normalizeJobLogs(res.logs);
  if (logs.length > 0) {
    return { jobId: res.job_id ?? res.jobId ?? jobId, logs };
  }
  return {
    jobId: res.job_id ?? res.jobId ?? jobId,
    logs: normalizeStructuredLogLines(res.lines),
  };
}

export async function fetchRunMetrics(runId: string, options?: ApiRequestOptions): Promise<unknown> {
  if (USE_MOCK) {
    const mock = buildMockResult(runId);
    return {
      run_id: runId,
      metrics: mock.metrics,
      config: { model_type: mock.modelType, feature_mode: mock.featureMode },
    };
  }
  return await fetchJson<unknown>(`/runs/${encodeURIComponent(runId)}/metrics`, undefined, {
    timeoutMs: options?.timeoutMs ?? 10_000,
    retries: options?.retries ?? 1,
    retryDelayMs: options?.retryDelayMs ?? 450,
    onRetry: options?.onRetry,
    signal: options?.signal,
  });
}

export async function fetchRunArtifacts(runId: string, options?: ApiRequestOptions): Promise<unknown> {
  if (USE_MOCK) {
    const mock = buildMockResult(runId);
    return {
      run_id: runId,
      artifacts: mock.artifacts,
    };
  }
  return await fetchJson<unknown>(`/runs/${encodeURIComponent(runId)}/artifacts`, undefined, {
    timeoutMs: options?.timeoutMs ?? 10_000,
    retries: options?.retries ?? 1,
    retryDelayMs: options?.retryDelayMs ?? 450,
    onRetry: options?.onRetry,
    signal: options?.signal,
  });
}

export async function fetchRunReport(runId: string, options?: ApiRequestOptions): Promise<unknown> {
  if (USE_MOCK) {
    const mock = buildMockResult(runId);
    return {
      run_id: runId,
      report: mock.reportMarkdown,
      predictions: mock.predictions,
      input_series: mock.inputSeries,
      metrics: mock.metrics,
    };
  }
  return await fetchJson<unknown>(`/runs/${encodeURIComponent(runId)}/report`, undefined, {
    timeoutMs: options?.timeoutMs ?? 10_000,
    retries: options?.retries ?? 1,
    retryDelayMs: options?.retryDelayMs ?? 450,
    onRetry: options?.onRetry,
    signal: options?.signal,
  });
}

export async function fetchResult(runId: string, options?: ApiRequestOptions): Promise<ResultPayload> {
  if (USE_MOCK) return buildMockResult(runId);

  const [reportResult, metricsResult, artifactsResult] = await Promise.allSettled([
    fetchRunReport(runId, options),
    fetchRunMetrics(runId, options),
    fetchRunArtifacts(runId, options),
  ]);

  const reportPayload = reportResult.status === "fulfilled" ? reportResult.value : null;
  const metricsPayload = metricsResult.status === "fulfilled" ? metricsResult.value : null;
  const artifactsPayload = artifactsResult.status === "fulfilled" ? artifactsResult.value : null;

  if (reportResult.status === "rejected" && metricsResult.status === "rejected") {
    throw toApiError(metricsResult.reason ?? reportResult.reason);
  }

  const metrics = normalizeMetrics(metricsPayload) ?? normalizeMetrics(reportPayload);
  if (!metrics) {
    throw new ApiError("메트릭 정보를 찾을 수 없습니다.");
  }

  const artifacts = normalizeArtifacts(artifactsPayload ?? reportPayload);
  const modelType = normalizeModelType(metricsPayload ?? reportPayload);
  const featureMode = normalizeFeatureMode(metricsPayload ?? reportPayload);
  const predictions = normalizePredictions(reportPayload);
  const splineInfo = normalizeSplineInfo(metricsPayload, reportPayload, artifactsPayload);
  const splineComparison = normalizeSplineComparison(metricsPayload, reportPayload, artifactsPayload);

  return {
    runId: normalizeRunId(metricsPayload ?? reportPayload ?? artifactsPayload, runId),
    metrics,
    predictions,
    inputSeries: normalizeInputSeries(reportPayload, predictions),
    reportMarkdown: normalizeReportMarkdown(reportPayload),
    artifacts: Object.keys(artifacts).length > 0 ? artifacts : undefined,
    modelType,
    featureMode,
    splineInfo,
    splineComparison,
  };
}
