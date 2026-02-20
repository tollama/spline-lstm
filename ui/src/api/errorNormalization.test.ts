import { describe, expect, it } from "vitest";

import { ApiError } from "./errors";
import { NETWORK_MESSAGE, TIMEOUT_MESSAGE, isTimeoutLikeError, normalizeRequestError } from "./errorNormalization";

describe("errorNormalization", () => {
  it("detects AbortError as timeout", () => {
    const abortLike = new Error("signal aborted");
    abortLike.name = "AbortError";
    expect(isTimeoutLikeError(abortLike)).toBe(true);
  });

  it("detects timeout markers in error message", () => {
    expect(isTimeoutLikeError(new Error("timeout:12000"))).toBe(true);
    expect(isTimeoutLikeError("Request timed out")).toBe(true);
  });

  it("normalizes timeout-like errors to user-facing timeout message", () => {
    const normalized = normalizeRequestError(new Error("timeout:12000"), 12_000);
    expect(normalized).toBeInstanceOf(ApiError);
    expect(normalized.message).toBe(TIMEOUT_MESSAGE(12_000));
  });

  it("preserves ApiError instances", () => {
    const original = new ApiError("[500] backend fail", 500);
    expect(normalizeRequestError(original, 12_000)).toBe(original);
  });

  it("normalizes unknown errors to network failure message", () => {
    const normalized = normalizeRequestError(new Error("Failed to fetch"), 12_000);
    expect(normalized.message).toBe(NETWORK_MESSAGE);
  });
});
