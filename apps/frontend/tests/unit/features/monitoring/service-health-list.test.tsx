import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ServiceHealthList } from "@/features/monitoring/components/service-health-list";
import { useServiceTopology } from "@/features/monitoring/hooks/use-service-topology";

vi.mock("@/features/monitoring/hooks/use-service-topology", () => ({
  useServiceTopology: vi.fn(),
}));

const mocked = vi.mocked(useServiceTopology);

describe("ServiceHealthList", () => {
  it("renders each service's real topology-derived health, never assumed healthy", () => {
    mocked.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [
        { serviceName: "alerting-service", health: "healthy", fanIn: 3, fanOut: 1, criticality: 0.4, inCycle: false },
        { serviceName: "automation-service", health: "unhealthy", fanIn: 1, fanOut: 5, criticality: 0.8, inCycle: false },
      ],
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useServiceTopology>);

    render(<ServiceHealthList />);

    expect(screen.getByText("alerting-service")).toBeInTheDocument();
    expect(screen.getByText("automation-service")).toBeInTheDocument();
    expect(screen.getByText("Healthy")).toBeInTheDocument();
    expect(screen.getByText("Critical")).toBeInTheDocument();
  });

  it("caps the list when a limit is given", () => {
    mocked.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [
        { serviceName: "svc-a", health: "healthy", fanIn: 0, fanOut: 0, criticality: 0, inCycle: false },
        { serviceName: "svc-b", health: "healthy", fanIn: 0, fanOut: 0, criticality: 0, inCycle: false },
      ],
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useServiceTopology>);

    render(<ServiceHealthList limit={1} />);

    expect(screen.getByText("svc-a")).toBeInTheDocument();
    expect(screen.queryByText("svc-b")).not.toBeInTheDocument();
  });

  it("shows an honest empty state when the topology has no services", () => {
    mocked.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [],
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useServiceTopology>);

    render(<ServiceHealthList />);

    expect(screen.getByText("No services in the topology yet")).toBeInTheDocument();
  });
});
