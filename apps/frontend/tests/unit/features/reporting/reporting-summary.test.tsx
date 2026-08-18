import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ReportingSummary } from "@/features/reporting/components/reporting-summary";
import { useReportingStatistics } from "@/features/reporting/hooks/use-reports";

vi.mock("@/features/reporting/hooks/use-reports", () => ({ useReportingStatistics: vi.fn() }));

const mocked = vi.mocked(useReportingStatistics);

describe("ReportingSummary", () => {
  it("shows real backend-computed counts, never client-derived metrics", () => {
    mocked.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        totalReports: 8,
        totalExecutions: 40,
        successfulExecutions: 35,
        failedExecutions: 5,
        scheduledExecutions: 3,
        totalDownloads: 12,
        totalDistributions: 6,
        failedDistributions: 1,
        averageDurationMs: 2000,
        popularReports: {},
        exportFormatUsage: {},
        templateUsage: {},
        scheduleUsage: {},
        distributionUsage: {},
        computedAt: "2026-01-01T00:00:00Z",
      },
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useReportingStatistics>);

    render(<ReportingSummary organizationId="org-1" />);

    expect(screen.getByText("Reports")).toBeInTheDocument();
    expect(screen.getByText("8")).toBeInTheDocument();
    expect(screen.getByText("Generations")).toBeInTheDocument();
    expect(screen.getByText("40")).toBeInTheDocument();
    expect(screen.getByText("5 failed")).toBeInTheDocument();
    expect(screen.getByText("2.0s")).toBeInTheDocument();
  });
});
