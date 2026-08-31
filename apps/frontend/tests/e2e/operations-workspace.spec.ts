import { expect, test } from "@playwright/test";

import { seedAuthenticatedSession } from "./support/seed-session";

const API = "http://localhost:8027";

function envelope(data: unknown) {
  return JSON.stringify({ success: true, message: "ok", data, meta: {} });
}

async function stubJson(context: Parameters<typeof seedAuthenticatedSession>[0], pattern: string, body: unknown) {
  await context.route(pattern, (route) => route.fulfill({ status: 200, contentType: "application/json", body: envelope(body) }));
}

const ALERT = {
  id: "e2e-alert-1",
  organization_id: "e2e-org",
  project_id: null,
  rule_id: null,
  source: "monitoring",
  severity: "critical",
  status: "open",
  title: "CPU threshold exceeded",
  message: "CPU usage on edge-01 exceeded 90%.",
  fingerprint: "f1",
  source_reference: {},
  assigned_to: null,
  triggered_at: "2026-08-01T10:00:00Z",
  resolved_at: null,
  closed_at: null,
};

const EXECUTION = {
  id: "e2e-exec-1",
  organization_id: "e2e-org",
  job_id: "job-1",
  execution_plan_id: null,
  status: "failed",
  execution_mode: "manual",
  triggered_by: "e2e-user",
  variables: { _target_ids: ["asset-1"] },
  started_at: "2026-08-01T10:00:00Z",
  completed_at: "2026-08-01T10:05:00Z",
  timeout_seconds: null,
  error_message: "Connection refused",
  created_at: "2026-08-01T09:59:00Z",
};

async function stubOperationsBackend(context: Parameters<typeof seedAuthenticatedSession>[0]): Promise<void> {
  await stubJson(context, `${API}/alerts?*`, [ALERT]);
  await stubJson(context, `${API}/automation/executions?*`, [EXECUTION]);
  await stubJson(context, `${API}/compliance/audit?*`, []);
  await stubJson(context, `${API}/alerts/e2e-alert-1/correlations`, []);
  await stubJson(context, `${API}/alerts/e2e-alert-1/history`, []);
}

test("Operations Workspace shows real alert and automation signals, with a calm state when there are none", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await stubJson(context, `${API}/alerts?*`, []);
  await stubJson(context, `${API}/automation/executions?*`, []);
  await stubJson(context, `${API}/compliance/audit?*`, []);

  await page.goto("/operations");
  await expect(page.getByRole("heading", { name: "Operations Workspace" })).toBeVisible();
  await expect(page.getByText("No active issues detected in this scope")).toBeVisible();
});

test("selecting an alert opens its real investigation context, with actions and related alerts", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  // Mutation controls (Acknowledge/Resolve/...) are gated by this
  // frontend's own coarse role model — "operator" is the same role
  // `alerting.spec.ts` seeds for its own equivalent assertion.
  await context.addInitScript(() => {
    const raw = localStorage.getItem("aiios-auth");
    if (!raw) return;
    const parsed = JSON.parse(raw);
    parsed.state.role = "operator";
    parsed.state.organizationId = "e2e-org";
    localStorage.setItem("aiios-auth", JSON.stringify(parsed));
  });
  await stubOperationsBackend(context);

  await page.goto("/operations");
  await page.getByText("CPU threshold exceeded").click();

  await expect(page).toHaveURL(/\?signal=alert%3Ae2e-alert-1/);
  await expect(page.getByRole("link", { name: "Open Alert" })).toHaveAttribute("href", "/alerting/alerts/e2e-alert-1");
  await expect(page.getByText("No correlated alerts")).toBeVisible();
  await expect(page.getByRole("button", { name: "Acknowledge" })).toBeVisible();
});

test("selecting an automation run shows its real targets, never a fabricated resource link", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await stubOperationsBackend(context);

  await page.goto("/operations");
  await page.getByText(/^Run e2e-exec/).click();

  await expect(page).toHaveURL(/\?signal=execution%3Ae2e-exec-1/);
  await expect(page.getByText("Connection refused")).toBeVisible();
  await expect(page.getByText("asset-1")).toBeVisible();
  await expect(page.getByRole("link", { name: "asset-1" })).toHaveCount(0);
});

test("reloading a shared investigation URL restores the same selected alert", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await stubOperationsBackend(context);

  await page.goto("/operations?signal=alert:e2e-alert-1");
  await expect(page.getByRole("link", { name: "Open Alert" })).toBeVisible();
});

test("View full activity opens Audit & Activity, and Investigate with AI opens a real draft", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await context.addInitScript(() => {
    const raw = localStorage.getItem("aiios-auth");
    if (!raw) return;
    const parsed = JSON.parse(raw);
    parsed.state.role = "organization_admin";
    parsed.state.organizationId = "e2e-org";
    localStorage.setItem("aiios-auth", JSON.stringify(parsed));
  });
  await stubOperationsBackend(context);

  await page.goto("/operations");
  await page.getByRole("link", { name: "View full activity" }).click();
  await expect(page).toHaveURL(/\/audit\/activity/);

  await page.goto("/operations");
  await page.getByRole("link", { name: /Ask AI/ }).click();
  await expect(page).toHaveURL(/\/intelligence\/assistant\?draft=/);
});

test("Operations Workspace is reachable via global search", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await stubOperationsBackend(context);

  await page.goto("/");
  await page.keyboard.press("Control+k");
  await page.getByRole("combobox").fill("operations workspace");
  await expect(page.getByRole("option", { name: /Operations Workspace/ })).toBeVisible();
  await page.getByRole("option", { name: /Operations Workspace/ }).click();

  await expect(page).toHaveURL(/\/operations$/);
});
