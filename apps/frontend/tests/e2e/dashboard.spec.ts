import { expect, test } from "@playwright/test";

import { seedAuthenticatedSession } from "./support/seed-session";

// The dashboard is a protected route (docs/frontend Prompt 004 §10) —
// these specs exercise its own UI, not the login flow (see
// `auth.spec.ts`), so a session is seeded directly rather than going
// through a real `POST /auth/login` that needs a live backend.
test.beforeEach(async ({ context }) => {
  await seedAuthenticatedSession(context);
});

test("dashboard loads and shows the AI-IOS header", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("banner").getByText("AI-IOS")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
});

test("dashboard fetches gateway liveness data", async ({ page }) => {
  await page.goto("/");

  // The mocked `/health` response resolves near-instantly, so the
  // transient "Checking…" state isn't reliably observable here — it's
  // covered precisely by GatewayLivenessCard's own unit test instead.
  await expect(page.getByText("healthy")).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText("gateway", { exact: true })).toBeVisible();
});

test("dashboard auto-selects the sole organization and renders every real section with its own data", async ({ page }) => {
  await page.goto("/");
  // Scoped to <main> — the sidebar also has a (currently disabled,
  // "Planned") "Users" nav entry that would otherwise make this
  // ambiguous.
  const main = page.getByRole("main");

  await expect(main.getByRole("heading", { name: "Overview", level: 2 })).toBeVisible();
  await expect(main.getByText("Users")).toBeVisible();
  await expect(main.getByText("3", { exact: true })).toBeVisible();

  // Asset Health (§10/§11, Prompt 020) — real, org-scoped
  // `/inventory/statistics`, seeded empty by `seed-session.ts`.
  await expect(main.getByRole("heading", { name: "Asset health" })).toBeVisible();
  await expect(main.getByText("No assets registered yet")).toBeVisible();

  await expect(main.getByRole("heading", { name: "Operational health" })).toBeVisible();
  await expect(main.getByRole("heading", { name: "Attention required" })).toBeVisible();
  await expect(main.getByText("No active alerts")).toBeVisible();
  await expect(main.getByRole("heading", { name: "Recent automation activity" })).toBeVisible();
  await expect(main.getByText("No recent automation activity")).toBeVisible();
  await expect(main.getByRole("heading", { name: "System status" })).toBeVisible();

  // Quick Access (§23, Prompt 020) — real routes from the registry.
  await expect(main.getByRole("heading", { name: "Quick access" })).toBeVisible();
  await expect(main.getByRole("link", { name: "Infrastructure", exact: true })).toBeVisible();
  await expect(main.getByRole("link", { name: "Operations", exact: true })).toBeVisible();

  // The optional widget grid (§26) — Executive mode is the default.
  await expect(main.getByRole("heading", { name: "Additional insights" })).toBeVisible();
  await expect(main.getByRole("heading", { name: "Reporting" })).toBeVisible();
  await expect(main.getByRole("heading", { name: "AI Insight" })).toBeVisible();
});

test("refresh action re-fetches dashboard data", async ({ page }) => {
  await page.goto("/");
  const overviewHeading = page.getByRole("main").getByRole("heading", { name: "Overview", level: 2 });
  await expect(overviewHeading).toBeVisible();

  const refreshButton = page.getByRole("button", { name: "Refresh dashboard" });
  await refreshButton.click();
  await expect(refreshButton).not.toHaveAttribute("aria-busy", "true");
  await expect(overviewHeading).toBeVisible();
});

test("shows the organization picker and switches to its dashboard on selection", async ({ page, context }) => {
  const envelope = (data: unknown) => JSON.stringify({ success: true, message: "ok", data, meta: {} });
  await context.route("**/organizations", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: envelope([
        { id: "e2e-org", name: "e2e-org", display_name: "E2E Org", short_name: null, slug: "e2e-org", status: "active" },
        { id: "e2e-org-2", name: "e2e-org-2", display_name: "E2E Org Two", short_name: null, slug: "e2e-org-2", status: "active" },
      ]),
    }),
  );

  await page.goto("/");

  const overviewHeading = page.getByRole("main").getByRole("heading", { name: "Overview", level: 2 });
  await expect(page.getByText("Choose an organization")).toBeVisible();
  await expect(overviewHeading).not.toBeVisible();

  await page.getByRole("button", { name: "E2E Org", exact: true }).click();

  await expect(overviewHeading).toBeVisible();
});

test("theme toggle switches between light and dark", async ({ page }) => {
  await page.goto("/");

  const html = page.locator("html");
  const toggle = page.getByRole("button", { name: "Toggle theme" });

  const initiallyDark = await html.evaluate((el) => el.classList.contains("dark"));
  await toggle.click();
  await expect(html).toHaveClass(initiallyDark ? /^(?!.*dark).*$/ : /dark/);
});

test("switching to Operations mode swaps which optional widgets are visible", async ({ page }) => {
  await page.goto("/");
  const main = page.getByRole("main");

  await expect(main.getByRole("heading", { name: "Reporting" })).toBeVisible();
  await expect(main.getByRole("heading", { name: "Operations Workspace" })).not.toBeVisible();

  await page.getByRole("radio", { name: "Operations" }).click();
  await expect(page).toHaveURL(/[?&]mode=operations/);

  await expect(main.getByRole("heading", { name: "Operations Workspace" })).toBeVisible();
  await expect(main.getByRole("heading", { name: "Reporting" })).not.toBeVisible();

  // The mode is a real, shareable URL param (§51) — reloading keeps it.
  await page.reload();
  await expect(main.getByRole("heading", { name: "Operations Workspace" })).toBeVisible();
});

test("Quick Access navigates into a real module", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("main").getByRole("link", { name: "Infrastructure", exact: true }).click();
  await expect(page).toHaveURL(/\/infrastructure$/);
});

test("Customize menu hides and restores an optional widget", async ({ page }) => {
  await page.goto("/");
  const main = page.getByRole("main");
  await expect(main.getByRole("heading", { name: "AI Insight" })).toBeVisible();

  await page.getByRole("button", { name: "Customize dashboard" }).click();
  await page.getByRole("checkbox", { name: "AI Insight" }).uncheck();
  await expect(main.getByRole("heading", { name: "AI Insight" })).not.toBeVisible();

  // Persisted (§24) — still hidden after a reload.
  await page.reload();
  await expect(main.getByRole("heading", { name: "AI Insight" })).not.toBeVisible();

  await page.getByRole("button", { name: "Customize dashboard" }).click();
  await page.getByRole("checkbox", { name: "AI Insight" }).check();
  await expect(main.getByRole("heading", { name: "AI Insight" })).toBeVisible();
});

// "Dashboard cross-links into Alerting" is covered by
// `alerting.spec.ts` (that link's own behavior is unchanged here).
