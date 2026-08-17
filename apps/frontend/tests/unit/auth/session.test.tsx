import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/api/client";
import { AuthBootstrap, useSession } from "@/auth/session";
import { useAuthStore } from "@/auth/store";
import { TestQueryProvider } from "../../query-test-utils";

function mockFetchOnce(status: number, body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ status, ok: status >= 200 && status < 300, json: () => Promise.resolve(body) }),
  );
}

describe("AuthBootstrap", () => {
  afterEach(() => {
    useAuthStore.getState().clear();
    vi.unstubAllGlobals();
  });

  it("wires the auth store's access token into the api client's requests", async () => {
    useAuthStore.setState({ accessToken: "wired-token", status: "authenticated" });
    mockFetchOnce(200, { success: true, message: "ok", data: {}, meta: {} });

    render(
      <TestQueryProvider>
        <AuthBootstrap>
          <p>app</p>
        </AuthBootstrap>
      </TestQueryProvider>,
    );

    await apiClient.get("/whoami");

    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.headers.Authorization).toBe("Bearer wired-token");
  });

  it("clears the session when the api client reports a 401", async () => {
    useAuthStore.setState({ accessToken: "expired-token", status: "authenticated" });
    mockFetchOnce(401, {
      success: false,
      message: "expired",
      error: { code: "AIIOS-AUTH-0001", details: [] },
      meta: {},
    });

    render(
      <TestQueryProvider>
        <AuthBootstrap>
          <p>app</p>
        </AuthBootstrap>
      </TestQueryProvider>,
    );

    await expect(apiClient.get("/whoami", { skipRetry: true })).rejects.toBeTruthy();

    await waitFor(() => expect(useAuthStore.getState().status).toBe("unauthenticated"));
  });
});

function SessionProbe() {
  const session = useSession();
  return <p>status:{session.status}</p>;
}

describe("useSession", () => {
  afterEach(() => {
    useAuthStore.getState().clear();
    vi.unstubAllGlobals();
  });

  it("reflects the store's status without fetching a profile when unauthenticated", () => {
    useAuthStore.setState({ status: "unauthenticated" });

    render(
      <TestQueryProvider>
        <SessionProbe />
      </TestQueryProvider>,
    );

    expect(screen.getByText("status:unauthenticated")).toBeInTheDocument();
  });
});
