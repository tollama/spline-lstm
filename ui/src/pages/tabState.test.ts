import { describe, expect, it } from "vitest";

import { nextTab, parseTabHash, tabToHash } from "./tabState";

describe("tab hash helpers", () => {
  it("parses known hash values and defaults", () => {
    expect(parseTabHash("#run")).toBe("run");
    expect(parseTabHash("#results")).toBe("results");
    expect(parseTabHash("#unknown")).toBe("dashboard");
  });

  it("builds hash and cycles tab order", () => {
    expect(tabToHash("dashboard")).toBe("#dashboard");
    expect(nextTab("dashboard", 1)).toBe("run");
    expect(nextTab("dashboard", -1)).toBe("results");
  });
});
