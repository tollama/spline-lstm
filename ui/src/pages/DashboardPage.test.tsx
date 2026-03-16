import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { DashboardMobileTelemetrySection } from "./DashboardPage";

describe("DashboardMobileTelemetrySection", () => {
  it("renders mobile telemetry aggregates and recent uploads", () => {
    const html = renderToStaticMarkup(
      <DashboardMobileTelemetrySection
        mobileBenchmarks={{
          totalReceipts: 4,
          successfulReceipts: 3,
          failedReceipts: 1,
          successRate: 0.75,
          uniqueRuns: 2,
          latestReceivedAt: "2026-03-16T00:00:00Z",
          statusCounts: { succeeded: 3, validation_failed: 1 },
          platformCounts: { android: 2, ios: 1 },
          runtimeStackCounts: { tflite: 2, onnx: 1 },
          deviceProfileCounts: { android_high_end: 2, ios_high_end: 1 },
          averages: {
            latencyP95Ms: 21.5,
            memoryPeakMb: 188.3,
            sizeMb: 4.1,
            rmse: 0.93,
            baselineRmse: 1.02,
          },
          recentUploads: [
            {
              receiptId: "mobile-receipt-001",
              receivedAt: "2026-03-16T00:00:00Z",
              runId: "run-mobile-001",
              deviceProfile: "android_high_end",
              status: "succeeded",
              platform: "android",
              runtimeStack: "tflite",
              latencyP95Ms: 20.2,
              rmse: 0.91,
            },
          ],
        }}
      />,
    );

    expect(html).toContain("Mobile Telemetry");
    expect(html).toContain("Total Receipts");
    expect(html).toContain("75.0%");
    expect(html).toContain("tflite 2");
    expect(html).toContain("mobile-receipt-001");
  });

  it("renders the empty state when there are no mobile uploads", () => {
    const html = renderToStaticMarkup(<DashboardMobileTelemetrySection mobileBenchmarks={undefined} />);
    expect(html).toContain("모바일 벤치마크 업로드가 아직 없습니다.");
  });
});
