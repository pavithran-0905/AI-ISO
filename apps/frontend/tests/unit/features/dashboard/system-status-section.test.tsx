import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SystemStatusSection } from "@/features/dashboard/components/system-status-section";
import { useGatewayHealth } from "@/features/dashboard/hooks/use-gateway-health";

vi.mock("@/features/dashboard/hooks/use-gateway-health", () => ({
  useGatewayHealth: vi.fn(),
}));

const mocked = vi.mocked(useGatewayHealth);

describe("SystemStatusSection", () => {
  it("renders each real service instance with its own reported status, never assumed healthy", () => {
    mocked.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        overallStatus: "degraded",
        instances: [
          {
            serviceId: "svc-1",
            instanceUrl: "http://alerting-service:8010",
            status: "healthy",
            latencyMs: 12.4,
            error: null,
            checkedAt: "2026-01-01T00:00:00Z",
          },
          {
            serviceId: "svc-2",
            instanceUrl: "http://automation-service:8011",
            status: "degraded",
            latencyMs: null,
            error: "timeout",
            checkedAt: "2026-01-01T00:00:00Z",
          },
        ],
      },
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useGatewayHealth>);

    render(<SystemStatusSection organizationId="org-1" />);

    expect(screen.getByText("http://alerting-service:8010")).toBeInTheDocument();
    expect(screen.getByText("http://automation-service:8011")).toBeInTheDocument();
    expect(screen.getByText("Healthy")).toBeInTheDocument();
    expect(screen.getByText("Degraded")).toBeInTheDocument();
    expect(screen.getByText("12ms")).toBeInTheDocument();
  });

  it("shows an honest empty state when no services are registered", () => {
    mocked.mockReturnValue({
      isLoading: false,
      isError: false,
      data: { overallStatus: "unknown", instances: [] },
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useGatewayHealth>);

    render(<SystemStatusSection organizationId="org-1" />);

    expect(screen.getByText("No registered services yet")).toBeInTheDocument();
  });
});
