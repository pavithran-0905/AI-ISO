import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { InfrastructureOverviewWidget } from "@/features/dashboard/components/infrastructure-overview-widget";
import { useInventoryStatistics } from "@/features/infrastructure/hooks/use-statistics";

vi.mock("@/features/infrastructure/hooks/use-statistics", () => ({
  useInventoryStatistics: vi.fn(),
}));

const mocked = vi.mocked(useInventoryStatistics);

describe("InfrastructureOverviewWidget", () => {
  it("shows the real relationship count, and links to Infrastructure and Topology — never a second Assets tile", () => {
    mocked.mockReturnValue({
      isLoading: false,
      isError: false,
      data: { totalAssets: 10, totalRelationships: 4 },
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useInventoryStatistics>);

    render(<InfrastructureOverviewWidget organizationId="org-1" />);

    expect(screen.getByText("Relationships")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
    // KpiGrid's own "Assets" tile already shows the total asset count
    // (§43: avoid a redundant card) — this widget never repeats it.
    expect(screen.queryByText("Assets")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View Infrastructure" })).toHaveAttribute("href", "/infrastructure");
    expect(screen.getByRole("link", { name: "Open Topology" })).toHaveAttribute("href", "/infrastructure/topology");
  });

  it("shows a retry-capable error state on failure", () => {
    mocked.mockReturnValue({
      isLoading: false,
      isError: true,
      data: undefined,
      error: new Error("boom"),
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useInventoryStatistics>);

    render(<InfrastructureOverviewWidget organizationId="org-1" />);
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });
});
