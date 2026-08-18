import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { HealthOverviewSection } from "@/features/dashboard/components/health-overview-section";
import { useGatewayHealth } from "@/features/dashboard/hooks/use-gateway-health";

vi.mock("@/features/dashboard/hooks/use-gateway-health", () => ({
  useGatewayHealth: vi.fn(),
}));

const mocked = vi.mocked(useGatewayHealth);

function mockHealth(instances: { status: string }[]) {
  mocked.mockReturnValue({
    isLoading: false,
    isError: false,
    data: { overallStatus: "healthy", instances },
    error: null,
    refetch: vi.fn(),
  } as unknown as ReturnType<typeof useGatewayHealth>);
}

describe("HealthOverviewSection", () => {
  it("counts instances by status, client-side, from real per-instance data", () => {
    mockHealth([
      { status: "healthy" },
      { status: "healthy" },
      { status: "degraded" },
      { status: "unhealthy" },
    ]);

    render(<HealthOverviewSection organizationId="org-1" />);

    expect(screen.getByText("Healthy")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("Degraded")).toBeInTheDocument();
    expect(screen.getByText("Critical")).toBeInTheDocument();
  });

  it("shows an honest empty state when nothing is registered", () => {
    mockHealth([]);
    render(<HealthOverviewSection organizationId="org-1" />);
    expect(screen.getByText("No registered services yet")).toBeInTheDocument();
  });
});
