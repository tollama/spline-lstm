import { describe, expect, it } from "vitest";

import { validateRunJobInput } from "./runJobValidation";

describe("validateRunJobInput", () => {
  it("returns field errors for invalid values", () => {
    const errors = validateRunJobInput({
      runId: "x",
      model: "",
      epochs: 0,
      synthetic: true,
      featureMode: "multivariate",
      targetCols: "",
      dynamicCovariates: "",
      exportFormats: "none",
    });

    expect(errors.runId).toBeTruthy();
    expect(errors.model).toBeTruthy();
    expect(errors.epochs).toBeTruthy();
    expect(errors.targetCols).toBeTruthy();
    expect(errors.dynamicCovariates).toBeTruthy();
  });

  it("accepts valid univariate payload", () => {
    const errors = validateRunJobInput({
      runId: "ui-run-001",
      model: "lstm",
      epochs: 3,
      synthetic: true,
      featureMode: "univariate",
      targetCols: "target",
      dynamicCovariates: "",
      exportFormats: "none",
    });

    expect(errors).toEqual({});
  });
});
