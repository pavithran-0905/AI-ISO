import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { HealthSummary } from "@/features/monitoring/components/health-summary";
import { useInventoryStatistics } from "@/features/infrastructure/hooks/use-statistics";

vi.mock("@/features/infrastructure/hooks/use-statistics", () => ({
  useInventoryStatistics: vi.fn(),
}));

const mocked = vi.mocked(useInventoryStatistics);

describe("HealthSummary", () => {
  it("shows total plus only the health states actually present, from real backend-computed counts", () => {
    mocked.mockReturnValue({
      isLoading: false,
      isError: false,
      data: { totalAssets: 12, healthDistribution: { healthy: 10, critical: 2 } },
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useInventoryStatistics>);

    render(<HealthSummary organizationId="org-1" />);

    expect(screen.getByText("Total")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("Healthy")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.getByText("Critical")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.queryByText("Warning")).not.toBeInTheDocument();
  });

  it("shows an honest empty state when there are no assets at all", () => {
    mocked.mockReturnValue({
      isLoading: false,
      isError: false,
      data: { totalAssets: 0, healthDistribution: {} },
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useInventoryStatistics>);

    render(<HealthSummary organizationId="org-1" />);

    expect(screen.getByText("No assets yet")).toBeInTheDocument();
  });
});
