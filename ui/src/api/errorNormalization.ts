import { ApiError } from "./errors";

export const TIMEOUT_MESSAGE = (timeoutMs: number): string => `요청 시간 초과 (${timeoutMs}ms)`;
export const NETWORK_MESSAGE = "네트워크 연결 실패";

function hasTimeoutMarker(value: string): boolean {
  const text = value.toLowerCase();
  return (
    text.includes("timeout:") ||
    /\btimeout\b\s*:?\s*\d+/i.test(value) ||
    text.includes("timed out") ||
    text.includes("timeout")
  );
}

export function isTimeoutLikeError(error: unknown): boolean {
  if (error instanceof DOMException && error.name === "AbortError") return true;

  if (error instanceof Error && error.name === "AbortError") return true;

  if (error instanceof Error) {
    if (error.name === "TimeoutError") return true;
    if (hasTimeoutMarker(error.message)) return true;
  }

  if (typeof error === "string") {
    return hasTimeoutMarker(error);
  }

  return false;
}

export function normalizeRequestError(error: unknown, timeoutMs: number): ApiError {
  if (isTimeoutLikeError(error)) {
    return new ApiError(TIMEOUT_MESSAGE(timeoutMs));
  }

  if (error instanceof ApiError) {
    return error;
  }

  return new ApiError(NETWORK_MESSAGE);
}
