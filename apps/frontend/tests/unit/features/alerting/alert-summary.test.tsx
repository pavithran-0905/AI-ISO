import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AlertSummary } from "@/features/alerting/components/alert-summary";
import { useAlerts } from "@/features/alerting/hooks/use-alerts";
import { useAlertStatistics } from "@/features/alerting/hooks/use-alert-statistics";
import type { Alert } from "@/features/alerting/types";

vi.mock("@/features/alerting/hooks/use-alerts", () => ({ useAlerts: vi.fn() }));
vi.mock("@/features/alerting/hooks/use-alert-statistics", () => ({ useAlertStatistics: vi.fn() }));

const mockedAlerts = vi.mocked(useAlerts);
const mockedStats = vi.mocked(useAlertStatistics);

function alert(overrides: Partial<Alert>): Alert {
  return {
    id: "a1",
    organizationId: "org-1",
    projectId: null,
    ruleId: null,
    source: "monitoring",
    severity: "medium",
    status: "open",
    title: "Something happened",
    message: "",
    fingerprint: "fp-1",
    sourceReference: {},
    assignedTo: null,
    triggeredAt: "2026-01-01T00:00:00Z",
    resolvedAt: null,
    closedAt: null,
    ...overrides,
  };
}

describe("AlertSummary", () => {
  it("shows a severity tile per severity actually present, plus real backend-computed metrics", () => {
    mockedAlerts.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [alert({ id: "1", severity: "critical" }), alert({ id: "2", severity: "critical" }), alert({ id: "3", severity: "low" })],
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useAlerts>);
    mockedStats.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        totalAlerts: 3,
        openAlertCount: 3,
        noiseRatio: 0,
        suppressionRate: 0,
        averageResolutionSeconds: null,
        mttaSeconds: 900,
        mttrSeconds: null,
        computedAt: "2026-01-01T00:00:00Z",
      },
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useAlertStatistics>);

    render(<AlertSummary organizationId="org-1" />);

    expect(screen.getByText("Critical")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("Low")).toBeInTheDocument();
    expect(screen.queryByText("High")).not.toBeInTheDocument();
    expect(screen.getByText("Total alerts")).toBeInTheDocument();
    expect(screen.getByText("15m")).toBeInTheDocument();
    expect(screen.getByText("Avg. time to resolve")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("shows an honest empty state when there are no alerts at all", () => {
    mockedAlerts.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [],
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useAlerts>);
    mockedStats.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        totalAlerts: 0,
        openAlertCount: 0,
        noiseRatio: 0,
        suppressionRate: 0,
        averageResolutionSeconds: null,
        mttaSeconds: null,
        mttrSeconds: null,
        computedAt: "2026-01-01T00:00:00Z",
      },
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useAlertStatistics>);

    render(<AlertSummary organizationId="org-1" />);

    expect(screen.getByText("No alerts yet")).toBeInTheDocument();
  });
});
