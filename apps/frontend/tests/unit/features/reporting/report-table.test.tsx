import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReportTable } from "@/features/reporting/components/report-table";
import type { Report } from "@/features/reporting/types";

const REPORTS: Report[] = [
  {
    id: "r1",
    organizationId: "org-1",
    projectId: null,
    templateId: null,
    name: "Weekly infra summary",
    description: null,
    category: "infrastructure",
    reportType: "summary",
    defaultFormat: "pdf",
    parameterValues: {},
    filters: [],
    enabled: true,
    ownerId: null,
  },
];

function renderTable(overrides: Partial<React.ComponentProps<typeof ReportTable>> = {}) {
  return render(
    <ReportTable reports={REPORTS} favoriteIds={new Set()} onToggleFavorite={vi.fn()} sortField="name" sortDirection="asc" onSortChange={vi.fn()} {...overrides} />,
  );
}

describe("ReportTable", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders every real column, linking to the report's detail page", () => {
    renderTable();

    const table = screen.getByRole("table");
    expect(within(table).getByRole("link", { name: "Weekly infra summary" })).toHaveAttribute("href", "/reporting/reports/r1");
    expect(within(table).getByText("infrastructure")).toBeInTheDocument();
    expect(within(table).getByText("summary")).toBeInTheDocument();
    expect(within(table).getByText("Enabled")).toBeInTheDocument();
  });

  it("calls onSortChange with the clicked column", () => {
    const onSortChange = vi.fn();
    renderTable({ onSortChange });

    fireEvent.click(screen.getByRole("button", { name: /^Report/ }));

    expect(onSortChange).toHaveBeenCalledWith("name");
  });

  it("calls onToggleFavorite with the current favorited state", () => {
    const onToggleFavorite = vi.fn();
    renderTable({ onToggleFavorite, favoriteIds: new Set(["r1"]) });

    fireEvent.click(screen.getAllByRole("button", { name: "Unfavorite report" })[0]);

    expect(onToggleFavorite).toHaveBeenCalledWith("r1", true);
  });
});
