import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApiRequestError } from "@/api/client";
import { KpiGrid } from "@/features/dashboard/components/kpi-grid";
import { useOrganizationStatistics } from "@/features/dashboard/hooks/use-organization-statistics";

vi.mock("@/features/dashboard/hooks/use-organization-statistics", () => ({
  useOrganizationStatistics: vi.fn(),
}));

const mocked = vi.mocked(useOrganizationStatistics);

describe("KpiGrid", () => {
  it("renders every real statistic, with no fabricated trend/percentage", () => {
    mocked.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        organizationId: "org-1",
        userCount: 12,
        projectCount: 4,
        assetCount: 88,
        workflowCount: 6,
        automationCount: 21,
        validationCount: 3,
        computedAt: "2026-01-01T00:00:00Z",
      },
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useOrganizationStatistics>);

    render(<KpiGrid organizationId="org-1" />);

    expect(screen.getByText("Users")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("88")).toBeInTheDocument();
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
  });

  it("shows a permission-safe state for a 403", () => {
    mocked.mockReturnValue({
      isLoading: false,
      isError: true,
      data: undefined,
      error: new ApiRequestError(403, "forbidden", "X", []),
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useOrganizationStatistics>);

    render(<KpiGrid organizationId="org-1" />);

    expect(screen.getByText("Access denied")).toBeInTheDocument();
  });
});
