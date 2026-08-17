import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useAuthStore } from "@/auth/store";
import { AuthGuard, GuestGuard } from "@/auth/guards";
import { TestQueryProvider } from "../../query-test-utils";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
}));

describe("AuthGuard", () => {
  afterEach(() => {
    useAuthStore.getState().clear();
    replace.mockClear();
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

  it("redirects and renders nothing when unauthenticated", () => {
    useAuthStore.setState({ status: "unauthenticated" });

    render(
      <TestQueryProvider>
        <AuthGuard>
          <p>protected content</p>
        </AuthGuard>
      </TestQueryProvider>,
    );

    expect(screen.queryByText("protected content")).not.toBeInTheDocument();
    expect(replace).toHaveBeenCalledWith("/unauthorized");
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
    useAuthStore.getState().clear();
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

  it("redirects away and renders nothing when already authenticated", () => {
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
});
