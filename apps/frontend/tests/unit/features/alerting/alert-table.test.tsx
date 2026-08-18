import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AlertTable } from "@/features/alerting/components/alert-table";
import type { Alert } from "@/features/alerting/types";

const ALERTS: Alert[] = [
  {
    id: "a1",
    organizationId: "org-1",
    projectId: null,
    ruleId: null,
    source: "monitoring",
    severity: "critical",
    status: "open",
    title: "Database unreachable",
    message: "",
    fingerprint: "fp-1",
    sourceReference: {},
    assignedTo: null,
    triggeredAt: "2026-01-02T00:00:00Z",
    resolvedAt: null,
    closedAt: null,
  },
];

function renderTable(overrides: Partial<React.ComponentProps<typeof AlertTable>> = {}) {
  return render(<AlertTable alerts={ALERTS} sortField="triggeredAt" sortDirection="desc" onSortChange={vi.fn()} {...overrides} />);
}

describe("AlertTable", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders every real column, linking to the alert's detail page", () => {
    renderTable();

    const table = screen.getByRole("table");
    expect(within(table).getByRole("link", { name: "Database unreachable" })).toHaveAttribute(
      "href",
      "/alerting/alerts/a1",
    );
    expect(within(table).getByText("monitoring")).toBeInTheDocument();
    expect(within(table).getByText("Critical")).toBeInTheDocument();
    expect(within(table).getByText("open")).toBeInTheDocument();
  });

  it("calls onSortChange with the clicked column", () => {
    const onSortChange = vi.fn();
    renderTable({ onSortChange });

    fireEvent.click(screen.getByRole("button", { name: /^Alert/ }));

    expect(onSortChange).toHaveBeenCalledWith("title");
  });

  it("shows the real alert count", () => {
    renderTable();
    expect(screen.getByText("1 alert")).toBeInTheDocument();
  });
});
