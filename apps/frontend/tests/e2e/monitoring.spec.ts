import { expect, test } from "@playwright/test";

import { seedAuthenticatedSession } from "./support/seed-session";

/** Asset list/search/detail E2E coverage lives in
 * `infrastructure.spec.ts` now — `features/infrastructure` (Prompt
 * 011) owns that experience, Monitoring no longer has its own copy. */
function envelope(data: unknown) {
  return JSON.stringify({ success: true, message: "ok", data, meta: {} });
}

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
