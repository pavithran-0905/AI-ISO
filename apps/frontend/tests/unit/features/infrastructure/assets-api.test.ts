import { afterEach, describe, expect, it, vi } from "vitest";

import { assetsApi } from "@/features/infrastructure/api/assets-api";

function envelope(data: unknown) {
  return { success: true, message: "ok", data, meta: {} };
}

function mockFetchOnce(body: unknown) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ status: 200, ok: true, json: () => Promise.resolve(body) }));
}

const ASSET_BODY = {
  id: "a1",
  organization_id: "org-1",
  project_id: null,
  name: "web-01",
  display_name: null,
  hostname: "web-01.internal",
  fqdn: null,
  ip_address: null,
  mac_address: "AA:BB:CC:DD:EE:FF",
  serial_number: "SN123",
  vendor: null,
  manufacturer: null,
  model: null,
  firmware_version: null,
  operating_system: null,
  architecture: null,
  environment: "production",
  asset_type: "virtual_machine",
  category_id: null,
  class_id: null,
  location_id: null,
  owner_id: null,
  status: "managed",
  health: "healthy",
  lifecycle_state: "operational",
  criticality: "medium",
  current_version: 2,
  metadata: {},
  tags: [],
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-02T00:00:00Z",
};

describe("assetsApi", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("maps AssetResponse's real snake_case fields, including the ones features/monitoring's own narrower type used to drop", async () => {
    mockFetchOnce(envelope(ASSET_BODY));

    const asset = await assetsApi.getById("a1");

    expect(asset.macAddress).toBe("AA:BB:CC:DD:EE:FF");
    expect(asset.serialNumber).toBe("SN123");
    expect(asset.currentVersion).toBe(2);
  });

  it("edits via PATCH, never PUT — see PatchAssetInput's own docstring on the PUT status-reset trap", async () => {
    mockFetchOnce(envelope(ASSET_BODY));

    await assetsApi.patch("a1", { status: "retired" });

    const [url, init] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/inventory/assets/a1");
    expect(init.method).toBe("PATCH");
  });

  it("builds the search query from only the real GET /inventory/search params", async () => {
    mockFetchOnce(envelope({ items: [], pagination: { total: 0, page: 1, page_size: 20, total_pages: 0, has_next: false, has_previous: false } }));

    await assetsApi.search({ organizationId: "org-1", ownerId: "u1", projectId: "p1", assetType: "database" });

    const [url] = vi.mocked(fetch).mock.calls[0] as [string];
    expect(url).toContain("organization_id=org-1");
    expect(url).toContain("owner_id=u1");
    expect(url).toContain("project_id=p1");
    expect(url).toContain("asset_type=database");
  });

  it("soft-deletes via DELETE /inventory/assets/{id}", async () => {
    mockFetchOnce(envelope({ success: true }));

    await assetsApi.remove("a1");

    const [url, init] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/inventory/assets/a1");
    expect(init.method).toBe("DELETE");
  });
});
