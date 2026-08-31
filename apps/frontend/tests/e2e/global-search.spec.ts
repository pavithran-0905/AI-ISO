import { expect, test } from "@playwright/test";

import { seedAuthenticatedSession } from "./support/seed-session";

const API = "http://localhost:8027";

function envelope(data: unknown) {
  return JSON.stringify({ success: true, message: "ok", data, meta: {} });
}

async function stubJson(context: Parameters<typeof seedAuthenticatedSession>[0], pattern: string, body: unknown) {
  await context.route(pattern, (route) => route.fulfill({ status: 200, contentType: "application/json", body: envelope(body) }));
}

async function stubEmptySearchBackend(context: Parameters<typeof seedAuthenticatedSession>[0]): Promise<void> {
  await stubJson(context, `${API}/inventory/search*`, { items: [], pagination: { total: 0, page: 1, page_size: 5, total_pages: 0, has_next: false, has_previous: false } });
  await stubJson(context, `${API}/alerts?*`, []);
  await stubJson(context, `${API}/automation/jobs?*`, []);
  await stubJson(context, `${API}/reports?*`, []);
  await stubJson(context, `${API}/ai/conversations*`, []);
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
  vendor: null,
  manufacturer: null,
  model: null,
  operating_system: null,
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
  metadata: {},
  tags: [],
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const ALERT = {
  id: "e2e-alert-1",
  organization_id: "e2e-org",
  project_id: null,
  rule_id: null,
  source: "monitoring",
  severity: "high",
  status: "open",
  title: "CPU threshold exceeded",
  message: "CPU usage on edge-01 exceeded 90%.",
  fingerprint: "f1",
  source_reference: {},
  assigned_to: null,
  triggered_at: "2026-01-01T00:00:00Z",
  resolved_at: null,
  closed_at: null,
};

test("opens with Ctrl+K, searches a real asset, and navigates to it", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await stubEmptySearchBackend(context);
  await stubJson(context, `${API}/inventory/search*`, { items: [ASSET], pagination: { total: 1, page: 1, page_size: 5, total_pages: 1, has_next: false, has_previous: false } });
  await stubJson(context, `${API}/inventory/assets/e2e-asset-1`, ASSET);
  await stubJson(context, `${API}/inventory/relationships*`, []);

  await page.goto("/");
  await page.keyboard.press("Control+k");
  await expect(page.getByRole("dialog", { name: "Command palette" })).toBeVisible();

  await page.getByRole("combobox").fill("edge-01");
  await expect(page.getByRole("option", { name: /edge-01/ })).toBeVisible();
  await page.getByRole("option", { name: /edge-01/ }).click();

  await expect(page).toHaveURL(/\/infrastructure\/assets\/e2e-asset-1/);
});

test("searches for a real alert and navigates to Alerting", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await stubEmptySearchBackend(context);
  await stubJson(context, `${API}/alerts?*`, [ALERT]);
  await stubJson(context, `${API}/alerts/e2e-alert-1`, ALERT);
  await stubJson(context, `${API}/alerts/e2e-alert-1/acknowledgements`, []);
  await stubJson(context, `${API}/alerts/e2e-alert-1/history`, []);
  await stubJson(context, `${API}/alerts/e2e-alert-1/correlations`, []);
  await stubJson(context, `${API}/alerts/e2e-alert-1/notifications`, []);

  await page.goto("/");
  await page.getByRole("button", { name: /^Search…/ }).click();
  await page.getByRole("combobox").fill("cpu threshold");

  await expect(page.getByRole("option", { name: /CPU threshold exceeded/ })).toBeVisible();
  await page.getByRole("option", { name: /CPU threshold exceeded/ }).click();

  await expect(page).toHaveURL(/\/alerting\/alerts\/e2e-alert-1/);
});

test("keyboard navigation moves the highlighted option, and Escape closes the palette", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await stubEmptySearchBackend(context);

  await page.goto("/");
  await page.keyboard.press("Control+k");
  const combobox = page.getByRole("combobox");

  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("ArrowDown");
  await expect(page.getByRole("option", { selected: true })).toBeVisible();

  await combobox.press("Escape");
  await expect(page.getByRole("dialog", { name: "Command palette", includeHidden: true })).not.toBeVisible();
});

test("View all results opens the dedicated Search page, grouped by resource type", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await stubEmptySearchBackend(context);
  await stubJson(context, `${API}/inventory/search*`, { items: [ASSET], pagination: { total: 1, page: 1, page_size: 20, total_pages: 1, has_next: false, has_previous: false } });

  await page.goto("/");
  await page.keyboard.press("Control+k");
  await page.getByRole("combobox").fill("edge-01");
  await expect(page.getByRole("link", { name: "View all results" })).toBeVisible();
  await page.getByRole("link", { name: "View all results" }).click();

  await expect(page).toHaveURL(/\/search\?q=edge-01/);
  await expect(page.getByRole("heading", { name: "Assets" })).toBeVisible();
  await expect(page.getByRole("link", { name: "edge-01 Managed edge-01.internal" })).toBeVisible();
});
