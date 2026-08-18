import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AttentionRequiredSection } from "@/features/dashboard/components/attention-required-section";
import { useAlerts } from "@/features/alerting/hooks/use-alerts";
import type { Alert } from "@/features/alerting/types";

vi.mock("@/features/alerting/hooks/use-alerts", () => ({
  useAlerts: vi.fn(),
}));

const mocked = vi.mocked(useAlerts);

function alert(overrides: Partial<Alert>): Alert {
  return {
    id: "a1",
    organizationId: "org-1",
    projectId: null,
    ruleId: null,
    severity: "medium",
    status: "open",
    title: "Something happened",
    message: "",
    source: "monitoring",
    fingerprint: "fp-1",
    sourceReference: {},
    assignedTo: null,
    triggeredAt: "2026-01-01T00:00:00Z",
    resolvedAt: null,
    closedAt: null,
    ...overrides,
  };
}

function mockAlerts(alerts: Alert[]) {
  mocked.mockReturnValue({
    isLoading: false,
    isError: false,
    data: alerts,
    error: null,
    refetch: vi.fn(),
  } as unknown as ReturnType<typeof useAlerts>);
}

describe("AttentionRequiredSection", () => {
  it("excludes resolved/closed/expired alerts", () => {
    mockAlerts([
      alert({ id: "resolved", status: "resolved", title: "Old issue" }),
      alert({ id: "active", status: "open", title: "Live issue" }),
    ]);

    render(<AttentionRequiredSection organizationId="org-1" />);

    expect(screen.getByText("Live issue")).toBeInTheDocument();
    expect(screen.queryByText("Old issue")).not.toBeInTheDocument();
  });

  it("sorts by severity, most critical first", () => {
    mockAlerts([
      alert({ id: "1", severity: "low", title: "Low severity" }),
      alert({ id: "2", severity: "critical", title: "Critical severity" }),
    ]);

    render(<AttentionRequiredSection organizationId="org-1" />);

    const items = screen.getAllByText(/severity/);
    expect(items[0]).toHaveTextContent("Critical severity");
    expect(items[1]).toHaveTextContent("Low severity");
  });

  it("links each alert to its own Alerting detail page", () => {
    mockAlerts([alert({ id: "a1", title: "Live issue" })]);

    render(<AttentionRequiredSection organizationId="org-1" />);

    expect(screen.getByRole("link", { name: /Live issue/ })).toHaveAttribute("href", "/alerting/alerts/a1");
  });

  it("shows 'No active alerts' rather than a generic empty message", () => {
    mockAlerts([]);
    render(<AttentionRequiredSection organizationId="org-1" />);
    expect(screen.getByText("No active alerts")).toBeInTheDocument();
  });
});
