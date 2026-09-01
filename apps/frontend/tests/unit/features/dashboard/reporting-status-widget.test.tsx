import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ReportingStatusWidget } from "@/features/dashboard/components/reporting-status-widget";
import { useReportingStatistics } from "@/features/reporting/hooks/use-reports";

vi.mock("@/features/reporting/hooks/use-reports", () => ({
  useReportingStatistics: vi.fn(),
}));

const mocked = vi.mocked(useReportingStatistics);

describe("ReportingStatusWidget", () => {
  it("shows the four real execution counts §17 asks for", () => {
    mocked.mockReturnValue({
      isLoading: false,
      isError: false,
      data: { totalReports: 2, scheduledExecutions: 1, successfulExecutions: 4, failedExecutions: 1 },
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useReportingStatistics>);

    render(<ReportingStatusWidget organizationId="org-1" />);

    expect(screen.getByText("Reports")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("Scheduled runs")).toBeInTheDocument();
    expect(screen.getByText("Successful runs")).toBeInTheDocument();
    expect(screen.getByText("Failed runs")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Reporting" })).toHaveAttribute("href", "/reporting");
  });

  it("shows the loading skeleton while fetching", () => {
    mocked.mockReturnValue({
      isLoading: true,
      isError: false,
      data: undefined,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useReportingStatistics>);

    render(<ReportingStatusWidget organizationId="org-1" />);
    expect(screen.getByRole("status", { name: "Loading" })).toBeInTheDocument();
  });
});
