import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AssetDetailPage } from "@/features/infrastructure/pages/asset-detail-page";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(""),
}));

function envelope(data: unknown) {
  return { success: true, message: "ok", data, meta: {} };
}

function errorEnvelope(message: string, code: string) {
  return { success: false, message, error: { code, details: [] }, meta: {} };
}

const ASSET_BODY = {
  id: "a1",
  organization_id: "org-1",
  project_id: null,
  name: "edge-01",
  display_name: "edge-01",
  hostname: "edge-01.internal",
  fqdn: null,
  ip_address: null,
  mac_address: null,
  serial_number: null,
  vendor: null,
  manufacturer: null,
  model: null,
  firmware_version: null,
  operating_system: null,
  architecture: null,
  environment: "production",
  asset_type: "physical_server",
  category_id: null,
  class_id: null,
  location_id: null,
  owner_id: null,
  status: "managed",
  health: "healthy",
  lifecycle_state: "operational",
  criticality: "medium",
  current_version: 1,
  metadata: {},
  tags: [],
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-02T00:00:00Z",
};

function renderPage(statusOverride?: { status: number; body: unknown }) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) => {
      if (statusOverride) return Promise.resolve({ status: statusOverride.status, ok: false, json: () => Promise.resolve(statusOverride.body) });
      const respond = (data: unknown) => Promise.resolve({ status: 200, ok: true, json: () => Promise.resolve(envelope(data)) });
      if (url.includes("/inventory/assets/a1")) return respond(ASSET_BODY);
      if (url.includes("/inventory/relationships")) return respond([]);
      if (url.includes("/inventory/topology")) return respond({ root_asset_id: "a1", query_kind: "neighbors", nodes: [] });
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    }),
  );

  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return { ...render(
    <QueryClientProvider client={queryClient}>
      <AssetDetailPage assetId="a1" />
    </QueryClientProvider>,
  ), queryClient };
}

describe("AssetDetailPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the real breadcrumb trail and resource header once loaded", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByRole("heading", { name: "edge-01" })).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "Infrastructure" })).toHaveAttribute("href", "/infrastructure");
    expect(screen.getByRole("link", { name: "Assets" })).toHaveAttribute("href", "/infrastructure/assets");
  });

  it("shows a dedicated not-found state for a real 404, not the generic retry error", async () => {
    renderPage({ status: 404, body: errorEnvelope("Asset not found.", "AIIOS-NOT-FOUND") });
    await waitFor(() => expect(screen.getByText("Asset not found")).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
  });

  it("shows the generic retry-capable error state for a real 500, distinct from not-found", async () => {
    renderPage({ status: 500, body: errorEnvelope("Internal error.", "AIIOS-INTERNAL") });
    await waitFor(() => expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument());
    expect(screen.queryByText("Asset not found")).not.toBeInTheDocument();
  });

  it("refresh invalidates only this resource's own real query keys", async () => {
    const { queryClient } = renderPage();
    await waitFor(() => expect(screen.getByRole("heading", { name: "edge-01" })).toBeInTheDocument());

    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    fireEvent.click(screen.getByRole("button", { name: "Refresh asset data" }));

    await waitFor(() => expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["infrastructure", "assets", "a1"] }));
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["infrastructure", "relationships", "a1"] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["infrastructure", "topology", "a1"] });
  });
});
