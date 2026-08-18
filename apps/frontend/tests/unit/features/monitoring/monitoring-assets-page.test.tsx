import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MonitoringAssetsPage } from "@/features/monitoring/pages/monitoring-assets-page";
import { useOrganizationStore } from "@/organization/store";

const push = vi.fn();
const mockSearch = vi.hoisted(() => ({ current: "" }));
vi.mock("next/navigation", () => ({
  usePathname: () => "/monitoring/assets",
  useRouter: () => ({ push }),
  useSearchParams: () => new URLSearchParams(mockSearch.current),
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
      if (url.includes("/inventory/search")) {
        return respond({
          items: [
            {
              id: "a1",
              organization_id: "org-1",
              project_id: null,
              name: "db-01",
              display_name: "Primary DB",
              hostname: "db-01.internal",
              fqdn: null,
              ip_address: null,
              vendor: null,
              manufacturer: null,
              model: null,
              operating_system: null,
              environment: "production",
              asset_type: "database",
              category_id: null,
              class_id: null,
              location_id: null,
              owner_id: null,
              status: "managed",
              health: "healthy",
              lifecycle_state: "operational",
              criticality: "high",
              metadata: {},
              tags: [],
              created_at: "2026-01-01T00:00:00Z",
              updated_at: "2026-01-02T00:00:00Z",
            },
          ],
          pagination: { total: 1, page: 1, page_size: 25, total_pages: 1, has_next: false, has_previous: false },
        });
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    }),
  );
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MonitoringAssetsPage />
    </QueryClientProvider>,
  );
}

describe("MonitoringAssetsPage", () => {
  afterEach(() => {
    useOrganizationStore.setState({ selectedOrganizationId: null });
    push.mockClear();
    mockSearch.current = "";
    vi.unstubAllGlobals();
  });

  it("auto-selects the sole organization and renders the real asset table", async () => {
    mockBackend();
    renderPage();

    await waitFor(() => expect(screen.getByRole("link", { name: "Primary DB" })).toBeInTheDocument());
    expect(screen.getByText("1 asset · page 1 of 1")).toBeInTheDocument();
  });

  it("pushes a URL with the search query so the filtered view is shareable", async () => {
    mockBackend();
    renderPage();

    await waitFor(() => expect(screen.getByLabelText("Search")).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText("Search"), { target: { value: "db-01" } });

    expect(push).toHaveBeenCalledWith("/monitoring/assets?q=db-01");
  });

  it("reads the initial status filter from the URL", async () => {
    mockSearch.current = "status=managed";
    mockBackend();
    renderPage();

    await waitFor(() => expect(screen.getByLabelText("Status")).toHaveValue("managed"));
  });
});
