import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiNetworkError,
  ApiRequestError,
  ApiTimeoutError,
  apiClient,
  setAuthTokenProvider,
  setUnauthorizedHandler,
} from "@/api/client";

function mockFetchOnce(status: number, body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      status,
      ok: status >= 200 && status < 300,
      json: () => Promise.resolve(body),
    }),
  );
}

const OK_ENVELOPE = (data: unknown) => ({
  success: true,
  message: "ok",
  data,
  meta: { request_id: "abc", timestamp: "2026-01-01T00:00:00Z" },
});

describe("apiClient", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    setAuthTokenProvider(() => null);
    setUnauthorizedHandler(() => {});
  });

  it("returns the data payload on a successful GET", async () => {
    mockFetchOnce(200, OK_ENVELOPE({ status: "healthy" }));

    const result = await apiClient.get<{ status: string }>("/health");

    expect(result).toEqual({ status: "healthy" });
  });

  it("sends request ID and correlation ID headers", async () => {
    mockFetchOnce(200, OK_ENVELOPE({}));

    await apiClient.get("/health");

    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.headers["X-Request-ID"]).toBeTruthy();
    expect(init.headers["X-Correlation-ID"]).toBe(init.headers["X-Request-ID"]);
  });

  it("throws ApiRequestError with structured details on a non-ok response", async () => {
    mockFetchOnce(503, {
      success: false,
      message: "Service is not ready.",
      error: { code: "AIIOS-GATEWAY-0001", details: ["dependency down"] },
      meta: { request_id: "abc", timestamp: "2026-01-01T00:00:00Z" },
    });

    await expect(apiClient.get("/readiness", { skipRetry: true })).rejects.toMatchObject({
      status: 503,
      code: "AIIOS-GATEWAY-0001",
      details: ["dependency down"],
      message: "Service is not ready.",
    });
  });

  it("throws ApiRequestError instances specifically", async () => {
    mockFetchOnce(400, {
      success: false,
      message: "Invalid input.",
      error: { code: "AIIOS-VAL-0001", details: [] },
      meta: { request_id: "abc", timestamp: "2026-01-01T00:00:00Z" },
    });

    await expect(apiClient.get("/x", { skipRetry: true })).rejects.toBeInstanceOf(ApiRequestError);
  });

  it("attaches the bearer token when a provider is registered", async () => {
    setAuthTokenProvider(() => "token-123");
    mockFetchOnce(200, OK_ENVELOPE({}));

    await apiClient.get("/protected");

    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.headers.Authorization).toBe("Bearer token-123");
  });

  it("does not attach a token when skipAuth is set", async () => {
    setAuthTokenProvider(() => "token-123");
    mockFetchOnce(200, OK_ENVELOPE({}));

    await apiClient.get("/public", { skipAuth: true });

    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.headers.Authorization).toBeUndefined();
  });

  it("invokes the unauthorized handler on a 401 response", async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    mockFetchOnce(401, {
      success: false,
      message: "Unauthorized.",
      error: { code: "AIIOS-AUTH-0001", details: [] },
      meta: { request_id: "abc", timestamp: "2026-01-01T00:00:00Z" },
    });

    await expect(apiClient.get("/protected", { skipRetry: true })).rejects.toBeInstanceOf(ApiRequestError);
    expect(handler).toHaveBeenCalledOnce();
  });

  it("does not invoke the unauthorized handler when skipAuth is set", async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    mockFetchOnce(401, {
      success: false,
      message: "Unauthorized.",
      error: { code: "AIIOS-AUTH-0001", details: [] },
      meta: { request_id: "abc", timestamp: "2026-01-01T00:00:00Z" },
    });

    await expect(
      apiClient.get("/login-adjacent", { skipAuth: true, skipRetry: true }),
    ).rejects.toBeInstanceOf(ApiRequestError);
    expect(handler).not.toHaveBeenCalled();
  });

  it("serializes a JSON body and sets Content-Type on POST", async () => {
    mockFetchOnce(200, OK_ENVELOPE({ id: "1" }));

    await apiClient.post("/things", { name: "widget" });

    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ name: "widget" }));
    expect(init.headers["Content-Type"]).toBe("application/json");
  });

  it("returns undefined for a 204 No Content response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ status: 204, ok: true, json: () => Promise.resolve(undefined) }),
    );

    const result = await apiClient.delete("/things/1");

    expect(result).toBeUndefined();
  });

  it("normalizes a fetch rejection into ApiNetworkError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
    );

    await expect(apiClient.get("/health", { skipRetry: true })).rejects.toBeInstanceOf(ApiNetworkError);
  });

  it("aborts and throws ApiTimeoutError when the timeout elapses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string, init: RequestInit) => {
        return new Promise((_resolve, reject) => {
          init.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
        });
      }),
    );

    await expect(apiClient.get("/slow", { timeoutMs: 5, skipRetry: true })).rejects.toBeInstanceOf(
      ApiTimeoutError,
    );
  });

  it("retries a GET on a 503 up to the retry limit, then succeeds", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ status: 503, ok: false, json: () => Promise.resolve({ success: false, message: "down", error: { code: "X", details: [] }, meta: {} }) })
      .mockResolvedValueOnce({ status: 200, ok: true, json: () => Promise.resolve(OK_ENVELOPE({ ok: true })) });
    vi.stubGlobal("fetch", fetchMock);

    const result = await apiClient.get<{ ok: boolean }>("/flaky");

    expect(result).toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("does not retry a POST even on a retryable status", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      status: 503,
      ok: false,
      json: () => Promise.resolve({ success: false, message: "down", error: { code: "X", details: [] }, meta: {} }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiClient.post("/things", {})).rejects.toBeInstanceOf(ApiRequestError);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
