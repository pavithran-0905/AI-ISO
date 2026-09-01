import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DashboardWidget } from "@/features/dashboard/components/dashboard-widget";

describe("DashboardWidget", () => {
  it("renders title, description, and action link", () => {
    render(
      <DashboardWidget title="Reporting" description="Report activity." action={{ label: "Open Reporting", href: "/reporting" }} isLoading={false} isError={false}>
        <p>content</p>
      </DashboardWidget>,
    );

    expect(screen.getByRole("heading", { name: "Reporting" })).toBeInTheDocument();
    expect(screen.getByText("Report activity.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Reporting" })).toHaveAttribute("href", "/reporting");
    expect(screen.getByText("content")).toBeInTheDocument();
  });

  it("shows a loading skeleton and hides children while isLoading", () => {
    render(
      <DashboardWidget title="Reporting" isLoading isError={false}>
        <p>content</p>
      </DashboardWidget>,
    );

    expect(screen.getByRole("status", { name: "Loading" })).toBeInTheDocument();
    expect(screen.queryByText("content")).not.toBeInTheDocument();
    // The header still renders during loading — the shell itself never disappears (§29).
    expect(screen.getByRole("heading", { name: "Reporting" })).toBeInTheDocument();
  });

  it("shows a retry-capable error state, isolated to this widget, while isError", () => {
    const onRetry = vi.fn();
    render(
      <DashboardWidget title="Reporting" isLoading={false} isError error={new Error("boom")} onRetry={onRetry}>
        <p>content</p>
      </DashboardWidget>,
    );

    expect(screen.queryByText("content")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Reporting" })).toBeInTheDocument();
    screen.getByRole("button", { name: /retry/i }).click();
    expect(onRetry).toHaveBeenCalled();
  });

  it("renders no action link when none is given", () => {
    render(
      <DashboardWidget title="Reporting" isLoading={false} isError={false}>
        <p>content</p>
      </DashboardWidget>,
    );
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});
