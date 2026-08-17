import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PrimaryNavigation } from "@/components/navigation/primary-navigation";
import { useMobileNavStore } from "@/state/mobile-nav-store";
import { useSidebarStore } from "@/state/sidebar-store";
import { TestQueryProvider } from "../../../query-test-utils";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
}));

function renderNav() {
  return render(
    <TestQueryProvider>
      <PrimaryNavigation />
    </TestQueryProvider>,
  );
}

describe("PrimaryNavigation", () => {
  afterEach(() => {
    useSidebarStore.setState({ collapsed: false, collapsedGroups: {} });
    useMobileNavStore.setState({ open: false });
  });

  it("renders the single-route Overview group as a flat Dashboard link", () => {
    renderNav();
    const link = screen.getByRole("link", { name: /dashboard/i });
    expect(link).toHaveAttribute("href", "/");
    expect(link).toHaveAttribute("aria-current", "page");
  });

  it("renders multi-route groups as expandable headers with their canonical label", () => {
    renderNav();
    expect(screen.getByRole("button", { name: /operations/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /platform/i })).toBeInTheDocument();
  });

  it("shows planned sub-items by default (groups start expanded), each marked Planned and not a link", () => {
    renderNav();
    const nav = screen.getByRole("navigation", { name: "Primary" });
    expect(screen.getByRole("button", { name: /operations/i })).toHaveAttribute("aria-expanded", "true");
    expect(within(nav).getByText("Monitoring")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /monitoring/i })).not.toBeInTheDocument();
    const monitoringRow = within(nav).getByText("Monitoring").closest("div[aria-disabled]");
    expect(monitoringRow).toHaveAttribute("aria-disabled", "true");
    expect(within(monitoringRow as HTMLElement).getByText("Planned")).toBeInTheDocument();
  });

  it("collapses a group's sub-items when its header is clicked", () => {
    renderNav();
    const nav = screen.getByRole("navigation", { name: "Primary" });
    const operationsButton = screen.getByRole("button", { name: /operations/i });
    fireEvent.click(operationsButton);

    expect(operationsButton).toHaveAttribute("aria-expanded", "false");
    expect(within(nav).queryByText("Monitoring")).not.toBeInTheDocument();
  });

  it("collapses to icon-only width and moves labels into hover tooltips", () => {
    useSidebarStore.setState({ collapsed: true });
    renderNav();
    expect(screen.getByRole("navigation", { name: "Primary" })).toHaveClass("w-14");

    const link = screen.getByRole("link");
    expect(link).toHaveTextContent("");

    const dashboardTooltip = screen.getAllByRole("tooltip").find((node) => node.textContent === "Dashboard");
    expect(dashboardTooltip).toBeDefined();
  });

  it("toggles the collapsed state via the collapse/expand button", () => {
    renderNav();
    const toggle = screen.getByRole("button", { name: "Collapse sidebar" });
    fireEvent.click(toggle);
    expect(useSidebarStore.getState().collapsed).toBe(true);
  });

  it("keeps the narrow-viewport drawer closed until the mobile nav store opens it", () => {
    renderNav();
    expect(screen.getByRole("dialog", { hidden: true })).not.toHaveAttribute("open");

    act(() => {
      useMobileNavStore.getState().show();
    });
    expect(screen.getByRole("dialog")).toHaveAttribute("open");
  });

  it("closes the drawer once a real (implemented) link inside it is chosen", () => {
    renderNav();
    act(() => {
      useMobileNavStore.getState().show();
    });

    const drawer = screen.getByRole("dialog");
    fireEvent.click(within(drawer).getByRole("link", { name: /dashboard/i }));

    expect(useMobileNavStore.getState().open).toBe(false);
  });
});
