import { expect, test } from "@playwright/test";

import { seedAuthenticatedSession } from "./support/seed-session";

/** The real API host (`config/env.ts`'s own default, `.env`'s
 * `NEXT_PUBLIC_API_BASE_URL`) — every stub below is anchored to it
 * explicitly. A bare `**\/alerts...` glob would also match the
 * frontend's OWN page navigation to `/alerting/alerts/...` (Playwright
 * routes intercept document navigations too, not just XHR/fetch), which
 * silently replaces the whole page with the stub's raw JSON body
 * instead of the app shell. Scoping to the API origin avoids that. */
const API = "http://localhost:8027";

function envelope(data: unknown) {
  return JSON.stringify({ success: true, message: "ok", data, meta: {} });
}

const ONE_ALERT = {
  id: "e2e-alert-1",
  organization_id: "e2e-org",
  project_id: null,
  rule_id: null,
  source: "monitoring",
  severity: "critical",
  status: "open",
  title: "Database unreachable",
  message: "Connection refused on the primary replica.",
  fingerprint: "e2e-fingerprint",
  source_reference: { host: "db-01" },
  assigned_to: null,
  triggered_at: "2026-01-01T00:00:00Z",
  resolved_at: null,
  closed_at: null,
};

const ALERT_STATISTICS = {
  total_alerts: 1,
  open_alert_count: 1,
  noise_ratio: 0,
  suppression_rate: 0,
  average_resolution_seconds: null,
  mtta_seconds: null,
  mttr_seconds: null,
  computed_at: "2026-01-01T00:00:00Z",
};

async function stubJson(context: Parameters<typeof seedAuthenticatedSession>[0], pattern: string, body: unknown) {
  await context.route(pattern, (route) => route.fulfill({ status: 200, contentType: "application/json", body: envelope(body) }));
}

async function stubOneAlertDetail(context: Parameters<typeof seedAuthenticatedSession>[0]) {
  await stubJson(context, `${API}/alerts/e2e-alert-1`, ONE_ALERT);
  await stubJson(context, `${API}/alerts/e2e-alert-1/history`, []);
  await stubJson(context, `${API}/alerts/e2e-alert-1/acknowledgements`, []);
  await stubJson(context, `${API}/alerts/e2e-alert-1/correlations`, []);
  await stubJson(context, `${API}/alerts/e2e-alert-1/notifications`, []);
}

/** Grants the "operator" role for this test only, by overwriting the
 * seeded session's role after `seedAuthenticatedSession` has already
 * run (Playwright applies multiple `addInitScript` calls in
 * registration order, so this one wins). Every other spec keeps the
 * default `role: null` (read-only) seeded session. */
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

test("Alerting is reachable from the sidebar and Overview shows real data", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await stubJson(context, `${API}/alerts?*`, [ONE_ALERT]);
  await stubJson(context, `${API}/alert-statistics*`, ALERT_STATISTICS);
  await stubJson(context, `${API}/maintenance-windows*`, []);

  await page.goto("/");
  await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Alerting" }).click();

  await expect(page).toHaveURL(/\/alerting$/);
  await expect(page.getByRole("heading", { name: "Alerting", level: 1 })).toBeVisible();
  await expect(page.getByText("Total alerts")).toBeVisible();
  await expect(page.getByText("No active maintenance windows")).toBeVisible();
});

test("Dashboard cross-links into Alerting", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await page.goto("/");

  await page.getByRole("link", { name: "View in Alerting" }).click();
  await expect(page).toHaveURL(/\/alerting\/alerts$/);
});

test("alert list, search, and navigation to alert detail", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await stubJson(context, `${API}/alerts?*`, [ONE_ALERT]);
  await stubOneAlertDetail(context);

  await page.goto("/alerting/alerts");

  await expect(page.getByRole("link", { name: "Database unreachable" })).toBeVisible();

  await page.getByLabel("Search").fill("database");
  await expect(page).toHaveURL(/q=database/);
  await expect(page.getByRole("link", { name: "Database unreachable" })).toBeVisible();

  await page.getByRole("link", { name: "Database unreachable" }).click();
  await expect(page).toHaveURL(/\/alerting\/alerts\/e2e-alert-1/);
  await expect(page.getByRole("heading", { name: "Database unreachable" })).toBeVisible();
  await expect(page.getByText("Connection refused on the primary replica.")).toBeVisible();
});

test("a read-only session sees alert detail without mutation controls", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await stubOneAlertDetail(context);

  await page.goto("/alerting/alerts/e2e-alert-1");

  await expect(page.getByRole("heading", { name: "Database unreachable" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Acknowledge" })).not.toBeVisible();
});

test("acknowledging an alert waits for the real backend response and updates the view", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await seedAsOperator(context);
  await stubOneAlertDetail(context);
  await stubJson(context, `${API}/alerts/e2e-alert-1/acknowledge`, { ...ONE_ALERT, status: "acknowledged" });

  await page.goto("/alerting/alerts/e2e-alert-1");

  await page.getByRole("button", { name: "Acknowledge" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("dialog").getByRole("button", { name: "Acknowledge" }).click();

  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(page.getByText("Alert acknowledged")).toBeVisible();
});
