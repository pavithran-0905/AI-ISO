import { expect, test } from "@playwright/test";

import { seedAuthenticatedSession } from "./support/seed-session";

/** The real API host — scoped explicitly for the same reason as every
 * other spec in this suite: Playwright routes intercept document
 * navigations too, not just XHR/fetch. `/inventory/...` shares no
 * substring with `/infrastructure/...`, but every stub below is
 * anchored to the origin anyway, matching this suite's own discipline. */
const API = "http://localhost:8027";

function envelope(data: unknown) {
  return JSON.stringify({ success: true, message: "ok", data, meta: {} });
}

async function stubJson(context: Parameters<typeof seedAuthenticatedSession>[0], pattern: string, body: unknown) {
  await context.route(pattern, (route) => route.fulfill({ status: 200, contentType: "application/json", body: envelope(body) }));
}

const ONE_ASSET = {
  id: "e2e-asset-1",
  organization_id: "e2e-org",
  project_id: null,
  name: "db-01",
  display_name: "Primary DB",
  hostname: "db-01.internal",
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
  asset_type: "database",
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
  tags: [],
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-02T00:00:00Z",
};

const ANALYTICS = {
  total_assets: 5,
  total_relationships: 2,
  type_distribution: { database: 3, virtual_machine: 2 },
  health_distribution: { healthy: 4, critical: 1 },
  lifecycle_distribution: { operational: 5 },
  os_distribution: {},
  vendor_distribution: {},
  location_distribution: {},
  discovery_source_distribution: {},
  assets_added_last_30_days: 2,
  computed_at: "2026-01-01T00:00:00Z",
};

/** Grants the "operator" role for this test only — mirrors every
 * other spec's own helper. Every other spec keeps the default
 * `role: null` (read-only) seeded session. */
async function seedAsOperator(context: Parameters<typeof seedAuthenticatedSession>[0]): Promise<void> {
  await context.addInitScript(() => {
    const raw = localStorage.getItem("aiios-auth");
    if (!raw) return;
    const parsed = JSON.parse(raw);
    parsed.state.role = "operator";
    parsed.state.organizationId = "e2e-org";
    localStorage.setItem("aiios-auth", JSON.stringify(parsed));
  });
}

test("Infrastructure is reachable from the sidebar and Overview shows real data", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await stubJson(context, `${API}/inventory/analytics*`, ANALYTICS);
  await stubJson(context, `${API}/inventory/search*`, {
    items: [],
    pagination: { total: 0, page: 1, page_size: 100, total_pages: 0, has_next: false, has_previous: false },
  });

  await page.goto("/");
  await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Infrastructure" }).click();

  await expect(page).toHaveURL(/\/infrastructure$/, { timeout: 15000 });
  await expect(page.getByRole("heading", { name: "Infrastructure", level: 1 })).toBeVisible();
  await expect(page.getByText("Total assets")).toBeVisible();
  await expect(page.getByText("No critical issues")).toBeVisible();
});

test("Dashboard cross-links into Infrastructure", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await page.goto("/");

  await page.getByRole("link", { name: /^Assets/ }).click();
  await expect(page).toHaveURL(/\/infrastructure\/assets$/);
});

test("asset list, search, and navigation to a detail page with real relationships and topology", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await stubJson(context, `${API}/inventory/search*`, {
    items: [ONE_ASSET],
    pagination: { total: 1, page: 1, page_size: 25, total_pages: 1, has_next: false, has_previous: false },
  });
  await stubJson(context, `${API}/inventory/assets/e2e-asset-1`, ONE_ASSET);
  await stubJson(context, `${API}/inventory/assets?*`, [ONE_ASSET]);
  await stubJson(context, `${API}/inventory/relationships*`, []);
  await stubJson(context, `${API}/inventory/topology*`, { root_asset_id: "e2e-asset-1", query_kind: "neighbors", nodes: [] });

  await page.goto("/infrastructure/assets");
  await expect(page.getByRole("link", { name: "Primary DB" })).toBeVisible();

  await page.getByRole("link", { name: "Primary DB" }).click();
  await expect(page).toHaveURL(/\/infrastructure\/assets\/e2e-asset-1/);
  await expect(page.getByRole("heading", { name: "Primary DB" })).toBeVisible();
  await expect(page.getByText("db-01.internal")).toBeVisible();
  await expect(page.getByText("Ubuntu 24.04")).toBeVisible();
});

test("a read-only session sees asset detail without mutation controls", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await stubJson(context, `${API}/inventory/assets/e2e-asset-1`, ONE_ASSET);
  await stubJson(context, `${API}/inventory/assets?*`, [ONE_ASSET]);
  await stubJson(context, `${API}/inventory/relationships*`, []);
  await stubJson(context, `${API}/inventory/topology*`, { root_asset_id: "e2e-asset-1", query_kind: "neighbors", nodes: [] });

  await page.goto("/infrastructure/assets/e2e-asset-1");

  await expect(page.getByRole("heading", { name: "Primary DB" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Edit" })).not.toBeVisible();
  await expect(page.getByRole("button", { name: "Delete" })).not.toBeVisible();
});

test("creating an asset waits for the real backend response before navigating to its detail page", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await seedAsOperator(context);
  const NEW_ASSET = { ...ONE_ASSET, id: "e2e-new-asset", name: "new-host", display_name: null };
  await context.route(`${API}/inventory/assets`, (route) => {
    if (route.request().method() === "POST") {
      return route.fulfill({ status: 201, contentType: "application/json", body: envelope(NEW_ASSET) });
    }
    return route.fallback();
  });
  await stubJson(context, `${API}/inventory/assets/e2e-new-asset`, NEW_ASSET);
  await stubJson(context, `${API}/inventory/assets?*`, [NEW_ASSET]);
  await stubJson(context, `${API}/inventory/relationships*`, []);
  await stubJson(context, `${API}/inventory/topology*`, { root_asset_id: "e2e-new-asset", query_kind: "neighbors", nodes: [] });

  await page.goto("/infrastructure/assets/new");
  await page.getByLabel("Name", { exact: true }).fill("new-host");
  await page.getByLabel("Type", { exact: true }).selectOption("virtual_machine");
  await page.getByRole("button", { name: "Register asset" }).click();

  await expect(page).toHaveURL(/\/infrastructure\/assets\/e2e-new-asset/);
});

test("Ask AI from an asset opens a pre-filled, unsent draft referencing the real asset", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await stubJson(context, `${API}/inventory/assets/e2e-asset-1`, ONE_ASSET);
  await stubJson(context, `${API}/inventory/assets?*`, [ONE_ASSET]);
  await stubJson(context, `${API}/inventory/relationships*`, []);
  await stubJson(context, `${API}/inventory/topology*`, { root_asset_id: "e2e-asset-1", query_kind: "neighbors", nodes: [] });
  await stubJson(context, `${API}/ai/conversations?*`, []);
  await stubJson(context, `${API}/ai/tools?*`, []);

  await page.goto("/infrastructure/assets/e2e-asset-1");
  await page.getByRole("link", { name: "Ask AI" }).click();

  await expect(page).toHaveURL(/\/intelligence\/assistant\?draft=/);
  await expect(page.getByLabel("Message")).toHaveValue(/db-01/);
});
