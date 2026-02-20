import { JobStatus } from "../api/client";

export type UiState = "idle" | "submitting" | "polling" | "succeeded" | "failed" | "timeout" | "canceled";

export type RunStatusView = {
  tone: "neutral" | "info" | "success" | "warning" | "error";
  title: string;
  detail: string;
};

export function clampProgress(progress: number | null): number | null {
  if (typeof progress !== "number" || !Number.isFinite(progress)) return null;
  if (progress < 0) return 0;
  if (progress > 100) return 100;
  return Math.round(progress);
}

export function buildRunStatusView(input: {
  uiState: UiState;
  jobStatus: JobStatus | null;
  jobStep: string | null;
  progress: number | null;
  isRetrying: boolean;
  retryCount: number;
}): RunStatusView {
  const progress = clampProgress(input.progress);
  const stepLabel = input.jobStep ? ` · step: ${input.jobStep}` : "";
  const progressLabel = progress != null ? ` · ${progress}%` : "";

  if (input.uiState === "succeeded" || input.jobStatus === "success") {
    return { tone: "success", title: "작업 완료", detail: `학습 및 평가가 완료되었습니다${progressLabel}${stepLabel}.` };
  }
  if (input.uiState === "failed" || input.uiState === "timeout" || input.jobStatus === "fail") {
    return { tone: "error", title: "작업 실패", detail: `실패 상태입니다${progressLabel}${stepLabel}.` };
  }
  if (input.uiState === "canceled" || input.jobStatus === "canceled") {
    return { tone: "warning", title: "작업 취소", detail: `사용자 또는 시스템에 의해 취소되었습니다${stepLabel}.` };
  }
  if (input.uiState === "submitting") {
    return { tone: "info", title: "요청 제출 중", detail: "실행 요청을 전송하고 있습니다." };
  }
  if (input.uiState === "polling" || input.jobStatus === "running" || input.jobStatus === "queued") {
    const retryLabel = input.isRetrying ? ` · 재시도 ${input.retryCount}회` : "";
    return { tone: "info", title: "실행 중", detail: `작업 상태를 확인 중입니다${progressLabel}${stepLabel}${retryLabel}.` };
  }

  return { tone: "neutral", title: "대기", detail: "작업 실행을 시작하면 상태가 여기에 표시됩니다." };
}

export type ArtifactItem = {
  key: string;
  path: string;
  group: "metrics" | "report" | "model" | "checkpoint" | "data" | "other";
  fileName: string;
};

export function toArtifactItems(artifacts?: Record<string, string>): ArtifactItem[] {
  if (!artifacts) return [];
  return Object.entries(artifacts).map(([key, path]) => {
    const normalized = `${key} ${path}`.toLowerCase();
    const group = normalized.includes("metric")
      ? "metrics"
      : normalized.includes("report")
        ? "report"
        : normalized.includes("checkpoint") || normalized.includes(".keras")
          ? "checkpoint"
          : normalized.includes("model")
            ? "model"
            : normalized.includes("data") || normalized.includes("npz")
              ? "data"
              : "other";

    const fileName = path.split("/").filter(Boolean).pop() ?? path;
    return { key, path, group, fileName };
  });
}
