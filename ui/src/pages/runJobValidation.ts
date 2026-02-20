import { RunJobPayload } from "../api/client";

export type RunJobFormInput = {
  runId: string;
  model: string;
  epochs: number;
  synthetic: boolean;
  featureMode: "univariate" | "multivariate";
  targetCols: string;
  dynamicCovariates: string;
  exportFormats: string;
};

export type RunJobFieldErrors = Partial<Record<keyof RunJobFormInput, string>>;

const RUN_ID_PATTERN = /^[a-zA-Z0-9][a-zA-Z0-9_-]{2,63}$/;

function parseCsv(raw: string): string[] {
  return raw
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function validateRunJobInput(input: RunJobFormInput): RunJobFieldErrors {
  const errors: RunJobFieldErrors = {};

  if (!input.runId.trim()) {
    errors.runId = "Run ID를 입력해 주세요.";
  } else if (!RUN_ID_PATTERN.test(input.runId.trim())) {
    errors.runId = "Run ID는 영문/숫자로 시작하고 3~64자(영문, 숫자, -, _)여야 합니다.";
  }

  if (!input.model.trim()) {
    errors.model = "모델을 선택해 주세요.";
  }

  if (!Number.isInteger(input.epochs) || input.epochs < 1 || input.epochs > 10000) {
    errors.epochs = "Epochs는 1~10000 사이 정수여야 합니다.";
  }

  if (!input.targetCols.trim()) {
    errors.targetCols = "예측 타깃 컬럼을 1개 이상 입력해 주세요.";
  }

  const targetCols = parseCsv(input.targetCols);
  if (targetCols.length === 0) {
    errors.targetCols = "타깃 컬럼 CSV 형식이 올바르지 않습니다.";
  }

  if (input.featureMode === "multivariate") {
    const dynamicCovariates = parseCsv(input.dynamicCovariates);
    if (dynamicCovariates.length === 0) {
      errors.dynamicCovariates = "multivariate 모드에서는 Dynamic Covariates를 1개 이상 입력해 주세요.";
    }
  }

  return errors;
}

export function toRunJobPayload(input: RunJobFormInput): RunJobPayload {
  return {
    runId: input.runId.trim(),
    model: input.model,
    epochs: input.epochs,
    synthetic: input.synthetic,
    featureMode: input.featureMode,
    targetCols: input.targetCols,
    dynamicCovariates: input.dynamicCovariates,
    exportFormats: input.exportFormats,
  };
}
