import { FormEvent, useEffect, useRef, useState } from "react";
import {
  cancelJob,
  JobDetail,
  JobStatus,
  RetryEvent,
  fetchJob,
  fetchJobLogs,
  formatApiError,
  getApiBaseInfo,
  isMockMode,
  postRunJob,
} from "../api/client";
import { useToast } from "../components/Toast";
import { logUiEvent } from "../observability/logging";
import { buildRunStatusView, clampProgress, UiState } from "./presentation";
import { RunJobFieldErrors, RunJobFormInput, toRunJobPayload, validateRunJobInput } from "./runJobValidation";

const TERMINAL_STATUS: JobStatus[] = ["success", "fail", "canceled"];
const POLL_INTERVAL_MS = 1300;
const POLL_TIMEOUT_MS = 90_000;

function readFormInput(form: HTMLFormElement): RunJobFormInput {
  const formData = new FormData(form);
  return {
    runId: String(formData.get("runId") ?? ""),
    model: String(formData.get("model") ?? "lstm"),
    epochs: Number(formData.get("epochs") ?? 1),
    synthetic: String(formData.get("synthetic") ?? "true") === "true",
    featureMode: String(formData.get("featureMode") ?? "univariate") as "univariate" | "multivariate",
    targetCols: String(formData.get("targetCols") ?? "target"),
    dynamicCovariates: String(formData.get("dynamicCovariates") ?? ""),
    exportFormats: String(formData.get("exportFormats") ?? "none"),
  };
}

