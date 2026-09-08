export class ApiRequestError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, message: string, detail = "") {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.detail = detail;
  }
}

export function apiRequestError(status: number, detail = ""): ApiRequestError {
  if (status === 401) {
    return new ApiRequestError(
      status,
      "Your session is missing or expired. Sign in again and retry.",
      detail,
    );
  }
  if (status === 503) {
    return new ApiRequestError(
      status,
      detail || "A live service is temporarily unavailable. Retry shortly.",
      detail,
    );
  }
  return new ApiRequestError(
    status,
    detail || `The API request failed (${status}).`,
    detail,
  );
}
