import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  clamp,
  clearPersistedControlPoints,
  constrainXRatio,
  readPersistedControlPoints,
  svgToRatio,
  svgToY,
  writePersistedControlPoints,
} from "./SimpleLineChart";

describe("SimpleLineChart helpers", () => {
  beforeEach(() => {
    const store = new Map<string, string>();
    vi.stubGlobal("window", {
      localStorage: {
        getItem: (key: string) => store.get(key) ?? null,
        setItem: (key: string, value: string) => {
          store.set(key, value);
        },
        removeItem: (key: string) => {
          store.delete(key);
        },
      },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("clamp keeps values inside min/max", () => {
    expect(clamp(5, 0, 10)).toBe(5);
    expect(clamp(-2, 0, 10)).toBe(0);
    expect(clamp(12, 0, 10)).toBe(10);
  });

  it("svgToY maps and clamps coordinates to data domain", () => {
    const height = 240;
    const padding = 28;
    const minY = 0;
    const maxY = 100;

    expect(svgToY(28, height, padding, minY, maxY)).toBeCloseTo(100, 5);
    expect(svgToY(240 - 28, height, padding, minY, maxY)).toBeCloseTo(0, 5);
    expect(svgToY(-100, height, padding, minY, maxY)).toBeCloseTo(100, 5);
    expect(svgToY(999, height, padding, minY, maxY)).toBeCloseTo(0, 5);
  });

  it("svgToRatio maps/clamps x in drawing area", () => {
    expect(svgToRatio(28, 900, 28)).toBeCloseTo(0, 5);
    expect(svgToRatio(900 - 28, 900, 28)).toBeCloseTo(1, 5);
    expect(svgToRatio(-100, 900, 28)).toBeCloseTo(0, 5);
    expect(svgToRatio(9999, 900, 28)).toBeCloseTo(1, 5);
  });

  it("constrainXRatio preserves point order with min gap", () => {
    const points = [{ xPos: 0 }, { xPos: 0.3 }, { xPos: 0.7 }, { xPos: 1 }];
    const minGap = 0.1;

    expect(constrainXRatio(0.95, 1, points, minGap)).toBeCloseTo(0.6, 6);
    expect(constrainXRatio(0.05, 2, points, minGap)).toBeCloseTo(0.4, 6);
    expect(constrainXRatio(0.4, 0, points, minGap)).toBe(0);
    expect(constrainXRatio(0.4, 3, points, minGap)).toBe(1);
  });

  it("persists and restores edited points from localStorage", () => {
    const key = "test-run:input";
    writePersistedControlPoints(key, [
      { xPos: 0, y: 1 },
      { xPos: 0.4, y: 2 },
      { xPos: 1, y: 3 },
    ]);

    const restored = readPersistedControlPoints(key);
    expect(restored).toEqual([
      { xPos: 0, y: 1 },
      { xPos: 0.4, y: 2 },
      { xPos: 1, y: 3 },
    ]);

    clearPersistedControlPoints(key);
    expect(readPersistedControlPoints(key)).toBeNull();
  });
});
