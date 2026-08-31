import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AlertSignalsList } from "@/features/operations/components/alert-signals-list";
import { useAlerts } from "@/features/alerting/hooks/use-alerts";
import type { Alert } from "@/features/alerting/types";

vi.mock("@/features/alerting/hooks/use-alerts", () => ({ useAlerts: vi.fn() }));

function alert(overrides: Partial<Alert> = {}): Alert {
  return {
    id: "a1",
    organizationId: "org-1",
    projectId: null,
    ruleId: null,
    source: "monitoring",
    severity: "high",
    status: "open",
    title: "CPU threshold exceeded",
    message: "CPU above 90%",
    fingerprint: "f1",
    sourceReference: {},
    assignedTo: null,
    triggeredAt: "2026-08-01T10:00:00Z",
    resolvedAt: null,
    closedAt: null,
    ...overrides,
  };
}

describe("AlertSignalsList", () => {
  it("shows only unresolved alerts, sorted by severity", () => {
    vi.mocked(useAlerts).mockReturnValue({
      data: [
        alert({ id: "low", severity: "low", title: "Low severity alert" }),
        alert({ id: "resolved", status: "resolved", title: "Already resolved alert" }),
        alert({ id: "critical", severity: "critical", title: "Critical alert" }),
      ],
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useAlerts>);

    render(<AlertSignalsList organizationId="org-1" selectedAlertId={null} onSelect={vi.fn()} />);
    expect(screen.getByText("Low severity alert")).toBeInTheDocument();
    expect(screen.getByText("Critical alert")).toBeInTheDocument();
    expect(screen.queryByText("Already resolved alert")).not.toBeInTheDocument();
  });

  it("shows a calm empty state when there are no active alerts", () => {
    vi.mocked(useAlerts).mockReturnValue({ data: [], isLoading: false, isError: false } as unknown as ReturnType<typeof useAlerts>);
    render(<AlertSignalsList organizationId="org-1" selectedAlertId={null} onSelect={vi.fn()} />);
    expect(screen.getByText("No active alerts")).toBeInTheDocument();
  });

  it("calls onSelect with the real alert object when clicked, never navigating away", () => {
    const onSelect = vi.fn();
    vi.mocked(useAlerts).mockReturnValue({ data: [alert()], isLoading: false, isError: false } as unknown as ReturnType<typeof useAlerts>);
    render(<AlertSignalsList organizationId="org-1" selectedAlertId={null} onSelect={onSelect} />);

    fireEvent.click(screen.getByText("CPU threshold exceeded"));
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: "a1" }));
  });
});
