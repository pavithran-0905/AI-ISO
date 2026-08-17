import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useAuthStore } from "@/auth/store";
import { UserMenu } from "@/components/navigation/user-menu";
import { TestQueryProvider } from "../../../query-test-utils";

function mockFetchOnce(status: number, body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ status, ok: status >= 200 && status < 300, json: () => Promise.resolve(body) }),
  );
}

function renderMenu() {
  return render(
    <TestQueryProvider>
      <UserMenu />
    </TestQueryProvider>,
  );
}

describe("UserMenu", () => {
  afterEach(() => {
    useAuthStore.getState().clear();
    vi.unstubAllGlobals();
  });

  it("offers only Documentation when unauthenticated (no identity to show)", () => {
    useAuthStore.setState({ status: "unauthenticated" });
    renderMenu();

    fireEvent.click(screen.getByRole("button", { name: "Account menu" }));

    expect(screen.getByRole("menuitem", { name: "Documentation" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "Sign out" })).not.toBeInTheDocument();
  });

  it("shows the real email plus honest 'Not assigned'/'No organization' fallbacks when role/org are unset", async () => {
    useAuthStore.setState({ status: "authenticated", userId: "u1", role: null, organizationId: null });
    mockFetchOnce(200, {
      success: true,
      message: "ok",
      data: {
        id: "u1",
        email: "sarun@example.com",
        display_name: "Sarun",
        is_email_verified: true,
        mfa_enabled: false,
        last_login_at: null,
        created_at: "2026-01-01T00:00:00Z",
      },
      meta: {},
    });

    renderMenu();
    fireEvent.click(screen.getByRole("button", { name: /account menu/i }));

    await waitFor(() => expect(screen.getByText("sarun@example.com")).toBeInTheDocument());
    expect(screen.getByText("Role: Not assigned")).toBeInTheDocument();
    expect(screen.getByText("Organization: No organization")).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Sign out" })).toBeInTheDocument();
  });

  it("clears the session when Sign out is selected", async () => {
    useAuthStore.setState({ status: "authenticated", userId: "u1", role: "operator", organizationId: "org1" });
    mockFetchOnce(200, {
      success: true,
      message: "ok",
      data: {
        id: "u1",
        email: "sarun@example.com",
        display_name: "Sarun",
        is_email_verified: true,
        mfa_enabled: false,
        last_login_at: null,
        created_at: "2026-01-01T00:00:00Z",
      },
      meta: {},
    });

    renderMenu();
    fireEvent.click(screen.getByRole("button", { name: /account menu/i }));
    await waitFor(() => expect(screen.getByRole("menuitem", { name: "Sign out" })).toBeInTheDocument());

    fireEvent.click(screen.getByRole("menuitem", { name: "Sign out" }));

    expect(useAuthStore.getState().status).toBe("unauthenticated");
  });
});
