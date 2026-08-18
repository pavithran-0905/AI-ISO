import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { GatewayLivenessCard } from "@/features/dashboard/components/gateway-liveness-card";
import { useGatewayLiveness } from "@/features/dashboard/hooks/use-gateway-liveness";

vi.mock("@/features/dashboard/hooks/use-gateway-liveness", () => ({
  useGatewayLiveness: vi.fn(),
}));

const mockedUseGatewayLiveness = vi.mocked(useGatewayLiveness);

describe("GatewayLivenessCard", () => {
  it("shows a loading message while fetching", () => {
    mockedUseGatewayLiveness.mockReturnValue({
      isLoading: true,
      isError: false,
      data: undefined,
      error: null,
    } as ReturnType<typeof useGatewayLiveness>);

    render(<GatewayLivenessCard />);

    expect(screen.getByText(/checking gateway status/i)).toBeInTheDocument();
  });

  it("shows an error state when the gateway is unreachable", () => {
    mockedUseGatewayLiveness.mockReturnValue({
      isLoading: false,
      isError: true,
      data: undefined,
      error: new Error("Failed to fetch"),
    } as ReturnType<typeof useGatewayLiveness>);

    render(<GatewayLivenessCard />);

    expect(screen.getByText("Unreachable")).toBeInTheDocument();
    expect(screen.getByText("Failed to fetch")).toBeInTheDocument();
  });

  it("shows liveness details on success", () => {
    mockedUseGatewayLiveness.mockReturnValue({
      isLoading: false,
      isError: false,
      data: { status: "healthy", service: "gateway", version: "0.1.0", environment: "development" },
      error: null,
    } as ReturnType<typeof useGatewayLiveness>);

    render(<GatewayLivenessCard />);

    expect(screen.getByText("healthy")).toBeInTheDocument();
    expect(screen.getByText("gateway")).toBeInTheDocument();
    expect(screen.getByText("0.1.0")).toBeInTheDocument();
    expect(screen.getByText("development")).toBeInTheDocument();
  });
});
