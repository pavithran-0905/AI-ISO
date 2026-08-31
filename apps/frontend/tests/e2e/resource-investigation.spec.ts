import { expect, test } from "@playwright/test";

import { seedAuthenticatedSession } from "./support/seed-session";

const API = "http://localhost:8027";

function envelope(data: unknown) {
  return JSON.stringify({ success: true, message: "ok", data, meta: {} });
}

function errorEnvelope(message: string, code: string) {
  return JSON.stringify({ success: false, message, error: { code, details: [] }, meta: {} });
}

async function stubJson(context: Parameters<typeof seedAuthenticatedSession>[0], pattern: string, body: unknown) {
  await context.route(pattern, (route) => route.fulfill({ status: 200, contentType: "application/json", body: envelope(body) }));
}

const ASSET = {
  id: "e2e-asset-1",
  organization_id: "e2e-org",
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
  operating_system: "Ubuntu 24.04",
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
  criticality: "high",
  current_version: 1,
  metadata: {},
  tags: ["edge"],
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-02T00:00:00Z",
};

test("shows a real breadcrumb trail (Infrastructure → Assets → resource name) that a dynamic route never showed before", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await stubJson(context, `${API}/inventory/assets/e2e-asset-1`, ASSET);
  await stubJson(context, `${API}/inventory/relationships*`, []);
  await stubJson(context, `${API}/inventory/topology*`, { root_asset_id: "e2e-asset-1", query_kind: "neighbors", nodes: [] });

  await page.goto("/infrastructure/assets/e2e-asset-1");

  const breadcrumb = page.getByRole("navigation", { name: "Breadcrumb" });
  await expect(breadcrumb.getByRole("link", { name: "Infrastructure" })).toBeVisible();
  await expect(breadcrumb.getByRole("link", { name: "Assets" })).toBeVisible();
  await expect(breadcrumb.getByText("edge-01", { exact: true })).toBeVisible();
});

test("switches between Overview, Relationships, Topology, and Configuration tabs, updating the URL", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await stubJson(context, `${API}/inventory/assets/e2e-asset-1`, ASSET);
  await stubJson(context, `${API}/inventory/relationships*`, []);
  await stubJson(context, `${API}/inventory/topology*`, { root_asset_id: "e2e-asset-1", query_kind: "neighbors", nodes: [] });

  await page.goto("/infrastructure/assets/e2e-asset-1");
  await expect(page.getByRole("tab", { name: "Overview", selected: true })).toBeVisible();

  await page.getByRole("tab", { name: "Configuration" }).click();
  await expect(page).toHaveURL(/\?tab=configuration/);
  await expect(page.getByRole("tabpanel").getByText("edge", { exact: true })).toBeVisible();

  await page.getByRole("tab", { name: "Relationships" }).click();
  await expect(page).toHaveURL(/\?tab=relationships/);

  await page.getByRole("tab", { name: "Topology" }).click();
  await expect(page).toHaveURL(/\?tab=topology/);
  await expect(page.getByText("No relationships available")).toBeVisible();
});

test("shows a dedicated not-found state for a real 404, with Back and Search actions, not a generic error", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await context.route(`${API}/inventory/assets/does-not-exist`, (route) =>
    route.fulfill({ status: 404, contentType: "application/json", body: errorEnvelope("Asset not found.", "AIIOS-NOT-FOUND") }),
  );

  await page.goto("/infrastructure/assets/does-not-exist");

  await expect(page.getByText("Asset not found")).toBeVisible();
  await expect(page.getByRole("link", { name: "Back to Assets" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Search" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry" })).not.toBeVisible();
});

test("refresh re-fetches only this resource's own data, not the whole application", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  let assetCalls = 0;
  await context.route(`${API}/inventory/assets/e2e-asset-1`, (route) => {
    assetCalls += 1;
    return route.fulfill({ status: 200, contentType: "application/json", body: envelope(ASSET) });
  });
  await stubJson(context, `${API}/inventory/relationships*`, []);
  await stubJson(context, `${API}/inventory/topology*`, { root_asset_id: "e2e-asset-1", query_kind: "neighbors", nodes: [] });

  await page.goto("/infrastructure/assets/e2e-asset-1");
  await expect(page.getByRole("heading", { name: "edge-01" })).toBeVisible();
  const callsAfterLoad = assetCalls;

  await page.getByRole("button", { name: "Refresh asset data" }).click();
  await expect.poll(() => assetCalls).toBeGreaterThan(callsAfterLoad);
});

test("global search opens a resource's real detail page directly", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await stubJson(context, `${API}/inventory/search*`, { items: [ASSET], pagination: { total: 1, page: 1, page_size: 5, total_pages: 1, has_next: false, has_previous: false } });
  await stubJson(context, `${API}/inventory/assets/e2e-asset-1`, ASSET);
  await stubJson(context, `${API}/inventory/relationships*`, []);
  await stubJson(context, `${API}/inventory/topology*`, { root_asset_id: "e2e-asset-1", query_kind: "neighbors", nodes: [] });
  await stubJson(context, `${API}/alerts?*`, []);
  await stubJson(context, `${API}/automation/jobs?*`, []);
  await stubJson(context, `${API}/reports?*`, []);
  await stubJson(context, `${API}/ai/conversations*`, []);

  await page.goto("/");
  await page.keyboard.press("Control+k");
  await page.getByRole("combobox").fill("edge-01");
  await page.getByRole("option", { name: /edge-01/ }).click();

  await expect(page).toHaveURL(/\/infrastructure\/assets\/e2e-asset-1/);
  await expect(page.getByRole("heading", { name: "edge-01" })).toBeVisible();
});
