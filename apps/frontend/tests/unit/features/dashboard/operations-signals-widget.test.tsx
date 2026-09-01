import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useAlerts } from "@/features/alerting/hooks/use-alerts";
import type { Alert } from "@/features/alerting/types";
import { useExecutions } from "@/features/automation/hooks/use-executions";
import type { AutomationExecution } from "@/features/automation/types";
import { OperationsSignalsWidget } from "@/features/dashboard/components/operations-signals-widget";

vi.mock("@/features/alerting/hooks/use-alerts", () => ({ useAlerts: vi.fn() }));
vi.mock("@/features/automation/hooks/use-executions", () => ({ useExecutions: vi.fn() }));

const mockedAlerts = vi.mocked(useAlerts);
const mockedExecutions = vi.mocked(useExecutions);

function alert(overrides: Partial<Alert>): Alert {
  return {
    id: "a1",
    organizationId: "org-1",
    projectId: null,
    ruleId: null,
    severity: "medium",
    status: "open",
    title: "x",
    message: "",
    source: "monitoring",
    fingerprint: "fp",
    sourceReference: {},
    assignedTo: null,
    triggeredAt: "2026-01-01T00:00:00Z",
    resolvedAt: null,
    closedAt: null,
    ...overrides,
  };
}

function execution(overrides: Partial<AutomationExecution>): AutomationExecution {
  return {
    id: "e1",
    organizationId: "org-1",
    automationId: "auto-1",
    status: "completed",
    triggeredBy: null,
    variables: {},
    result: null,
    errorMessage: null,
    startedAt: "2026-01-01T00:00:00Z",
    completedAt: "2026-01-01T00:05:00Z",
    createdAt: "2026-01-01T00:00:00Z",
    ...overrides,
  } as AutomationExecution;
}

describe("OperationsSignalsWidget", () => {
  it("counts unresolved alerts and failed/timed-out runs from already-typed real data", () => {
    mockedAlerts.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [alert({ id: "1", status: "open" }), alert({ id: "2", status: "resolved" })],
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useAlerts>);
    mockedExecutions.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [
        execution({ id: "e1", status: "failed" }),
        execution({ id: "e2", status: "timed_out" }),
        execution({ id: "e3", status: "completed" }),
      ],
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useExecutions>);

    render(<OperationsSignalsWidget organizationId="org-1" />);

    expect(screen.getByText("Unresolved alerts")).toBeInTheDocument();
    expect(screen.getByText("Failed automation runs")).toBeInTheDocument();
    const counts = screen.getAllByText(/^[0-9]+$/).map((el) => el.textContent);
    expect(counts).toEqual(["1", "2"]);
  });

  it("links to the real Operations Workspace, never a duplicate correlation view", () => {
    mockedAlerts.mockReturnValue({ isLoading: false, isError: false, data: [], error: null, refetch: vi.fn() } as unknown as ReturnType<
      typeof useAlerts
    >);
    mockedExecutions.mockReturnValue({ isLoading: false, isError: false, data: [], error: null, refetch: vi.fn() } as unknown as ReturnType<
      typeof useExecutions
    >);

    render(<OperationsSignalsWidget organizationId="org-1" />);
    expect(screen.getByRole("link", { name: "Open Operations Workspace" })).toHaveAttribute("href", "/operations");
  });

  it("shows an isolated error state when either source fails", () => {
    mockedAlerts.mockReturnValue({
      isLoading: false,
      isError: true,
      data: undefined,
      error: new Error("boom"),
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useAlerts>);
    mockedExecutions.mockReturnValue({ isLoading: false, isError: false, data: [], error: null, refetch: vi.fn() } as unknown as ReturnType<
      typeof useExecutions
    >);

    render(<OperationsSignalsWidget organizationId="org-1" />);
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });
});
