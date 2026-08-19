import { expect, test } from "@playwright/test";

import { seedAuthenticatedSession } from "./support/seed-session";

/** Same discipline as `infrastructure.spec.ts`: every stub is anchored
 * to the real API origin, since Playwright routes intercept document
 * navigations too, not just XHR/fetch. */
const API = "http://localhost:8027";

function envelope(data: unknown) {
  return JSON.stringify({ success: true, message: "ok", data, meta: {} });
}

async function stubJson(context: Parameters<typeof seedAuthenticatedSession>[0], pattern: string, body: unknown) {
  await context.route(pattern, (route) => route.fulfill({ status: 200, contentType: "application/json", body: envelope(body) }));
}

function asset(overrides: Record<string, unknown>) {
  return {
    id: "e2e-root",
    organization_id: "e2e-org",
    project_id: null,
    name: "web-01",
    display_name: "web-01",
    hostname: null,
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
    asset_type: "web_server",
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
    ...overrides,
  };
}

const ROOT_ASSET = asset({});
const DB_ASSET = asset({ id: "e2e-db", name: "db-01", display_name: "db-01", asset_type: "database", health: "critical" });

const NEIGHBORS_RESPONSE = {
  root_asset_id: "e2e-root",
  query_kind: "neighbors",
  nodes: [{ id: "e2e-db", name: "db-01", asset_type: "database", distance: 1, relationship_type: "depends_on", outgoing: true }],
};

async function stubTopologyBackend(context: Parameters<typeof seedAuthenticatedSession>[0]) {
  await stubJson(context, `${API}/inventory/assets/e2e-root`, ROOT_ASSET);
  await stubJson(context, `${API}/inventory/assets?*`, [ROOT_ASSET, DB_ASSET]);
  await stubJson(context, `${API}/inventory/topology*`, NEIGHBORS_RESPONSE);
  await stubJson(context, `${API}/inventory/relationships*`, [
    {
      id: "rel-1",
      organization_id: "e2e-org",
      source_asset_id: "e2e-root",
      target_asset_id: "e2e-db",
      relationship_type: "depends_on",
      custom_label: "primary link",
      metadata: {},
    },
  ]);
}

test("Topology prompts for an asset, then searching and selecting a result loads its real graph", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await stubTopologyBackend(context);
  await stubJson(context, `${API}/inventory/search*`, {
    items: [DB_ASSET],
    pagination: { total: 1, page: 1, page_size: 8, total_pages: 1, has_next: false, has_previous: false },
  });

  await page.goto("/infrastructure/topology");
  await expect(page.getByText("Choose an asset to explore its topology")).toBeVisible();

  await page.getByLabel("Search assets").fill("db");
  await page.getByRole("button", { name: /^db-01/ }).click();

  await expect(page).toHaveURL(/\/infrastructure\/topology\?focus=e2e-db/);
});

test("selecting a node in the graph opens its detail panel with a real focus action and a link to full asset detail", async ({
  page,
  context,
}) => {
  await seedAuthenticatedSession(context);
  await stubTopologyBackend(context);

  await page.goto("/infrastructure/topology?focus=e2e-root");
  await expect(page.getByRole("button", { name: /^db-01/ })).toBeVisible();

  await page.getByRole("button", { name: /^db-01/ }).click();
  await expect(page.getByRole("button", { name: "Focus topology on this asset" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open full asset detail" })).toHaveAttribute("href", "/infrastructure/assets/e2e-db");
});

test("focusing on a neighbor issues a real new topology query and updates the URL", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await stubTopologyBackend(context);
  await stubJson(context, `${API}/inventory/assets/e2e-db`, DB_ASSET);
  await context.route(`${API}/inventory/topology*`, (route) => {
    const url = new URL(route.request().url());
    const assetId = url.searchParams.get("asset_id");
    if (assetId === "e2e-db") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({ root_asset_id: "e2e-db", query_kind: "neighbors", nodes: [] }),
      });
    }
    return route.fulfill({ status: 200, contentType: "application/json", body: envelope(NEIGHBORS_RESPONSE) });
  });

  await page.goto("/infrastructure/topology?focus=e2e-root");
  await page.getByRole("button", { name: /^db-01/ }).click();
  await page.getByRole("button", { name: "Focus topology on this asset" }).click();

  await expect(page).toHaveURL(/\/infrastructure\/topology\?focus=e2e-db/);
});

test("switching to List view shows the accessible structured alternative, including Dependencies/Impact tabs", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await stubTopologyBackend(context);

  await page.goto("/infrastructure/topology?focus=e2e-root");
  await page.getByRole("button", { name: "List view" }).click();

  await expect(page.getByRole("tablist", { name: "Topology view" })).toBeVisible();
  await expect(page.getByRole("link", { name: "db-01" })).toBeVisible();
  await expect(page.getByRole("button", { name: /^db-01/ })).not.toBeVisible();
});

test("View in Topology from an asset's own detail page deep-links straight to its focused graph", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await stubTopologyBackend(context);

  await page.goto("/infrastructure/assets/e2e-root");
  await page.getByRole("link", { name: "View in Topology" }).click();

  await expect(page).toHaveURL(/\/infrastructure\/topology\?focus=e2e-root/);
  await expect(page.getByRole("button", { name: /^db-01/ })).toBeVisible();
});

test("Ask AI from a topology node's detail panel opens a pre-filled, unsent draft", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await stubTopologyBackend(context);
  await stubJson(context, `${API}/ai/conversations?*`, []);
  await stubJson(context, `${API}/ai/tools?*`, []);

  await page.goto("/infrastructure/topology?focus=e2e-root");
  await page.getByRole("button", { name: /^db-01/ }).click();
  await page.getByRole("link", { name: "Ask AI" }).click();

  await expect(page).toHaveURL(/\/intelligence\/assistant\?draft=/);
  await expect(page.getByLabel("Message")).toHaveValue(/db-01/);
});
