import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ExecutionTable } from "@/features/automation/components/execution-table";
import type { AutomationExecution } from "@/features/automation/types";

const EXECUTIONS: AutomationExecution[] = [
  {
    id: "e1abc234-0000-0000-0000-000000000000",
    organizationId: "org-1",
    jobId: "j1",
    executionPlanId: null,
    status: "completed",
    executionMode: "immediate",
    triggeredBy: "u1",
    variables: {},
    startedAt: "2026-01-01T00:00:00Z",
    completedAt: "2026-01-01T00:00:05Z",
    timeoutSeconds: null,
    errorMessage: null,
    createdAt: "2026-01-01T00:00:00Z",
  },
];

describe("ExecutionTable", () => {
  it("resolves the job name from the caller-supplied map and computes duration client-side", () => {
    render(
      <ExecutionTable
        executions={EXECUTIONS}
        jobNameById={new Map([["j1", "Patch web fleet"]])}
        sortField="createdAt"
        sortDirection="desc"
        onSortChange={vi.fn()}
      />,
    );

    expect(screen.getAllByRole("link", { name: "Patch web fleet" })[0]).toHaveAttribute(
      "href",
      "/automation/executions/e1abc234-0000-0000-0000-000000000000",
    );
    expect(screen.getAllByText("5.0s")[0]).toBeInTheDocument();
  });

  it("falls back to a short run id when the job is unresolved", () => {
    render(
      <ExecutionTable executions={EXECUTIONS} jobNameById={new Map()} sortField="createdAt" sortDirection="desc" onSortChange={vi.fn()} />,
    );

    expect(screen.getAllByRole("link", { name: "Run e1abc234" })[0]).toBeInTheDocument();
  });
});
