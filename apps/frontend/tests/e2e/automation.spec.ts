import { expect, test } from "@playwright/test";

import { seedAuthenticatedSession } from "./support/seed-session";

/** The real API host — scoped explicitly for the same reason as
 * `alerting.spec.ts`/`reporting.spec.ts`: a bare `**\/automation/...`
 * glob would also match the frontend's OWN page navigations to
 * `/automation/automations` and `/automation/executions`. */
const API = "http://localhost:8027";

function envelope(data: unknown) {
  return JSON.stringify({ success: true, message: "ok", data, meta: {} });
}

async function stubJson(context: Parameters<typeof seedAuthenticatedSession>[0], pattern: string, body: unknown) {
  await context.route(pattern, (route) => route.fulfill({ status: 200, contentType: "application/json", body: envelope(body) }));
}

/** Grants the "operator" role for this test only — mirrors
 * `alerting.spec.ts`'s own helper. Every other spec keeps the default
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

const ONE_JOB = {
  id: "e2e-job-1",
  organization_id: "e2e-org",
  project_id: null,
  name: "Patch web fleet",
  description: "Applies pending OS patches.",
  automation_type: "patch_management",
  playbook_type: "shell_script",
  status: "active",
  execution_mode: "manual",
  content: "echo hi",
  target_selector: {},
  variables: { region: "us-east" },
  tags: ["prod"],
  timeout_seconds: null,
  owner_id: null,
};

const STATISTICS = {
  total_jobs: 1,
  total_executions: 3,
  success_rate: 0.8,
  failure_rate: 0.2,
  average_runtime_seconds: 45,
  computed_at: "2026-01-01T00:00:00Z",
};

test("Automation is reachable from the sidebar and Overview shows real data", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await stubJson(context, `${API}/automation/statistics*`, STATISTICS);
  await stubJson(context, `${API}/automation/executions?*`, []);
  await stubJson(context, `${API}/automation/jobs?*`, []);

  await page.goto("/");
  await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Automation" }).click();

  await expect(page).toHaveURL(/\/automation$/);
  await expect(page.getByRole("heading", { name: "Automation", level: 1 })).toBeVisible();
  await expect(page.getByText("These figures are a stored snapshot")).toBeVisible();
  await expect(page.getByText("Nothing running")).toBeVisible();
});

test("Dashboard cross-links into Automation", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await page.goto("/");

  await page.getByRole("link", { name: "View in Automation" }).click();
  await expect(page).toHaveURL(/\/automation\/executions$/);
});

test("automation list, navigation to detail, and a read-only session sees no mutation controls", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await stubJson(context, `${API}/automation/jobs?*`, [ONE_JOB]);
  await stubJson(context, `${API}/automation/jobs/e2e-job-1`, ONE_JOB);
  await stubJson(context, `${API}/automation/executions?*`, []);

  await page.goto("/automation/automations");

  await expect(page.getByRole("link", { name: "Patch web fleet" })).toBeVisible();

  await page.getByRole("link", { name: "Patch web fleet" }).click();
  await expect(page).toHaveURL(/\/automation\/automations\/e2e-job-1/);
  await expect(page.getByRole("heading", { name: "Patch web fleet" })).toBeVisible();
  await expect(page.getByText("Applies pending OS patches.")).toBeVisible();

  // Default seeded session has role: null (read-only) — no Run/Edit/Delete.
  await expect(page.getByRole("button", { name: /Run Automation/ })).not.toBeVisible();
});

test("running an automation shows a safety confirmation before it executes", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await seedAsOperator(context);
  await stubJson(context, `${API}/automation/jobs/e2e-job-1`, ONE_JOB);
  await stubJson(context, `${API}/automation/executions?*`, []);
  await stubJson(context, `${API}/automation/jobs/e2e-job-1/execute`, {
    id: "e2e-exec-1",
    organization_id: "e2e-org",
    job_id: "e2e-job-1",
    execution_plan_id: null,
    status: "pending",
    execution_mode: "immediate",
    triggered_by: "e2e-user",
    variables: { region: "us-east" },
    started_at: null,
    completed_at: null,
    timeout_seconds: null,
    error_message: null,
    created_at: "2026-01-01T00:00:00Z",
  });
  await stubJson(context, `${API}/automation/executions/e2e-exec-1`, {
    id: "e2e-exec-1",
    organization_id: "e2e-org",
    job_id: "e2e-job-1",
    execution_plan_id: null,
    status: "pending",
    execution_mode: "immediate",
    triggered_by: "e2e-user",
    variables: { region: "us-east" },
    started_at: null,
    completed_at: null,
    timeout_seconds: null,
    error_message: null,
    created_at: "2026-01-01T00:00:00Z",
  });
  await stubJson(context, `${API}/automation/executions/e2e-exec-1/logs`, []);

  await page.goto("/automation/automations/e2e-job-1");

  await page.getByRole("button", { name: "Run Automation" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: "Run Patch web fleet" })).toBeVisible();

  await dialog.getByRole("button", { name: "Review" }).click();
  await expect(dialog.getByRole("heading", { name: "Confirm this run" })).toBeVisible();
  await expect(dialog.getByText("Patch web fleet")).toBeVisible();

  await dialog.getByRole("button", { name: "Run Automation" }).click();
  await expect(page).toHaveURL(/\/automation\/executions\/e2e-exec-1/);
});
