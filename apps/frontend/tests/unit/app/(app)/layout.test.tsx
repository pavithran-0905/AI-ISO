import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import AppRouteGroupLayout from "@/app/(app)/layout";
import { useAuthStore } from "@/auth/store";
import { TestQueryProvider } from "../../../query-test-utils";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({ push: vi.fn(), replace }),
}));

describe("AppRouteGroupLayout", () => {
  afterEach(() => {
    // `act()` flushes the resulting re-render/effect on the still-mounted
    // previous test's component synchronously, before `replace` is
    // cleared below — see the identical note in auth/guards.test.tsx.
    act(() => {
      useAuthStore.getState().clear();
    });
    replace.mockClear();
  });

  it("redirects to /login and renders nothing (not even the shell) when unauthenticated", () => {
    useAuthStore.setState({ status: "unauthenticated" });

    render(
      <TestQueryProvider>
        <AppRouteGroupLayout>
          <p>page content</p>
        </AppRouteGroupLayout>
      </TestQueryProvider>,
    );

    expect(screen.queryByText("page content")).not.toBeInTheDocument();
    expect(screen.queryByRole("banner")).not.toBeInTheDocument();
    expect(replace).toHaveBeenCalledWith("/login");
  });

  it("renders the shell and page content once authenticated", () => {
    useAuthStore.setState({ status: "authenticated" });

    render(
      <TestQueryProvider>
        <AppRouteGroupLayout>
          <p>page content</p>
        </AppRouteGroupLayout>
      </TestQueryProvider>,
    );

    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByText("page content")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });
});
