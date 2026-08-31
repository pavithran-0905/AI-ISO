import { expect, test } from "@playwright/test";

import { seedAuthenticatedSession } from "./support/seed-session";

const API = "http://localhost:8027";

function envelope(data: unknown) {
  return JSON.stringify({ success: true, message: "ok", data, meta: {} });
}

async function stubJson(context: Parameters<typeof seedAuthenticatedSession>[0], pattern: string, body: unknown) {
  await context.route(pattern, (route) => route.fulfill({ status: 200, contentType: "application/json", body: envelope(body) }));
}

async function seedAsOrgAdmin(context: Parameters<typeof seedAuthenticatedSession>[0]): Promise<void> {
  await context.addInitScript(() => {
    const raw = localStorage.getItem("aiios-auth");
    if (!raw) return;
    const parsed = JSON.parse(raw);
    parsed.state.role = "organization_admin";
    parsed.state.organizationId = "e2e-org";
    localStorage.setItem("aiios-auth", JSON.stringify(parsed));
  });
}

const COMPLIANCE_EVENT = {
  id: "evt-1",
  action: "finding_raised",
  entity_type: "finding",
  entity_id: "f-1",
  entity_reference: "Unencrypted volume detected",
  actor_id: "auditor-42",
  actor_type: "user",
  occurred_at: "2026-08-01T10:00:00Z",
  summary: "A finding was raised during a scheduled scan.",
  succeeded: true,
  changes: { field: "status", previous_value: "draft", new_value: "open" },
};

test("Audit is hidden from the sidebar for a non-administrative session", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await context.addInitScript(() => {
    const raw = localStorage.getItem("aiios-auth");
    if (!raw) return;
    const parsed = JSON.parse(raw);
    parsed.state.role = "operator";
    parsed.state.organizationId = "e2e-org";
    localStorage.setItem("aiios-auth", JSON.stringify(parsed));
  });

  await page.goto("/");
  await expect(page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Audit & Activity" })).not.toBeVisible();
});

test("an administrator opens Audit, sees the real compliance summary, and finds no platform-wide-log warning", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await seedAsOrgAdmin(context);
  await stubJson(context, `${API}/compliance/audit/summary*`, { since: "2026-07-01T00:00:00Z", total: 12, by_action: { finding_raised: 8, control_updated: 4 } });
  await stubJson(context, `${API}/compliance/findings/summary*`, { open_total: 3, by_severity: { high: 2, medium: 1 }, critical_open: 0, overdue: 1, open_statuses: ["open"] });

  await page.goto("/");
  await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Audit & Activity" }).click();

  await expect(page).toHaveURL(/\/audit$/);
  await expect(page.getByText("No platform-wide audit log exists")).toBeVisible();
  await expect(page.getByText("12", { exact: true })).toBeVisible();
  await expect(page.getByText("3", { exact: true })).toBeVisible();
});

test("Activity searches/filters the real compliance audit trail and opens an event's detail drawer", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await seedAsOrgAdmin(context);
  await stubJson(context, `${API}/compliance/audit?*`, [COMPLIANCE_EVENT]);

  await page.goto("/audit/activity");
  await expect(page.getByText("Unencrypted volume detected").first()).toBeVisible();
  await expect(page.getByText(/only requires a valid session token/)).toBeVisible();

  await page.getByLabel("Actor ID").fill("auditor-42");
  await expect(page).toHaveURL(/actorId=auditor-42/, { timeout: 2000 });

  await page.getByRole("button", { name: "View" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText("auditor-42")).toBeVisible();
  await expect(dialog.getByText("Finding Raised").first()).toBeVisible();
  await expect(dialog.getByText(/"previous_value": "draft"/)).toBeVisible();
});

test("Activity switches Table/Timeline over the same data, and switching source resets filters", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await seedAsOrgAdmin(context);
  await stubJson(context, `${API}/compliance/audit?*`, [COMPLIANCE_EVENT]);
  await stubJson(context, `${API}/notifications/audit?*`, [
    { id: "evt-2", action: "broadcast_initiated", entity_type: "broadcast", entity_id: "b-1", entity_reference: "Maintenance notice", actor_id: "user-2", actor_type: "user", occurred_at: "2026-08-01T09:00:00Z", summary: "Broadcast initiated.", succeeded: false, changes: {}, context: {} },
  ]);

  await page.goto("/audit/activity");
  await expect(page.getByText("Unencrypted volume detected").first()).toBeVisible();

  await page.getByRole("radio", { name: "Timeline" }).click();
  await expect(page.getByRole("tabpanel", { name: "Compliance" }).getByRole("list")).toBeVisible();

  await page.getByRole("tab", { name: "Notifications" }).click();
  await expect(page.getByText("Maintenance notice").first()).toBeVisible();
  await expect(page.getByText(/requires no authentication at all/)).toBeVisible();
  await expect(page.getByLabel("Export format")).not.toBeVisible();
});

test("exports the real compliance audit report and downloads the generated file", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await seedAsOrgAdmin(context);
  await stubJson(context, `${API}/compliance/audit?*`, [COMPLIANCE_EVENT]);
  await context.route(`${API}/compliance/reports*`, (route) => {
    if (route.request().method() === "POST") {
      return route.fulfill({ status: 201, contentType: "application/json", body: envelope({ id: "report-1", status: "completed", error: null }) });
    }
    return route.fallback();
  });
  await context.route(`${API}/compliance/reports/report-1/download*`, (route) =>
    route.fulfill({ status: 200, contentType: "text/csv", headers: { "Content-Disposition": 'attachment; filename="audit-report.csv"' }, body: "occurred_at,action\n2026-08-01T10:00:00Z,finding_raised\n" }),
  );

  await page.goto("/audit/activity");
  await expect(page.getByText("Unencrypted volume detected").first()).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: /Export last 90 days/ }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("audit-report.csv");
});