export function RunJobPage() {
  const { showToast } = useToast();

  const [responseText, setResponseText] = useState("아직 실행되지 않았습니다.");
  const [jobId, setJobId] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [uiState, setUiState] = useState<UiState>("idle");
  const [logs, setLogs] = useState<string[]>([]);
  const [failureMessage, setFailureMessage] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [pollStartedAt, setPollStartedAt] = useState<number | null>(null);
  const [jobStep, setJobStep] = useState<string | null>(null);
  const [jobProgress, setJobProgress] = useState<number | null>(null);
  const [retryCount, setRetryCount] = useState(0);
  const [isRetrying, setIsRetrying] = useState(false);
  const [lastRetryReason, setLastRetryReason] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<RunJobFieldErrors>({});

  const pollTimerRef = useRef<number | null>(null);
  const activeJobIdRef = useRef<string | null>(null);
  const requestVersionRef = useRef(0);
  const submitControllerRef = useRef<AbortController | null>(null);
  const pollControllerRef = useRef<AbortController | null>(null);

  const isBusy = uiState === "submitting" || uiState === "polling";

  function stopPolling() {
    if (pollTimerRef.current) {
      window.clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    pollControllerRef.current?.abort("stop-polling");
    pollControllerRef.current = null;
  }

  function cancelActiveRequest(reason: string) {
    submitControllerRef.current?.abort(reason);
    pollControllerRef.current?.abort(reason);
    submitControllerRef.current = null;
    pollControllerRef.current = null;
  }

  async function handleCancel() {
    const targetJobId = activeJobIdRef.current;

    stopPolling();
    cancelActiveRequest("user-canceled");
    requestVersionRef.current += 1;

    if (!targetJobId) {
      activeJobIdRef.current = null;
      setUiState("canceled");
      setJobStatus("canceled");
      setIsRetrying(false);
      setFailureMessage("사용자 취소로 작업 조회를 중단했습니다.");
      showToast("요청을 취소했습니다.", "info");
      return;
    }

    try {
      const canceled = await cancelJob(targetJobId);
      activeJobIdRef.current = null;
      setJobStatus(canceled.status);
      setJobStep(canceled.step ?? "canceled");
      setJobProgress(typeof canceled.progress === "number" ? canceled.progress : null);
      setUiState("canceled");
      setIsRetrying(false);
      setFailureMessage(canceled.errorMessage ?? canceled.message ?? "사용자 요청으로 작업이 취소되었습니다.");
      setResponseText(JSON.stringify(canceled, null, 2));
      showToast("작업 취소 요청을 전송했습니다.", "info");
    } catch (error) {
      const message = formatApiError(error);
      activeJobIdRef.current = null;
      setApiError(message);
      setUiState("failed");
      setJobStatus("fail");
      setIsRetrying(false);
      setFailureMessage(`취소 요청 실패: ${message}`);
      setResponseText(JSON.stringify({ status: "fail", message }, null, 2));
      showToast("작업 취소 요청에 실패했습니다.", "error");
    }
  }

  function applyJobDetail(detail: JobDetail) {
    setJobStatus(detail.status);
    setJobStep(detail.step ?? null);
    setJobProgress(typeof detail.progress === "number" ? detail.progress : null);

    if (detail.status === "success") {
      setUiState("succeeded");
      setFailureMessage(null);
      showToast("학습 작업이 완료되었습니다.", "success");
    } else if (detail.status === "fail") {
      setUiState("failed");
      setFailureMessage(detail.errorMessage ?? detail.message ?? "알 수 없는 실패");
      showToast("학습 작업이 실패했습니다.", "error");
    } else if (detail.status === "canceled") {
      setUiState("canceled");
      setFailureMessage(detail.errorMessage ?? detail.message ?? "작업이 취소되었습니다.");
      showToast("작업이 취소 상태로 종료되었습니다.", "info");
    }
  }

  function handleRetry(event: RetryEvent) {
    setIsRetrying(true);
    setRetryCount((prev) => prev + 1);
    setLastRetryReason(`${event.path} · ${event.reason} · ${event.nextDelayMs}ms 후 재시도`);
    logUiEvent({
      key: "ui.api.retry",
      userMessage: "일시적인 API 오류로 재시도 중입니다.",
      detail: event,
      level: "warn",
    });
  }

  async function loadJobState(targetJobId: string, requestVersion: number) {
    pollControllerRef.current?.abort("refresh");
    const controller = new AbortController();
    pollControllerRef.current = controller;

    const [detail, jobLogs] = await Promise.all([
      fetchJob(targetJobId, { onRetry: handleRetry, signal: controller.signal }),
      fetchJobLogs(targetJobId, { onRetry: handleRetry, signal: controller.signal }),
    ]);

    if (requestVersionRef.current !== requestVersion) return;

    applyJobDetail(detail);
    setLogs(jobLogs.logs);
    setIsRetrying(false);

    if (TERMINAL_STATUS.includes(detail.status)) {
      stopPolling();
    }
  }

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (isBusy) return;

    const input = readFormInput(e.currentTarget);
    const validationErrors = validateRunJobInput(input);
    setFieldErrors(validationErrors);
    if (Object.keys(validationErrors).length > 0) {
      showToast("입력값을 확인해 주세요.", "error");
      return;
    }

    stopPolling();
    cancelActiveRequest("start-new-request");
    activeJobIdRef.current = null;

    const requestVersion = requestVersionRef.current + 1;
    requestVersionRef.current = requestVersion;

    setApiError(null);
    setFailureMessage(null);
    setLogs([]);
    setJobId(null);
    setRunId(null);
    setJobStatus("queued");
    setJobStep(null);
    setJobProgress(null);
    setRetryCount(0);
    setIsRetrying(false);
    setLastRetryReason(null);
    setUiState("submitting");
    setPollStartedAt(null);

    setResponseText("실행 요청 중...");

    const submitController = new AbortController();
    submitControllerRef.current = submitController;

    try {
      const result = await postRunJob(toRunJobPayload(input), { signal: submitController.signal });
      if (requestVersionRef.current !== requestVersion) return;

      setResponseText(JSON.stringify(result, null, 2));
      setJobId(result.jobId);
      setRunId(result.runId);
      setJobStatus(result.status);

      activeJobIdRef.current = result.jobId;
      setUiState(TERMINAL_STATUS.includes(result.status) ? (result.status === "success" ? "succeeded" : "failed") : "polling");
      setPollStartedAt(Date.now());

      await loadJobState(result.jobId, requestVersion);
    } catch (error) {
      if (requestVersionRef.current !== requestVersion) return;

      const message = formatApiError(error);
      if (message.toLowerCase().includes("cancel") || message.toLowerCase().includes("abort")) {
        setUiState("canceled");
        setFailureMessage("요청이 취소되었습니다.");
      } else {
        setApiError(message);
        setUiState("failed");
        setJobStatus("fail");
        setFailureMessage(message);
        setResponseText(JSON.stringify({ status: "fail", message }, null, 2));
        const userMessage = "작업 실행 요청에 실패했습니다.";
        logUiEvent({ key: "ui.run.submit_failed", userMessage, detail: message });
        showToast(userMessage, "error");
      }
      setIsRetrying(false);
    } finally {
      submitControllerRef.current = null;
    }
  }

  useEffect(() => {
    if (!jobId || uiState !== "polling") return;

    stopPolling();
    const requestVersion = requestVersionRef.current;

    pollTimerRef.current = window.setInterval(async () => {
      if (!activeJobIdRef.current) {
        stopPolling();
        return;
      }

      const startedAt = pollStartedAt ?? Date.now();
      if (Date.now() - startedAt > POLL_TIMEOUT_MS) {
        stopPolling();
        setUiState("timeout");
        setJobStatus("fail");
        setFailureMessage(`폴링 제한 시간(${Math.floor(POLL_TIMEOUT_MS / 1000)}s)을 초과했습니다.`);
        setIsRetrying(false);
        showToast("작업 상태 조회 시간이 초과되었습니다.", "error");
        return;
      }

      try {
        await loadJobState(activeJobIdRef.current, requestVersion);
      } catch (error) {
        const message = formatApiError(error);
        if (message.toLowerCase().includes("cancel") || message.toLowerCase().includes("abort")) {
          return;
        }

        setApiError(message);
        setUiState("failed");
        setJobStatus("fail");
        setFailureMessage(message);
        setIsRetrying(false);
        stopPolling();
        const userMessage = "작업 상태 조회에 실패했습니다.";
        logUiEvent({ key: "ui.run.poll_failed", userMessage, detail: message });
        showToast(userMessage, "error");
      }
    }, POLL_INTERVAL_MS);

    return () => {
      stopPolling();
    };
  }, [jobId, uiState, pollStartedAt]);

  const uiStateLabel: Record<UiState, string> = {
    idle: "대기",
    submitting: "제출 중",
    polling: "상태 확인 중",
    succeeded: "완료",
    failed: "실패",
    timeout: "시간 초과",
    canceled: "취소됨",
  };

  const progressValue = clampProgress(jobProgress);
  const statusView = buildRunStatusView({
    uiState,
    jobStatus,
    jobStep,
    progress: progressValue,
    isRetrying,
    retryCount,
  });

  return (
    <>
      <section className="card">
        <p className="muted">
          API: <code>{getApiBaseInfo()}</code>
          {isMockMode() ? " (dev mock enabled)" : ""}
        </p>
        <form onSubmit={onSubmit} onChange={(e) => {
          const name = (e.target as HTMLInputElement | HTMLSelectElement).name as keyof RunJobFormInput;
          if (!name || !fieldErrors[name]) return;
          setFieldErrors((prev) => {
            const next = { ...prev };
            delete next[name];
            return next;
          });
        }} noValidate>
          <label>Run ID<input name="runId" defaultValue="ui-run-20260218-001" required aria-invalid={!!fieldErrors.runId} aria-describedby={fieldErrors.runId ? "runId-error" : undefined} /></label>
          {fieldErrors.runId && <p id="runId-error" className="error-text">{fieldErrors.runId}</p>}
          <label>Model
            <select name="model" defaultValue="lstm" aria-invalid={!!fieldErrors.model} aria-describedby={fieldErrors.model ? "model-error" : undefined}>
              <option value="lstm">LSTM</option>
              <option value="gru">GRU</option>
              <option value="attention_lstm">Attention LSTM</option>
            </select>
          </label>
          {fieldErrors.model && <p id="model-error" className="error-text">{fieldErrors.model}</p>}
          <label>Epochs<input name="epochs" type="number" min={1} defaultValue={1} aria-invalid={!!fieldErrors.epochs} aria-describedby={fieldErrors.epochs ? "epochs-error" : undefined} /></label>
          {fieldErrors.epochs && <p id="epochs-error" className="error-text">{fieldErrors.epochs}</p>}
          <label>Feature Mode
            <select name="featureMode" defaultValue="univariate">
              <option value="univariate">univariate</option>
              <option value="multivariate">multivariate</option>
            </select>
          </label>
          <label>Target Cols (CSV)<input name="targetCols" defaultValue="target" aria-invalid={!!fieldErrors.targetCols} aria-describedby={fieldErrors.targetCols ? "targetCols-error" : undefined} /></label>
          {fieldErrors.targetCols && <p id="targetCols-error" className="error-text">{fieldErrors.targetCols}</p>}
          <label>Dynamic Covariates (CSV)<input name="dynamicCovariates" defaultValue="" aria-invalid={!!fieldErrors.dynamicCovariates} aria-describedby={fieldErrors.dynamicCovariates ? "dynamicCovariates-error" : undefined} /></label>
          {fieldErrors.dynamicCovariates && <p id="dynamicCovariates-error" className="error-text">{fieldErrors.dynamicCovariates}</p>}
          <label>Export Formats (CSV)<input name="exportFormats" defaultValue="none" /></label>
          <label>Synthetic
            <select name="synthetic" defaultValue="true">
              <option value="true">true</option><option value="false">false</option>
            </select>
          </label>
          <div className="action-row">
            <button className="primary" type="submit" disabled={isBusy}>{uiState === "submitting" ? "Submitting..." : "Run Scenario"}</button>
            <button type="button" onClick={handleCancel} disabled={!isBusy}>Cancel</button>
          </div>
        </form>
      </section>

      <section className="card" aria-live="polite">
        <h3>Execution Status</h3>
        <div className={`state-banner state-${statusView.tone}`}>
          <strong>{statusView.title}</strong>
          <p>{statusView.detail}</p>
          {progressValue != null && (
            <div className="progress-wrap" aria-label="progress">
              <progress max={100} value={progressValue} />
              <span>{progressValue}%</span>
            </div>
          )}
        </div>
        <div className="status-grid">
          <div><strong>Job ID</strong><p>{jobId ?? "-"}</p></div>
          <div><strong>Run ID</strong><p>{runId ?? "-"}</p></div>
          <div><strong>Status</strong><p className={`status-badge status-${jobStatus ?? "idle"}`}>{jobStatus ?? "idle"}</p></div>
          <div><strong>UI State</strong><p>{uiStateLabel[uiState]}</p></div>
          <div><strong>Step</strong><p>{jobStep ?? "-"}</p></div>
          <div><strong>Progress</strong><p>{progressValue != null ? `${progressValue}%` : "-"}</p></div>
          <div><strong>Retry Status</strong><p>{isRetrying ? "재시도 중" : "대기"}</p></div>
          <div><strong>Retry Count</strong><p>{retryCount}</p></div>
        </div>
        {lastRetryReason && <p className="muted">마지막 재시도: {lastRetryReason}</p>}
      </section>

      <section className="card">
        <h3>Error Details</h3>
        {apiError || failureMessage ? (
          <>
            {apiError && <pre className="error-log">API Error\n{apiError}</pre>}
            {failureMessage && <pre className="error-log">Failure Message\n{failureMessage}</pre>}
          </>
        ) : (
          <p className="muted">현재 오류 없음</p>
        )}
      </section>

      <section className="card">
        <h3>Execution Logs</h3>
        {isBusy && logs.length === 0 && <p className="muted">로그 수집 중...</p>}
        {logs.length > 0 ? <pre>{logs.join("\n")}</pre> : !isBusy && <p className="muted">아직 로그가 없습니다.</p>}
      </section>

      <section className="card">
        <h3>Job Response</h3>
        <pre>{responseText}</pre>
      </section>
    </>
  );
}
