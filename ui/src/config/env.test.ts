import { describe, expect, it } from "vitest";

import { normalizeProfile, resolveApiBase } from "./env";

describe("env profile normalization", () => {
  it("maps staging profile", () => {
    expect(normalizeProfile("stage")).toBe("stage");
  });

  it("maps production aliases", () => {
    expect(normalizeProfile("prod")).toBe("prod");
    expect(normalizeProfile("production")).toBe("prod");
  });

  it("falls back to dev", () => {
    expect(normalizeProfile(undefined)).toBe("dev");
    expect(normalizeProfile("unknown")).toBe("dev");
  });
});

describe("resolveApiBase", () => {
  it("prefers runtime override when valid", () => {
    expect(resolveApiBase({ runtimeBase: "https://runtime.example.com/", configuredBase: "https://config.example.com", profile: "dev" })).toBe("https://runtime.example.com");
  });

  it("uses configured base when runtime is invalid", () => {
    expect(resolveApiBase({ runtimeBase: "::not-a-url::", configuredBase: "https://config.example.com/api", profile: "dev" })).toBe("https://config.example.com/api");
  });

  it("falls back to profile default", () => {
    expect(resolveApiBase({ profile: "stage" })).toBe("http://localhost:18000");
  });
});
