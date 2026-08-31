import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AutomationSignalsList } from "@/features/operations/components/automation-signals-list";
import { useExecutions } from "@/features/automation/hooks/use-executions";
import type { AutomationExecution } from "@/features/automation/types";

vi.mock("@/features/automation/hooks/use-executions", () => ({ useExecutions: vi.fn() }));

function execution(overrides: Partial<AutomationExecution> = {}): AutomationExecution {
  return {
    id: "exec-1",
    organizationId: "org-1",
    jobId: "job-1",
    executionPlanId: null,
    status: "completed",
    executionMode: "manual",
    triggeredBy: "user-1",
    variables: {},
    startedAt: "2026-08-01T10:00:00Z",
    completedAt: "2026-08-01T10:05:00Z",
    timeoutSeconds: null,
    errorMessage: null,
    createdAt: "2026-08-01T09:59:00Z",
    ...overrides,
  };
}

describe("AutomationSignalsList", () => {
  it("shows a calm empty state when nothing has run", () => {
    vi.mocked(useExecutions).mockReturnValue({ data: [], isLoading: false, isError: false } as unknown as ReturnType<typeof useExecutions>);
    render(<AutomationSignalsList organizationId="org-1" selectedExecutionId={null} onSelect={vi.fn()} />);
    expect(screen.getByText("No recent automation activity")).toBeInTheDocument();
  });

  it("surfaces failed/timed-out runs ahead of successful ones", () => {
    vi.mocked(useExecutions).mockReturnValue({
      data: [execution({ id: "ok-1", status: "completed" }), execution({ id: "bad-1", status: "failed" })],
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useExecutions>);

    render(<AutomationSignalsList organizationId="org-1" selectedExecutionId={null} onSelect={vi.fn()} />);
    const items = screen.getAllByText(/^Run /);
    expect(items[0]).toHaveTextContent("bad-1".slice(0, 8));
  });

  it("calls onSelect with the real execution object when clicked", () => {
    const onSelect = vi.fn();
    vi.mocked(useExecutions).mockReturnValue({ data: [execution()], isLoading: false, isError: false } as unknown as ReturnType<typeof useExecutions>);
    render(<AutomationSignalsList organizationId="org-1" selectedExecutionId={null} onSelect={onSelect} />);

    fireEvent.click(screen.getByText(/^Run /));
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: "exec-1" }));
  });
});
