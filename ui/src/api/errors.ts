export class ApiError extends Error {
  readonly status?: number;
  readonly body?: unknown;
  readonly code?: string;

  constructor(message: string, status?: number, body?: unknown, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
    this.code = code;
  }
}
