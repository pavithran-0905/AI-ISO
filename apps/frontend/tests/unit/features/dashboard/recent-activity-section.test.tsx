import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { RecentActivitySection } from "@/features/dashboard/components/recent-activity-section";
import { useExecutions } from "@/features/automation/hooks/use-executions";
import type { AutomationExecution } from "@/features/automation/types";

vi.mock("@/features/automation/hooks/use-executions", () => ({
  useExecutions: vi.fn(),
}));

const mocked = vi.mocked(useExecutions);

function execution(overrides: Partial<AutomationExecution>): AutomationExecution {
  return {
    id: "e1abc234-0000-0000-0000-000000000000",
    organizationId: "org-1",
    jobId: "job-42",
    executionPlanId: null,
    status: "completed",
    executionMode: "immediate",
    triggeredBy: "user-1",
    variables: {},
    startedAt: "2026-01-01T00:00:00Z",
    completedAt: "2026-01-01T00:05:00Z",
    timeoutSeconds: null,
    errorMessage: null,
    createdAt: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function mockExecutions(executions: AutomationExecution[]) {
  mocked.mockReturnValue({
    isLoading: false,
    isError: false,
    data: executions,
    error: null,
    refetch: vi.fn(),
  } as unknown as ReturnType<typeof useExecutions>);
}

describe("RecentActivitySection", () => {
  it("renders each execution's status", () => {
    mockExecutions([execution({})]);

    render(<RecentActivitySection organizationId="org-1" />);

    expect(screen.getByText("Completed")).toBeInTheDocument();
  });

  it("links each execution to its own Automation detail page", () => {
    mockExecutions([execution({})]);

    render(<RecentActivitySection organizationId="org-1" />);

    expect(screen.getByRole("link", { name: /Run e1abc234/ })).toHaveAttribute(
      "href",
      "/automation/executions/e1abc234-0000-0000-0000-000000000000",
    );
  });

  it("falls back to createdAt when a run hasn't started yet", () => {
    mockExecutions([execution({ status: "pending", startedAt: null, completedAt: null })]);

    render(<RecentActivitySection organizationId="org-1" />);

    expect(screen.getByText("Pending")).toBeInTheDocument();
    expect(screen.getByRole("time")).toHaveAttribute("datetime", "2026-01-01T00:00:00Z");
  });

  it("shows an honest empty state, not a generic 'no data'", () => {
    mockExecutions([]);

    render(<RecentActivitySection organizationId="org-1" />);

    expect(screen.getByText("No recent automation activity")).toBeInTheDocument();
  });
});
