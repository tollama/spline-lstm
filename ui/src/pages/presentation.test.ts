import { describe, expect, it } from "vitest";
import { buildRunStatusView, clampProgress, toArtifactItems } from "./presentation";

describe("presentation helpers", () => {
  it("clamps progress safely", () => {
    expect(clampProgress(null)).toBeNull();
    expect(clampProgress(-5)).toBe(0);
    expect(clampProgress(40.7)).toBe(41);
    expect(clampProgress(130)).toBe(100);
  });

  it("builds success status view", () => {
    const view = buildRunStatusView({
      uiState: "succeeded",
      jobStatus: "success",
      jobStep: "finalize",
      progress: 100,
      isRetrying: false,
      retryCount: 0,
    });
    expect(view.tone).toBe("success");
    expect(view.title).toContain("완료");
    expect(view.detail).toContain("100%");
  });

  it("includes retry info while polling", () => {
    const view = buildRunStatusView({
      uiState: "polling",
      jobStatus: "running",
      jobStep: "train",
      progress: 33,
      isRetrying: true,
      retryCount: 2,
    });
    expect(view.tone).toBe("info");
    expect(view.detail).toContain("재시도 2회");
  });

  it("classifies artifacts for clearer presentation", () => {
    const items = toArtifactItems({
      metrics_json: "artifacts/metrics/run-a.json",
      report_md: "artifacts/reports/run-a.md",
      checkpoint_best: "checkpoints/run-a/best.keras",
      misc: "artifacts/other/file.bin",
    });

    expect(items.find((item) => item.key === "metrics_json")?.group).toBe("metrics");
    expect(items.find((item) => item.key === "report_md")?.group).toBe("report");
    expect(items.find((item) => item.key === "checkpoint_best")?.group).toBe("checkpoint");
    expect(items.find((item) => item.key === "misc")?.fileName).toBe("file.bin");
  });
});
