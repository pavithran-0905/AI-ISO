import { expect, test } from "@playwright/test";

import { seedAuthenticatedSession } from "./support/seed-session";

/** The real API host — every stub below is anchored to it explicitly.
 * A bare `**\/reports...` glob would also match the frontend's OWN page
 * navigation to `/reporting/reports/...` (Playwright routes intercept
 * document navigations too, not just XHR/fetch) — the exact bug fixed
 * for Alerting's own E2E specs (see `alerting.spec.ts`). */
const API = "http://localhost:8027";

function envelope(data: unknown) {
  return JSON.stringify({ success: true, message: "ok", data, meta: {} });
}

async function stubJson(context: Parameters<typeof seedAuthenticatedSession>[0], pattern: string, body: unknown) {
  await context.route(pattern, (route) => route.fulfill({ status: 200, contentType: "application/json", body: envelope(body) }));
}

const ONE_REPORT = {
  id: "e2e-report-1",
  organization_id: "e2e-org",
  project_id: null,
  template_id: null,
  name: "Weekly infra summary",
  description: "A weekly rundown of infrastructure health.",
  category: "infrastructure",
  report_type: "summary",
  default_format: "pdf",
  parameter_values: {},
  filters: [],
  enabled: true,
  owner_id: null,
};

const STATISTICS = {
  total_reports: 1,
  total_executions: 4,
  successful_executions: 4,
  failed_executions: 0,
  scheduled_executions: 0,
  total_downloads: 2,
  total_distributions: 0,
  failed_distributions: 0,
  average_duration_ms: 1200,
  popular_reports: {},
  export_format_usage: {},
  template_usage: {},
  schedule_usage: {},
  distribution_usage: {},
  computed_at: "2026-01-01T00:00:00Z",
};

test("Reporting is reachable from the sidebar and Overview shows real data", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await stubJson(context, `${API}/reports/statistics*`, STATISTICS);
  await stubJson(context, `${API}/reports/history*`, []);
  await stubJson(context, `${API}/reports/favorites/mine*`, []);

  await page.goto("/");
  await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Reporting" }).click();

  await expect(page).toHaveURL(/\/reporting$/);
  await expect(page.getByRole("heading", { name: "Reporting", level: 1 })).toBeVisible();
  const main = page.getByRole("main");
  await expect(main.getByRole("link", { name: "Reports", exact: true })).toHaveAttribute("href", "/reporting/reports");
  await expect(main.getByText("No recent activity")).toBeVisible();
  await expect(main.getByText("No favorite reports")).toBeVisible();
});

test("report list and navigation to report detail", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await stubJson(context, `${API}/reports?*`, [ONE_REPORT]);
  await stubJson(context, `${API}/reports/favorites/mine*`, []);
  await stubJson(context, `${API}/reports/e2e-report-1`, ONE_REPORT);
  await stubJson(context, `${API}/reports/schedules*`, []);
  await stubJson(context, `${API}/reports/e2e-report-1/recipients`, []);
  await stubJson(context, `${API}/reports/history*`, []);

  await page.goto("/reporting/reports");

  await expect(page.getByRole("link", { name: "Weekly infra summary" })).toBeVisible();

  await page.getByRole("link", { name: "Weekly infra summary" }).click();
  await expect(page).toHaveURL(/\/reporting\/reports\/e2e-report-1/);
  await expect(page.getByRole("heading", { name: "Weekly infra summary" })).toBeVisible();
  await expect(page.getByText("A weekly rundown of infrastructure health.")).toBeVisible();
});

test("templates list shows real approval status and navigates to template detail", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  const TEMPLATE = {
    id: "e2e-template-1",
    organization_id: "e2e-org",
    project_id: null,
    category_id: null,
    name: "Infra weekly",
    description: null,
    category: "infrastructure",
    report_type: "summary",
    version_number: "1.0.0",
    status: "approved",
    definition: { title: "Infra weekly", sections: [] },
    branding: {},
    is_system: false,
    approved_by: "e2e-user",
    approved_at: "2026-01-01T00:00:00Z",
  };
  await stubJson(context, `${API}/reports/templates?*`, [TEMPLATE]);
  await stubJson(context, `${API}/reports/templates/e2e-template-1`, TEMPLATE);
  await stubJson(context, `${API}/reports/templates/e2e-template-1/versions`, []);

  await page.goto("/reporting/templates");

  const main = page.getByRole("main");
  await expect(main.getByText("Infra weekly")).toBeVisible();
  await expect(main.getByText("approved", { exact: true })).toBeVisible();

  await main.getByText("Infra weekly").click();
  await expect(page).toHaveURL(/\/reporting\/templates\/e2e-template-1/);
  await expect(page.getByRole("heading", { name: "Infra weekly" })).toBeVisible();
});
