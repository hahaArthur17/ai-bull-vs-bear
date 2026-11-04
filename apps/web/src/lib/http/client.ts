import config from "@/app/config/env";

export class HttpError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "HttpError";
  }
}

export function requireDemo(feature: string): void {
  if (config.dataMode !== "demo") {
    throw new HttpError(
      `${feature} is available in Demo mode. The live integration is not connected yet.`,
      501,
    );
  }
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const base = config.dataMode === "demo" ? "/api" : config.apiBaseUrl.replace(/\/$/, "");
  if (!base) throw new HttpError("A live API URL has not been configured.", 503);
  const response = await fetch(`${base}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  if (!response.ok) throw await responseError(response);
  return response.status === 204 ? (undefined as T) : (response.json() as Promise<T>);
}

async function responseError(response: Response): Promise<HttpError> {
  if (response.status === 401 || response.status === 403) {
    return new HttpError(
      "Live API authentication is not connected. Use the public Demo to explore.",
      response.status,
    );
  }
  const payload: unknown = await response.json().catch(() => null);
  const detail = readErrorMessage(payload);
  return new HttpError(
    detail ?? "The request could not be completed. Please try again.",
    response.status,
  );
}

function readErrorMessage(payload: unknown): string | undefined {
  if (!payload || typeof payload !== "object") return undefined;
  const value = payload as Record<string, unknown>;
  const message = value.message ?? value.detail;
  return typeof message === "string" ? message : undefined;
}
