import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { RecentActivitySection } from "@/features/dashboard/components/recent-activity-section";
import { useAutomationExecutions } from "@/features/dashboard/hooks/use-automation-executions";
import type { AutomationExecution } from "@/features/dashboard/types";

vi.mock("@/features/dashboard/hooks/use-automation-executions", () => ({
  useAutomationExecutions: vi.fn(),
}));

const mocked = vi.mocked(useAutomationExecutions);

function execution(overrides: Partial<AutomationExecution>): AutomationExecution {
  return {
    id: "e1",
    organizationId: "org-1",
    jobId: "job-42",
    status: "completed",
    triggeredBy: "user-1",
    startedAt: "2026-01-01T00:00:00Z",
    completedAt: "2026-01-01T00:05:00Z",
    errorMessage: null,
    ...overrides,
  };
}

describe("RecentActivitySection", () => {
  it("renders each execution's job and status", () => {
    mocked.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [execution({})],
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useAutomationExecutions>);

    render(<RecentActivitySection organizationId="org-1" />);

    expect(screen.getByText("Job job-42")).toBeInTheDocument();
    expect(screen.getByText("Completed")).toBeInTheDocument();
  });

  it("shows an honest empty state, not a generic 'no data'", () => {
    mocked.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [],
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useAutomationExecutions>);

    render(<RecentActivitySection organizationId="org-1" />);

    expect(screen.getByText("No recent automation activity")).toBeInTheDocument();
  });
});
