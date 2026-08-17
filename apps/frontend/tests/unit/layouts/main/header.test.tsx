import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Header } from "@/layouts/main/header";
import { useMobileNavStore } from "@/state/mobile-nav-store";
import { TestQueryProvider } from "../../../query-test-utils";

// `UserMenu` (rendered inside `Header`) uses `useLogout`, which needs `useRouter`.
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

function renderHeader() {
  return render(
    <TestQueryProvider>
      <Header />
    </TestQueryProvider>,
  );
}

describe("Header", () => {
  afterEach(() => {
    useMobileNavStore.setState({ open: false });
  });

  it("renders the AI-IOS brand and theme toggle within a banner landmark", () => {
    renderHeader();

    const banner = screen.getByRole("banner");
    expect(banner).toHaveTextContent("AI-IOS");
    expect(screen.getByRole("button", { name: "Toggle theme" })).toBeInTheDocument();
  });

  it("renders an environment badge outside production", () => {
    renderHeader();
    // config/env.ts falls back to "development" with no env var set (the test env).
    expect(screen.getByText("development")).toBeInTheDocument();
  });

  it("renders the search/command-palette trigger with a keyboard hint", () => {
    renderHeader();
    expect(screen.getByRole("button", { name: /search pages and commands/i })).toBeInTheDocument();
    expect(screen.getByText("⌘K")).toBeInTheDocument();
  });

  it("renders help, notifications, and account menu triggers", () => {
    renderHeader();
    expect(screen.getByRole("button", { name: "Documentation" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Notifications" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Account menu" })).toBeInTheDocument();
  });

  it("opens the narrow-viewport navigation drawer via its hamburger trigger", () => {
    renderHeader();
    expect(useMobileNavStore.getState().open).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: "Toggle navigation" }));

    expect(useMobileNavStore.getState().open).toBe(true);
  });
});
