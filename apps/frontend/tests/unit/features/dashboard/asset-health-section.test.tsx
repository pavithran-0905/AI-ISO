import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AssetHealthSection } from "@/features/dashboard/components/asset-health-section";
import { useInventoryStatistics } from "@/features/infrastructure/hooks/use-statistics";

vi.mock("@/features/infrastructure/hooks/use-statistics", () => ({
  useInventoryStatistics: vi.fn(),
}));

const mocked = vi.mocked(useInventoryStatistics);

function mockStats(data: unknown) {
  mocked.mockReturnValue({ isLoading: false, isError: false, data, error: null, refetch: vi.fn() } as unknown as ReturnType<
    typeof useInventoryStatistics
  >);
}

describe("AssetHealthSection", () => {
  it("shows an honest empty state when there are no registered assets", () => {
    mockStats({ totalAssets: 0, healthDistribution: {} });
    render(<AssetHealthSection organizationId="org-1" />);
    expect(screen.getByText("No assets registered yet")).toBeInTheDocument();
  });

  it("renders real health counts as a distribution, never gateway-health data", () => {
    mockStats({ totalAssets: 10, healthDistribution: { healthy: 7, warning: 2, critical: 1 } });
    render(<AssetHealthSection organizationId="org-1" />);

    expect(screen.getByText("Healthy")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getByText("Critical")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("links to the real Assets list", () => {
    mockStats({ totalAssets: 10, healthDistribution: { healthy: 10 } });
    render(<AssetHealthSection organizationId="org-1" />);
    expect(screen.getByRole("link", { name: "View Infrastructure" })).toHaveAttribute("href", "/infrastructure/assets");
  });
});
