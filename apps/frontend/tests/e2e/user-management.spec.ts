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

const ONE_USER = {
  id: "e2e-user-1",
  username: "sarun",
  email: "sarun@example.com",
  display_name: "Sarun M",
  avatar: null,
  status: "active",
  created_at: "2026-01-01T00:00:00Z",
};

const USER_DETAIL = {
  ...ONE_USER,
  first_name: "Sarun",
  middle_name: null,
  last_name: null,
  phone_number: null,
  timezone: "UTC",
  language: "en",
  locale: "en-US",
  last_login: null,
  metadata: {},
  updated_at: "2026-01-02T00:00:00Z",
};

test("Users is hidden from the sidebar for a non-administrative session", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await seedAsOperator(context);

  await page.goto("/");
  await expect(page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Users" })).not.toBeVisible();
});

test("an administrator can search users and open a user's detail page", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await seedAsOrgAdmin(context);
  await stubJson(context, `${API}/users?*`, [ONE_USER]);
  await stubJson(context, `${API}/users/e2e-user-1`, USER_DETAIL);

  await page.goto("/");
  await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Users" }).click();

  await expect(page).toHaveURL(/\/administration\/users$/);
  await expect(page.getByRole("link", { name: "Sarun M" })).toBeVisible();

  await page.getByRole("link", { name: "Sarun M" }).click();
  await expect(page).toHaveURL(/\/administration\/users\/e2e-user-1$/);
  await expect(page.getByRole("definition").filter({ hasText: "sarun@example.com" })).toBeVisible();
  await expect(page.getByText(/no endpoint anywhere in ai-ios correlates/i)).toBeVisible();
});

test("changing a user's status calls the real PATCH endpoint and shows the result", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await seedAsOrgAdmin(context);
  await stubJson(context, `${API}/users/e2e-user-1`, USER_DETAIL);
  await context.route(`${API}/users/e2e-user-1`, (route) => {
    if (route.request().method() === "PATCH") {
      return route.fulfill({ status: 200, contentType: "application/json", body: envelope({ ...USER_DETAIL, status: "suspended" }) });
    }
    return route.fulfill({ status: 200, contentType: "application/json", body: envelope(USER_DETAIL) });
  });

  await page.goto("/administration/users/e2e-user-1");
  await page.getByLabel("Change status").selectOption("suspended");
  await page.getByRole("button", { name: "Apply" }).click();

  await expect(page.getByText("Status changed to suspended")).toBeVisible();
});

test("Roles shows the real rbac-service catalog with a prominent no-live-effect warning", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await seedAsOrgAdmin(context);
  await stubJson(context, `${API}/roles`, [
    { id: "role-1", name: "Viewer", code: "viewer", description: "Read-only access.", role_type: "system", status: "active", is_system: true, priority: 10, organization_id: null, project_id: null },
  ]);

  await page.goto("/administration/roles");
  await expect(page.getByText("Reference catalog, not the live enforcement mechanism")).toBeVisible();
  await expect(page.getByText("Viewer (viewer)")).toBeVisible();
});

test("Invitations sends a real invitation with the chosen role, with no pending list shown", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await seedAsOrgAdmin(context);
  await context.route(`${API}/organizations/e2e-org/invite`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: envelope({
        id: "inv-1",
        organization_id: "e2e-org",
        email: "new.hire@example.com",
        invited_by: "e2e-user",
        role: "member",
        department_id: null,
        team_id: null,
        status: "pending",
        resend_count: 0,
        expires_at: "2026-01-08T00:00:00Z",
        created_at: "2026-01-01T00:00:00Z",
      }),
    }),
  );

  await page.goto("/administration/invitations");
  await expect(page.getByRole("alert").getByText("No pending-invitations list exists")).toBeVisible();

  await page.getByLabel("Email*").fill("new.hire@example.com");
  await page.getByRole("button", { name: "Send invitation" }).click();

  await expect(page.getByText("Invitation sent")).toBeVisible();
});

test("Project Members in Settings blocks removing the project's sole Owner", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await seedAsOrgAdmin(context);
  await stubJson(context, `${API}/projects?*`, [
    {
      id: "e2e-project-1",
      organization_id: "e2e-org",
      name: "core-platform",
      display_name: "Core Platform",
      description: null,
      code: null,
      status: "active",
      owner_id: "e2e-user",
      visibility: "private",
      default_language: "en",
      timezone: "UTC",
      category: null,
      priority: "medium",
      archived_at: null,
      metadata: {},
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    },
  ]);
  await stubJson(context, `${API}/projects/e2e-project-1/settings`, {
    default_environment: null,
    default_connector_id: null,
    default_workflow_runtime: null,
    notification_settings: {},
    retention_policies: {},
    execution_policies: {},
    automation_policies: {},
    validation_policies: {},
    monitoring_policies: {},
    ai_settings: {},
    storage_policies: {},
    security_policies: {},
  });
  await stubJson(context, `${API}/projects/e2e-project-1/members`, [
    { id: "m1", project_id: "e2e-project-1", user_id: "sole-owner", role_id: "r1", role_code: "owner", role_name: "Owner", status: "active", invited_by: null, created_at: "2026-01-01T00:00:00Z" },
  ]);

  await page.goto("/settings/projects");
  await page.getByLabel("Project").selectOption("e2e-project-1");
  await page.getByRole("button", { name: "Remove sole-owner" }).click();

  await expect(page.getByText("Can't remove this member")).toBeVisible();
});
