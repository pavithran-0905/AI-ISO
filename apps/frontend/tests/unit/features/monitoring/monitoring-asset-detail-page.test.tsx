import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MonitoringAssetDetailPage } from "@/features/monitoring/pages/monitoring-asset-detail-page";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
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

      if (url.includes("/inventory/assets/a1")) {
        return respond({
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
        });
      }
      if (url.includes("/inventory/relationships")) return respond([]);
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    }),
  );
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MonitoringAssetDetailPage assetId="a1" />
    </QueryClientProvider>,
  );
}

describe("MonitoringAssetDetailPage", () => {
  afterEach(() => {
    push.mockClear();
    vi.unstubAllGlobals();
  });

  it("loads the real asset and renders its identity", async () => {
    mockBackend();
    renderPage();

    await waitFor(() => expect(screen.getByRole("heading", { name: "Primary DB" })).toBeInTheDocument());
    expect(screen.getByText("db-01.internal")).toBeInTheDocument();
  });

  it("navigates back to the Assets list", async () => {
    mockBackend();
    renderPage();

    await waitFor(() => expect(screen.getByRole("button", { name: "Back to Assets" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Back to Assets" }));

    expect(push).toHaveBeenCalledWith("/monitoring/assets");
  });
});
