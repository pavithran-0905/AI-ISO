/**
 * The shared API client (docs/frontend Prompt 001 §10 "API ARCHITECTURE").
 *
 * This is the ONLY module in the app allowed to call `fetch()`. Every
 * feature must go through a feature-level API function
 * (`features/<feature>/api/`) that calls the methods here — never `fetch`
 * or another HTTP client directly from a component or hook.
 *
 * Responsibilities implemented here per the prompt's own list: base URL
 * configuration (`@/config/env`), authentication (bearer token, injected
 * via `setAuthTokenProvider` to avoid a circular import with `@/auth`),
 * request headers, correlation/request IDs, timeout, cancellation,
 * response parsing, error normalization, a conservative retry policy, and
 * HTTP status handling (401 triggers `setUnauthorizedHandler`'s callback).
 *
 * Backend contract: every AI-IOS service responds with the
 * `{success, message, data, meta}` / `{success, message, error, meta}`
 * envelope in `@/types/api`. This client unwraps it; callers only ever
 * see `TData` or a thrown `ApiRequestError`.
 */

import { env } from "@/config/env";
import type { ApiResponse } from "@/types/api";

export class ApiRequestError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: string[];

  constructor(status: number, message: string, code: string, details: string[]) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

/** Thrown when a request is aborted by timeout or caller cancellation — kept
 * distinct from `ApiRequestError` since there is no HTTP status/backend
 * error code to report. */
export class ApiTimeoutError extends Error {
  constructor(path: string) {
    super(`Request to ${path} timed out.`);
    this.name = "ApiTimeoutError";
  }
}

/** Thrown when `fetch` itself fails (offline, DNS, connection refused) —
 * distinct from a normalized backend error response. */
export class ApiNetworkError extends Error {
  constructor(path: string, cause: unknown) {
    super(`Network request to ${path} failed.`);
    this.name = "ApiNetworkError";
    this.cause = cause;
  }
}

/** Every AI-IOS backend service's own placeholder for the not-yet-built
 * multi-tenant Organization feature (each service defines this same fixed
 * UUID as its own `DEFAULT_ORGANIZATION_ID`, e.g.
 * `services/authentication-service/app/constants.py`). The gateway's
 * per-request routing (`services/api-gateway-service/app/api/proxy.py`)
 * cannot resolve *any* route — public or not — without an organization:
 * an authenticated call carries one in its JWT claims, but a pre-auth
 * call (login, register, refresh) has no token yet, so this header is
 * the only way the gateway can route it. Sent on every request; the
 * gateway prefers the JWT-derived organization when one is present. */
const DEFAULT_ORGANIZATION_ID = "00000000-0000-0000-0000-000000000001";

const DEFAULT_TIMEOUT_MS = 30_000;
const RETRYABLE_STATUSES = new Set([502, 503, 504]);
const RETRYABLE_METHODS = new Set(["GET", "HEAD"]);
const MAX_RETRIES = 2;
const RETRY_BASE_DELAY_MS = 300;

let authTokenProvider: (() => string | null) | null = null;
let unauthorizedHandler: (() => void) | null = null;

/** Registered once at app startup (see `@/auth/store`) so this module
 * never imports the auth store directly — that would be a circular
 * import, since `@/auth/api` itself calls through this client. */
export function setAuthTokenProvider(provider: () => string | null): void {
  authTokenProvider = provider;
}

/** Registered once at app startup so a 401 response can trigger session
 * cleanup (clear tokens, redirect to login) without this module knowing
 * anything about the auth store's shape. */
export function setUnauthorizedHandler(handler: () => void): void {
  unauthorizedHandler = handler;
}

export interface ApiClientOptions extends Omit<RequestInit, "body"> {
  /** Caller-provided cancellation, combined with the internal timeout signal. */
  signal?: AbortSignal;
  /** Milliseconds before the request is aborted. Defaults to 30s. */
  timeoutMs?: number;
  /** JSON-serializable request body (already-encoded strings pass through). */
  body?: unknown;
  /** Skip attaching the bearer token — for public endpoints (login, health). */
  skipAuth?: boolean;
  /** Skip the retry policy — for non-idempotent calls the caller wants to
   * control precisely, or GETs with side-effect-sensitive semantics. */
  skipRetry?: boolean;
}

