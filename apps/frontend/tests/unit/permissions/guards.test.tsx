import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { useAuthStore } from "@/auth/store";
import { RequirePermission, RequireRole } from "@/permissions/guards";
import { TestQueryProvider } from "../../query-test-utils";

describe("RequireRole", () => {
  afterEach(() => {
    useAuthStore.getState().clear();
  });

  it("renders children when the current role is in the allowed list", () => {
    useAuthStore.setState({ role: "operator" });

    render(
      <TestQueryProvider>
        <RequireRole roles={["operator", "super_admin"]}>
          <p>visible</p>
        </RequireRole>
      </TestQueryProvider>,
    );

    expect(screen.getByText("visible")).toBeInTheDocument();
  });

  it("renders the fallback when the current role is not allowed", () => {
    useAuthStore.setState({ role: "viewer" });

    render(
      <TestQueryProvider>
        <RequireRole roles={["super_admin"]} fallback={<p>denied</p>}>
          <p>visible</p>
        </RequireRole>
      </TestQueryProvider>,
    );

    expect(screen.queryByText("visible")).not.toBeInTheDocument();
    expect(screen.getByText("denied")).toBeInTheDocument();
  });

  it("renders nothing (no fallback given) for a null role", () => {
    useAuthStore.setState({ role: null });

    const { container } = render(
      <TestQueryProvider>
        <RequireRole roles={["super_admin"]}>
          <p>visible</p>
        </RequireRole>
      </TestQueryProvider>,
    );

    expect(container).toBeEmptyDOMElement();
  });
});

describe("RequirePermission", () => {
  afterEach(() => {
    useAuthStore.getState().clear();
  });

  it("renders children when the role's capability set includes the action", () => {
    useAuthStore.setState({ role: "operator" });

    render(
      <TestQueryProvider>
        <RequirePermission action="create">
          <button type="button">New</button>
        </RequirePermission>
      </TestQueryProvider>,
    );

    expect(screen.getByRole("button", { name: "New" })).toBeInTheDocument();
  });

  it("hides children when the role's capability set excludes the action", () => {
    useAuthStore.setState({ role: "viewer" });

    render(
      <TestQueryProvider>
        <RequirePermission action="delete">
          <button type="button">Delete</button>
        </RequirePermission>
      </TestQueryProvider>,
    );

    expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
  });
});
