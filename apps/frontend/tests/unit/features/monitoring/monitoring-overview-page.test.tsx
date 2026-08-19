import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MonitoringOverviewPage } from "@/features/monitoring/pages/monitoring-overview-page";
import { useOrganizationStore } from "@/organization/store";

vi.mock("next/navigation", () => ({
  usePathname: () => "/monitoring",
}));

function envelope(data: unknown) {
  return { success: true, message: "ok", data, meta: {} };
}

function mockBackend() {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) => {
      const respond = (data: unknown) =>
        Promise.resolve({ status: 200, ok: true, json: () => Promise.resolve(envelope(data)) });

      if (url.includes("/organizations") && !url.includes("statistics")) {
        return respond([{ id: "org-1", name: "org-1", display_name: "Org One", short_name: null, slug: "org-1", status: "active" }]);
      }
      if (url.includes("/inventory/statistics")) {
        return respond({ total_assets: 5, health_distribution: { healthy: 4, critical: 1 } });
      }
      if (url.includes("/inventory/search")) {
        return respond({
          items: [],
          pagination: { total: 0, page: 1, page_size: 100, total_pages: 0, has_next: false, has_previous: false },
        });
      }
      if (url.includes("/observability/topology")) return respond({ environment: "production", nodes: [] });
      if (url.includes("/observability/events")) return respond({ events: [], page: { next_cursor: null, has_more: false } });
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    }),
  );
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MonitoringOverviewPage />
    </QueryClientProvider>,
  );
}

describe("MonitoringOverviewPage", () => {
  afterEach(() => {
    useOrganizationStore.setState({ selectedOrganizationId: null });
    vi.unstubAllGlobals();
  });

  it("auto-selects the sole organization and renders every real section", async () => {
    mockBackend();
    renderPage();

    expect(screen.getByRole("heading", { name: "Monitoring", level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Services" })).toHaveAttribute("href", "/monitoring/services");

    await waitFor(() => expect(screen.getByText("Total")).toBeInTheDocument());
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("Critical issues")).toBeInTheDocument();
    expect(screen.getByText("Service health")).toBeInTheDocument();
    expect(screen.getByText("Recent events")).toBeInTheDocument();
  });
});
