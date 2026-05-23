/**
 * Typed HTTP helpers for the backend API.
 *
 * Base URL comes from `NEXT_PUBLIC_API_URL`, defaulting to localhost:8000.
 * Non-2xx responses throw an `ApiError` carrying status + parsed body.
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

export interface ApiErrorBody {
  error?: string;
  detail?: string;
  suggestion?: string;
  [key: string]: unknown;
}

export class ApiError extends Error {
  readonly status: number;
  readonly body: ApiErrorBody | string | null;

  constructor(status: number, message: string, body: ApiErrorBody | string | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

function joinUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE_URL}${normalized}`;
}

async function parseResponse<T>(res: Response): Promise<T> {
  const text = await res.text();
  let parsed: unknown = null;

  if (text.length > 0) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = text;
    }
  }

  if (!res.ok) {
    const body =
      parsed === null || typeof parsed === "string"
        ? (parsed as string | null)
        : (parsed as ApiErrorBody);
    const message =
      (typeof body === "object" && body && (body.error ?? body.detail)) ||
      (typeof body === "string" && body) ||
      `Request failed with status ${res.status}`;
    throw new ApiError(res.status, String(message), body);
  }

  return parsed as T;
}

export async function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(joinUrl(path), {
    method: "GET",
    headers: { Accept: "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
    ...init,
  });
  return parseResponse<T>(res);
}

export async function apiPost<T>(
  path: string,
  body?: unknown,
  init?: RequestInit,
): Promise<T> {
  const isFormData = typeof FormData !== "undefined" && body instanceof FormData;
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...((init?.headers as Record<string, string>) ?? {}),
  };
  if (!isFormData && body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(joinUrl(path), {
    method: "POST",
    headers,
    body:
      body === undefined
        ? undefined
        : isFormData
          ? (body as FormData)
          : JSON.stringify(body),
    cache: "no-store",
    ...init,
  });
  return parseResponse<T>(res);
}
