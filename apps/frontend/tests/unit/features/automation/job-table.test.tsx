import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { JobTable } from "@/features/automation/components/job-table";
import type { AutomationJob } from "@/features/automation/types";

const JOBS: AutomationJob[] = [
  {
    id: "j1",
    organizationId: "org-1",
    projectId: null,
    name: "Patch web fleet",
    description: null,
    automationType: "patch_management",
    playbookType: "shell_script",
    status: "active",
    executionMode: "manual",
    content: "echo hi",
    targetSelector: {},
    variables: {},
    tags: [],
    timeoutSeconds: null,
    ownerId: null,
  },
];

function renderTable(overrides: Partial<React.ComponentProps<typeof JobTable>> = {}) {
  return render(<JobTable jobs={JOBS} sortField="name" sortDirection="asc" onSortChange={vi.fn()} {...overrides} />);
}

describe("JobTable", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders every real column, linking to the automation's detail page", () => {
    renderTable();

    const table = screen.getByRole("table");
    expect(screen.getByRole("link", { name: "Patch web fleet" })).toHaveAttribute("href", "/automation/automations/j1");
    expect(table).toHaveTextContent("patch management");
    expect(table).toHaveTextContent("shell script");
    expect(table).toHaveTextContent("active");
  });

  it("calls onSortChange with the clicked column", () => {
    const onSortChange = vi.fn();
    renderTable({ onSortChange });

    fireEvent.click(screen.getByRole("button", { name: /^Automation/ }));

    expect(onSortChange).toHaveBeenCalledWith("name");
  });

  it("does not render Owner, Last execution, Next run, or Target columns — none exist on the real response", () => {
    renderTable();

    expect(screen.queryByText("Owner")).not.toBeInTheDocument();
    expect(screen.queryByText("Last execution")).not.toBeInTheDocument();
    expect(screen.queryByText("Next scheduled run")).not.toBeInTheDocument();
  });
});
