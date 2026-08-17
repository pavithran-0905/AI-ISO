import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useAuthStore } from "@/auth/store";
import { useLogin } from "@/auth/use-login";

function wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

function mockFetchOnce(status: number, body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ status, ok: status >= 200 && status < 300, json: () => Promise.resolve(body) }),
  );
}

describe("useLogin", () => {
  afterEach(() => {
    useAuthStore.getState().clear();
    vi.unstubAllGlobals();
  });

  it("establishes the session on a real token result", async () => {
    mockFetchOnce(200, {
      success: true,
      message: "ok",
      data: {
        access_token: "header.eyJzdWIiOiJ1MSIsImlzcyI6ImFpLWlvcyIsImlhdCI6MCwiZXhwIjo5OTk5OTk5OTk5LCJqdGkiOiJqMSJ9.sig",
        refresh_token: "refresh-token",
        token_type: "bearer",
        expires_in: 900,
      },
      meta: {},
    });

    const { result } = renderHook(() => useLogin(), { wrapper });
    result.current.mutate({ email: "sarun@example.com", password: "hunter2" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(useAuthStore.getState().status).toBe("authenticated");
    expect(useAuthStore.getState().accessToken).toContain("header.");
  });

  it("does not establish a session when the backend returns an MFA challenge", async () => {
    mockFetchOnce(200, {
      success: true,
      message: "ok",
      data: { mfa_required: true, mfa_challenge_id: "chal-1" },
      meta: {},
    });

    const { result } = renderHook(() => useLogin(), { wrapper });
    result.current.mutate({ email: "sarun@example.com", password: "hunter2" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(useAuthStore.getState().status).not.toBe("authenticated");
  });

  it("surfaces a rejected mutation on invalid credentials without touching session state", async () => {
    mockFetchOnce(401, {
      success: false,
      message: "Invalid credentials",
      error: { code: "AIIOS-AUTH-0001", details: [] },
      meta: {},
    });

    const { result } = renderHook(() => useLogin(), { wrapper });
    result.current.mutate({ email: "sarun@example.com", password: "wrong" });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(useAuthStore.getState().status).not.toBe("authenticated");
  });
});
