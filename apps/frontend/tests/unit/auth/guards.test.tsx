import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useAuthStore } from "@/auth/store";
import { AuthGuard, GuestGuard, isSafeReturnPath } from "@/auth/guards";
import { TestQueryProvider } from "../../query-test-utils";

const replace = vi.fn();
const mockPathname = vi.hoisted(() => ({ current: "/" }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  usePathname: () => mockPathname.current,
}));

describe("AuthGuard", () => {
  afterEach(() => {
    // `act()` flushes the store-change re-render (and this effect's
    // re-run) synchronously, on the still-mounted previous test's
    // component, before `replace` is cleared below — otherwise that
    // flush happens asynchronously (unwrapped `act` warning) and can
    // land during the *next* test instead.
    act(() => {
      useAuthStore.getState().clear();
    });
    replace.mockClear();
    mockPathname.current = "/";
  });

  it("renders children once authenticated", () => {
    useAuthStore.setState({ status: "authenticated" });

    render(
      <TestQueryProvider>
        <AuthGuard>
          <p>protected content</p>
        </AuthGuard>
      </TestQueryProvider>,
    );

    expect(screen.getByText("protected content")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("redirects to /login and renders nothing when unauthenticated", () => {
    useAuthStore.setState({ status: "unauthenticated" });

    render(
      <TestQueryProvider>
        <AuthGuard>
          <p>protected content</p>
        </AuthGuard>
      </TestQueryProvider>,
    );

    expect(screen.queryByText("protected content")).not.toBeInTheDocument();
    expect(replace).toHaveBeenCalledWith("/login");
  });

  it("includes the attempted path as ?from= so login can return the user there", () => {
    mockPathname.current = "/monitoring";
    useAuthStore.setState({ status: "unauthenticated" });

    render(
      <TestQueryProvider>
        <AuthGuard>
          <p>protected content</p>
        </AuthGuard>
      </TestQueryProvider>,
    );

    expect(replace).toHaveBeenCalledWith("/login?from=%2Fmonitoring");
  });

  it("adds &reason=expired only when the session was cleared by a 401, not a plain unauthenticated visit", () => {
    mockPathname.current = "/monitoring";
    useAuthStore.getState().clear("expired");

    render(
      <TestQueryProvider>
        <AuthGuard>
          <p>protected content</p>
        </AuthGuard>
      </TestQueryProvider>,
    );

    expect(replace).toHaveBeenCalledWith("/login?from=%2Fmonitoring&reason=expired");
  });

  it("does not append &reason=expired for a visitor who was simply never signed in", () => {
    mockPathname.current = "/monitoring";
    useAuthStore.setState({ status: "unauthenticated", lastClearReason: null });

    render(
      <TestQueryProvider>
        <AuthGuard>
          <p>protected content</p>
        </AuthGuard>
      </TestQueryProvider>,
    );

    expect(replace).toHaveBeenCalledWith("/login?from=%2Fmonitoring");
  });

  it("renders nothing (no redirect yet) while idle", () => {
    useAuthStore.setState({ status: "idle" });

    render(
      <TestQueryProvider>
        <AuthGuard>
          <p>protected content</p>
        </AuthGuard>
      </TestQueryProvider>,
    );

    expect(screen.queryByText("protected content")).not.toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });
});

describe("GuestGuard", () => {
  afterEach(() => {
    act(() => {
      useAuthStore.getState().clear();
    });
    replace.mockClear();
  });

  it("renders children when not authenticated", () => {
    useAuthStore.setState({ status: "unauthenticated" });

    render(
      <TestQueryProvider>
        <GuestGuard>
          <p>login form</p>
        </GuestGuard>
      </TestQueryProvider>,
    );

    expect(screen.getByText("login form")).toBeInTheDocument();
  });

  it("redirects away to the default destination and renders nothing when already authenticated", () => {
    useAuthStore.setState({ status: "authenticated" });

    render(
      <TestQueryProvider>
        <GuestGuard>
          <p>login form</p>
        </GuestGuard>
      </TestQueryProvider>,
    );

    expect(screen.queryByText("login form")).not.toBeInTheDocument();
    expect(replace).toHaveBeenCalledWith("/");
  });

  it("redirects to a caller-provided destination instead of the default when given one", () => {
    useAuthStore.setState({ status: "authenticated" });

    render(
      <TestQueryProvider>
        <GuestGuard redirectTo="/monitoring">
          <p>login form</p>
        </GuestGuard>
      </TestQueryProvider>,
    );

    expect(replace).toHaveBeenCalledWith("/monitoring");
  });
});

describe("isSafeReturnPath", () => {
  it("accepts a same-app absolute path", () => {
    expect(isSafeReturnPath("/monitoring")).toBe(true);
  });

  it.each([undefined, null, "", "example.com", "//evil.example", "/\\evil.example", "https://evil.example"])(
    "rejects %p",
    (value) => {
      expect(isSafeReturnPath(value)).toBe(false);
    },
  );
});
