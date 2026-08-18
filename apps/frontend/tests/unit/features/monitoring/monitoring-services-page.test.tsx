import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MonitoringServicesPage } from "@/features/monitoring/pages/monitoring-services-page";

vi.mock("next/navigation", () => ({
  usePathname: () => "/monitoring/services",
}));

describe("MonitoringServicesPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the page header and loads real topology data", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        status: 200,
        ok: true,
        json: () =>
          Promise.resolve({
            success: true,
            message: "ok",
            data: { environment: "production", nodes: [{ service_name: "gateway", health: "healthy", fan_in: 0, fan_out: 0, criticality: 0, in_cycle: false }] },
            meta: {},
          }),
      }),
    );

    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <MonitoringServicesPage />
      </QueryClientProvider>,
    );

    expect(screen.getByRole("heading", { name: "Service Health" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("gateway")).toBeInTheDocument());
  });
});
