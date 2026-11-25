import { getActiveId } from "@/utils/profile";
import type { ApiErrorBody } from "./types";

export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/+$/, "");

export class ApiError extends Error {
  status: number;
  code: string;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

/** Codes whose backend message is already plain enough to show a shopkeeper. */
const SHOW_SERVER_MESSAGE = new Set([
  "VALIDATION_ERROR",
  "INVALID_STATEMENT_FORMAT",
  "PAYLOAD_TOO_LARGE",
  "RESOURCE_NOT_FOUND",
  "INVALID_CREDENTIALS",
  "ACCOUNT_EXISTS",
]);

function friendly(status: number, code: string, serverMsg?: string): string {
  if (serverMsg && SHOW_SERVER_MESSAGE.has(code)) return serverMsg;
  if (status === 401 || status === 403) return "You are not signed in to this shop. Choose your shop again.";
  if (status === 404) return "We could not find that record.";
  if (status >= 500) return "The server had a problem. Try again in a moment.";
  return serverMsg || "Something went wrong. Try again.";
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH";
  json?: unknown;
  form?: FormData;
  query?: Record<string, string | number | boolean | null | undefined>;
  businessId?: string;
  timeoutMs?: number;
  expect?: "json" | "blob";
}

export async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", json, form, query, timeoutMs = 25_000, expect = "json" } = opts;

  const url = new URL(API_BASE + path);
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v));
    }
  }

  const headers: Record<string, string> = {};
  // Mock-mode tenancy (MOCK_AWS=true). In production this becomes a Cognito Bearer token.
  const bizId = opts.businessId ?? getActiveId();
  if (bizId) headers["X-Business-Id"] = bizId;
  if (json !== undefined) headers["Content-Type"] = "application/json";

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let res: Response;
  try {
    res = await fetch(url.toString(), {
      method,
      headers,
      body: form ?? (json !== undefined ? JSON.stringify(json) : undefined),
      signal: controller.signal,
      cache: "no-store",
    });
  } catch (e) {
    clearTimeout(timer);
    if ((e as Error)?.name === "AbortError") {
      throw new ApiError(0, "TIMEOUT", "This is taking too long. Check your data connection and try again.");
    }
    throw new ApiError(0, "NETWORK", "Can't reach Biashara Score. Check your data connection and try again.");
  }
  clearTimeout(timer);

  if (!res.ok) {
    let body: Partial<ApiErrorBody> | null = null;
    try {
      body = (await res.json()) as ApiErrorBody;
    } catch {
      /* non-JSON error */
    }
    const code = body?.error?.code ?? `HTTP_${res.status}`;
    throw new ApiError(res.status, code, friendly(res.status, code, body?.error?.message));
  }

  if (expect === "blob") return (await res.blob()) as T;
  return (await res.json()) as T;
}

export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  return "Something went wrong. Try again.";
}
