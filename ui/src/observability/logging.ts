export type UiLogKey =
  | "ui.dashboard.load_failed"
  | "ui.results.load_failed"
  | "ui.run.submit_failed"
  | "ui.run.poll_failed"
  | "ui.api.retry";

export type UiLogLevel = "info" | "warn" | "error";

export type UiLogPayload = {
  key: UiLogKey;
  userMessage: string;
  detail?: unknown;
  level?: UiLogLevel;
};

export function logUiEvent(payload: UiLogPayload): void {
  const level = payload.level ?? "error";
  const line = {
    key: payload.key,
    userMessage: payload.userMessage,
    detail: payload.detail,
    ts: new Date().toISOString(),
  };

  if (level === "warn") {
    console.warn(line);
    return;
  }
  if (level === "info") {
    console.info(line);
    return;
  }
  console.error(line);
}
