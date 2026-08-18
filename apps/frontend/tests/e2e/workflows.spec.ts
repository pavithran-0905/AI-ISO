import { expect, test } from "@playwright/test";

import { seedAuthenticatedSession } from "./support/seed-session";

/** Scoped to the real API host — same reasoning as `automation.spec.ts`:
 * the frontend has real pages at `/workflows` and
 * `/workflows/instances` that a bare glob would also intercept. */
const API = "http://localhost:8027";

function envelope(data: unknown) {
  return JSON.stringify({ success: true, message: "ok", data, meta: {} });
}

async function stubJson(context: Parameters<typeof seedAuthenticatedSession>[0], pattern: string, body: unknown) {
  await context.route(pattern, (route) => route.fulfill({ status: 200, contentType: "application/json", body: envelope(body) }));
}

const ONE_WORKFLOW = {
  id: "e2e-workflow-1",
  organization_id: "e2e-org",
  project_id: null,
  workflow_key: "onboard-server",
  name: "Onboard server",
  description: "Provisions and registers a new server.",
  owner: "platform-team",
  tags: ["provisioning"],
  default_variables: {},
  current_version_number: "1",
};

const ONE_INSTANCE = {
  id: "e2e-instance-1",
  organization_id: "e2e-org",
  project_id: null,
  definition_id: "e2e-workflow-1",
  version_id: "v1",
  parent_instance_id: null,
  sdk_execution_id: null,
  status: "waiting",
  trigger_type: "manual",
  triggered_by: "e2e-user",
  started_at: "2026-01-01T00:00:00Z",
  finished_at: null,
  error_message: null,
};

test("Workflows is reachable from the sidebar and lists real workflows", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await stubJson(context, `${API}/workflows?*`, [ONE_WORKFLOW]);

  await page.goto("/");
  await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Workflows" }).click();

  await expect(page).toHaveURL(/\/workflows$/);
  await expect(page.getByRole("heading", { name: "Workflows", level: 1 })).toBeVisible();
  await expect(page.getByText("Onboard server")).toBeVisible();
});

test("workflow instance detail shows real steps, logs, and an approval gate awaiting a decision", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await stubJson(context, `${API}/workflow-instances/e2e-instance-1`, ONE_INSTANCE);
  await stubJson(context, `${API}/workflows/e2e-workflow-1`, ONE_WORKFLOW);
  await stubJson(context, `${API}/workflow-instances/e2e-instance-1/steps`, [
    {
      id: "s1",
      instance_id: "e2e-instance-1",
      node_id: "provision-vm",
      node_type: "task",
      status: "completed",
      started_at: "2026-01-01T00:00:00Z",
      finished_at: "2026-01-01T00:00:05Z",
      output: {},
      error: null,
      attempts: 1,
    },
  ]);
  await stubJson(context, `${API}/workflow-instances/e2e-instance-1/logs`, [
    { id: "l1", instance_id: "e2e-instance-1", node_id: "provision-vm", level: "info", message: "VM provisioned.", logged_at: "2026-01-01T00:00:05Z" },
  ]);
  await stubJson(context, `${API}/workflow-instances/e2e-instance-1/approvals`, [
    {
      id: "a1",
      instance_id: "e2e-instance-1",
      node_id: "manual-review",
      node_type: "approval",
      approvers: ["ops-lead"],
      required_approvals: 1,
      decision: "pending",
      decisions_by_approver: {},
      comments: null,
      escalated_to: null,
      timeout_seconds: 3600,
      decided_at: null,
    },
  ]);

  await page.goto("/workflows/instances/e2e-instance-1");

  await expect(page.getByText("provision-vm").first()).toBeVisible();
  await expect(page.getByText("VM provisioned.")).toBeVisible();
  await expect(page.getByText("manual-review")).toBeVisible();
  await expect(page.getByText("ops-lead")).toBeVisible();
});