function combineSignals(...signals: (AbortSignal | undefined)[]): AbortSignal {
  const controller = new AbortController();
  for (const signal of signals) {
    if (!signal) continue;
    if (signal.aborted) {
      controller.abort(signal.reason);
      break;
    }
    signal.addEventListener("abort", () => controller.abort(signal.reason), { once: true });
  }
  return controller.signal;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function parseErrorBody(response: Response): Promise<{ message: string; code: string; details: string[] }> {
  try {
    const body = (await response.json()) as ApiResponse<unknown>;
    if (!body.success) {
      return { message: body.message, code: body.error.code, details: body.error.details };
    }
    return { message: response.statusText, code: "AIIOS-UNKNOWN", details: [] };
  } catch {
    return { message: response.statusText || "Request failed.", code: "AIIOS-UNKNOWN", details: [] };
  }
}

async function performRequest<TData>(
  path: string,
  method: string,
  options: ApiClientOptions,
): Promise<TData> {
  const requestId = crypto.randomUUID();
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const timeoutController = new AbortController();
  const timeoutHandle = setTimeout(() => timeoutController.abort(), timeoutMs);
  const signal = combineSignals(options.signal, timeoutController.signal);

  const headers: Record<string, string> = {
    Accept: "application/json",
    "X-Request-ID": requestId,
    "X-Correlation-ID": requestId,
    "X-Organization-Id": DEFAULT_ORGANIZATION_ID,
    ...(options.headers as Record<string, string> | undefined),
  };

  const token = options.skipAuth ? null : authTokenProvider?.();
  if (token) headers.Authorization = `Bearer ${token}`;

  let body: BodyInit | undefined;
  if (options.body !== undefined) {
    body = typeof options.body === "string" ? options.body : JSON.stringify(options.body);
    headers["Content-Type"] = "application/json";
  }

  let response: Response;
  try {
    response = await fetch(`${env.apiBaseUrl}${path}`, { ...options, method, headers, body, signal });
  } catch (cause) {
    clearTimeout(timeoutHandle);
    if (timeoutController.signal.aborted) throw new ApiTimeoutError(path);
    if (options.signal?.aborted) throw cause;
    throw new ApiNetworkError(path, cause);
  }
  clearTimeout(timeoutHandle);

  if (response.status === 401 && !options.skipAuth) {
    unauthorizedHandler?.();
  }

  if (!response.ok) {
    const { message, code, details } = await parseErrorBody(response);
    throw new ApiRequestError(response.status, message, code, details);
  }

  if (response.status === 204) return undefined as TData;

  const body_ = (await response.json()) as ApiResponse<TData>;
  if (!body_.success) {
    throw new ApiRequestError(response.status, body_.message, body_.error.code, body_.error.details);
  }
  return body_.data;
}

async function requestWithRetry<TData>(
  path: string,
  method: string,
  options: ApiClientOptions,
): Promise<TData> {
  const canRetry = !options.skipRetry && RETRYABLE_METHODS.has(method);
  let attempt = 0;

  while (true) {
    try {
      return await performRequest<TData>(path, method, options);
    } catch (error) {
      const isRetryableStatus = error instanceof ApiRequestError && RETRYABLE_STATUSES.has(error.status);
      const isRetryableNetworkError = error instanceof ApiNetworkError;
      const shouldRetry = canRetry && attempt < MAX_RETRIES && (isRetryableStatus || isRetryableNetworkError);

      if (!shouldRetry) throw error;
      await sleep(RETRY_BASE_DELAY_MS * 2 ** attempt);
      attempt += 1;
    }
  }
}

export const apiClient = {
  get: <TData>(path: string, options?: ApiClientOptions) =>
    requestWithRetry<TData>(path, "GET", options ?? {}),
  post: <TData>(path: string, body?: unknown, options?: ApiClientOptions) =>
    requestWithRetry<TData>(path, "POST", { ...options, body }),
  put: <TData>(path: string, body?: unknown, options?: ApiClientOptions) =>
    requestWithRetry<TData>(path, "PUT", { ...options, body }),
  patch: <TData>(path: string, body?: unknown, options?: ApiClientOptions) =>
    requestWithRetry<TData>(path, "PATCH", { ...options, body }),
  delete: <TData>(path: string, options?: ApiClientOptions) =>
    requestWithRetry<TData>(path, "DELETE", options ?? {}),
};
