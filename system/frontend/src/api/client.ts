import ky, { type HTTPError, type KyInstance, type Options } from "ky";

import type { QueryParams, Schema } from "./types";

export class ApiError extends Error {
  readonly status: number;
  readonly errorCode: string;
  readonly details: Record<string, unknown>;
  readonly requestId: string | null;

  constructor(message: string, params: { status: number; errorCode?: string; details?: Record<string, unknown>; requestId?: string | null }) {
    super(message);
    this.name = "ApiError";
    this.status = params.status;
    this.errorCode = params.errorCode ?? "api_error";
    this.details = params.details ?? {};
    this.requestId = params.requestId ?? null;
  }
}

type RequestConfig = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  query?: QueryParams;
  body?: unknown;
  headers?: Record<string, string | undefined>;
};

export function createRequestId(): string {
  const cryptoApi = globalThis.crypto;
  if (typeof cryptoApi?.randomUUID === "function") {
    return cryptoApi.randomUUID();
  }
  if (typeof cryptoApi?.getRandomValues === "function") {
    const bytes = new Uint8Array(16);
    cryptoApi.getRandomValues(bytes);
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0"));
    return `${hex.slice(0, 4).join("")}-${hex.slice(4, 6).join("")}-${hex.slice(6, 8).join("")}-${hex.slice(8, 10).join("")}-${hex.slice(10, 16).join("")}`;
  }
  return `req-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

export class ApiClient {
  private readonly http: KyInstance;

  constructor(baseUrl = import.meta.env.VITE_API_BASE_URL ?? "/api") {
    const resolvedBaseUrl = baseUrl.startsWith("/")
      ? `${globalThis.location?.origin ?? "http://localhost"}${baseUrl}`
      : baseUrl;
    this.http = ky.create({
      prefixUrl: resolvedBaseUrl,
      timeout: 20_000,
      credentials: "same-origin",
      hooks: {
        beforeRequest: [
          (request) => {
            request.headers.set("Accept", "application/json, application/*+json");
            request.headers.set("X-Request-Id", createRequestId());
          }
        ]
      }
    });
  }

  async request<T>(path: string, config: RequestConfig = {}): Promise<T> {
    const options: Options = {
      method: config.method ?? "GET",
      searchParams: this.toSearchParams(config.query),
      headers: this.cleanHeaders(config.headers)
    };

    if (config.body !== undefined) {
      options.json = config.body;
    }

    try {
      const response = await this.http(path.replace(/^\//, ""), options);
      if (response.status === 204) {
        return undefined as T;
      }
      return (await response.json()) as T;
    } catch (error) {
      throw await this.toApiError(error);
    }
  }

  private toSearchParams(query?: QueryParams): URLSearchParams | undefined {
    if (!query) {
      return undefined;
    }
    const params = new URLSearchParams();
    Object.entries(query).forEach(([key, value]) => {
      if (value === undefined || value === null || value === "") {
        return;
      }
      if (Array.isArray(value)) {
        if (value.length > 0) {
          params.set(key, value.join(","));
        }
        return;
      }
      params.set(key, String(value));
    });
    return params;
  }

  private cleanHeaders(headers?: Record<string, string | undefined>): Record<string, string> | undefined {
    if (!headers) {
      return undefined;
    }
    return Object.fromEntries(Object.entries(headers).filter((entry): entry is [string, string] => Boolean(entry[1])));
  }

  private async toApiError(error: unknown): Promise<ApiError> {
    const httpError = error as HTTPError;
    if (httpError.response) {
      let payload: Partial<Schema<"ErrorResponse">> = {};
      try {
        payload = (await httpError.response.json()) as Partial<Schema<"ErrorResponse">>;
      } catch {
        payload = {};
      }
      return new ApiError(payload.message ?? httpError.message, {
        status: httpError.response.status,
        errorCode: payload.error,
        details: (payload.details ?? {}) as Record<string, unknown>,
        requestId: httpError.response.headers.get("X-Request-Id")
      });
    }
    return new ApiError(error instanceof Error ? error.message : "Network request failed.", {
      status: 0,
      errorCode: "network_error"
    });
  }
}

export const apiClient = new ApiClient();
