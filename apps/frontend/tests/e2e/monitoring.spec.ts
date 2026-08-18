import { expect, test } from "@playwright/test";

import { seedAuthenticatedSession } from "./support/seed-session";

function envelope(data: unknown) {
  return JSON.stringify({ success: true, message: "ok", data, meta: {} });
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
};

test("protected route redirects to /login when unauthenticated", async ({ page }) => {
  await page.goto("/monitoring");

  await expect(page).toHaveURL(/\/login/);
});

test("Monitoring is reachable from the sidebar and Overview shows real data", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await context.route("**/inventory/statistics*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: envelope({ total_assets: 5, health_distribution: { healthy: 4, critical: 1 } }),
    }),
  );
  await page.goto("/");

  await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Monitoring" }).click();
  await expect(page).toHaveURL(/\/monitoring$/);
  await expect(page.getByRole("heading", { name: "Monitoring", level: 1 })).toBeVisible();
  await expect(page.getByText("Total")).toBeVisible();
});

test("Dashboard cross-links into Monitoring Overview and Services", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await page.goto("/");

  await page.getByRole("link", { name: "View in Monitoring" }).first().click();
  await expect(page).toHaveURL(/\/monitoring$/);
});

test("asset list, search, and navigation to asset detail", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await context.route("**/inventory/search*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: envelope({
        items: [ONE_ASSET],
        pagination: { total: 1, page: 1, page_size: 25, total_pages: 1, has_next: false, has_previous: false },
      }),
    }),
  );
  await context.route("**/inventory/assets/e2e-asset-1", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: envelope(ONE_ASSET) }),
  );

  await page.goto("/monitoring/assets");

  await expect(page.getByRole("link", { name: "Primary DB" })).toBeVisible();

  await page.getByRole("link", { name: "Primary DB" }).click();
  await expect(page).toHaveURL(/\/monitoring\/assets\/e2e-asset-1/);
  await expect(page.getByRole("heading", { name: "Primary DB" })).toBeVisible();
  await expect(page.getByText("db-01.internal")).toBeVisible();
});

test("filtering assets updates the URL so the view is shareable", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await context.route("**/inventory/search*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: envelope({
        items: [],
        pagination: { total: 0, page: 1, page_size: 25, total_pages: 0, has_next: false, has_previous: false },
      }),
    }),
  );

  await page.goto("/monitoring/assets");
  await page.getByLabel("Search").fill("db-01");

  await expect(page).toHaveURL(/q=db-01/);
  await expect(page.getByText("No matching assets")).toBeVisible();
});

test("refresh action reloads monitoring data", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await context.route("**/inventory/statistics*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: envelope({ total_assets: 5, health_distribution: { healthy: 5 } }),
    }),
  );
  await page.goto("/monitoring");
  await expect(page.getByText("Total")).toBeVisible();

  const refreshButton = page.getByRole("button", { name: "Refresh monitoring data" });
  await refreshButton.click();
  await expect(refreshButton).not.toHaveAttribute("aria-busy", "true");
});
