import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useAuthStore } from "@/auth/store";
import { useLogout } from "@/auth/use-logout";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

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

describe("useLogout", () => {
  afterEach(() => {
    act(() => {
      useAuthStore.getState().clear();
    });
    push.mockClear();
    vi.unstubAllGlobals();
  });

  it("clears the session and redirects to /login after the backend confirms logout", async () => {
    useAuthStore.setState({ status: "authenticated", accessToken: "t", refreshToken: "r", userId: "u1" });
    mockFetchOnce(200, { success: true, message: "ok", data: { success: true }, meta: {} });

    const { result } = renderHook(() => useLogout(), { wrapper });
    await act(async () => {
      await result.current.logout();
    });

    expect(useAuthStore.getState().status).toBe("unauthenticated");
    expect(useAuthStore.getState().accessToken).toBeNull();
    expect(push).toHaveBeenCalledWith("/login");
  });

  it("still signs the user out locally even when the backend call fails", async () => {
    useAuthStore.setState({ status: "authenticated", accessToken: "t", refreshToken: "r", userId: "u1" });
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    const { result } = renderHook(() => useLogout(), { wrapper });
    await act(async () => {
      await result.current.logout();
    });

    await waitFor(() => expect(useAuthStore.getState().status).toBe("unauthenticated"));
    expect(push).toHaveBeenCalledWith("/login");
  });
});
