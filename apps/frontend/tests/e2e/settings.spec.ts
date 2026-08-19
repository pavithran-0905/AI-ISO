import { expect, test } from "@playwright/test";

import { seedAuthenticatedSession } from "./support/seed-session";

const API = "http://localhost:8027";

function envelope(data: unknown) {
  return JSON.stringify({ success: true, message: "ok", data, meta: {} });
}

async function stubJson(context: Parameters<typeof seedAuthenticatedSession>[0], pattern: string, body: unknown) {
  await context.route(pattern, (route) => route.fulfill({ status: 200, contentType: "application/json", body: envelope(body) }));
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

const PREFERENCES = {
  user_id: "e2e-user",
  language: "en",
  theme: "system",
  timezone: "UTC",
  date_format: "YYYY-MM-DD",
  time_format: "24h",
  dashboard_preferences: {},
  notification_preferences: {},
  accessibility: {},
  default_organization_id: null,
  default_project_id: null,
};

const PROFILE = {
  user_id: "e2e-user",
  biography: null,
  job_title: null,
  department: null,
  employee_id: null,
  manager_id: null,
  custom_fields: {},
  profile_photo: null,
};

test("Preferences is reachable from the account menu and shows real, saveable form values", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await stubJson(context, `${API}/users/preferences`, PREFERENCES);
  await stubJson(context, `${API}/users/profile`, PROFILE);

  await page.goto("/");
  await page.getByRole("button", { name: /account menu/i }).click();
  await page.getByRole("menuitem", { name: "Preferences" }).click();

  await expect(page).toHaveURL(/\/settings$/);
  await expect(page.getByRole("heading", { name: "My Preferences" })).toBeVisible();
  await expect(page.getByLabel("Language")).toHaveValue("en");
});

test("saving My Preferences waits for the real backend response", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await stubJson(context, `${API}/users/profile`, PROFILE);
  await context.route(`${API}/users/preferences`, (route) => {
    if (route.request().method() === "PUT") {
      return route.fulfill({ status: 200, contentType: "application/json", body: envelope({ ...PREFERENCES, language: "fr" }) });
    }
    return route.fulfill({ status: 200, contentType: "application/json", body: envelope(PREFERENCES) });
  });

  await page.goto("/settings");
  await page.getByLabel("Language").fill("fr");
  await page.getByRole("button", { name: "Save preferences" }).click();

  await expect(page.getByText("Preferences updated")).toBeVisible();
});

test("Security shows real MFA status and lets the user start enrollment", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await stubJson(context, `${API}/auth/apikeys`, []);
  await stubJson(context, `${API}/auth/devices`, []);
  await stubJson(context, `${API}/auth/sessions`, []);
  await context.route(`${API}/auth/mfa/enable`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: envelope({ secret: "JBSWY3DPEHPK3PXP", otpauth_uri: "otpauth://totp/AI-IOS:e2e", recovery_codes: ["aaaa-bbbb", "cccc-dddd"] }),
    }),
  );

  await page.goto("/settings/security");
  await expect(page.getByText("Not enabled")).toBeVisible();

  await page.getByRole("button", { name: "Enable MFA" }).click();

  await expect(page.getByText("aaaa-bbbb")).toBeVisible();
  await expect(page.getByLabel("Verification code")).toBeVisible();
});

test("System is hidden from a non-administrative session but reachable for an organization admin", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await seedAsOperator(context);
  await stubJson(context, `${API}/users/preferences`, PREFERENCES);
  await stubJson(context, `${API}/users/profile`, PROFILE);

  await page.goto("/settings");
  await expect(page.getByRole("link", { name: "System" })).not.toBeVisible();
});

test("an organization admin can reach System and see real, read-only observability data", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await seedAsOrgAdmin(context);
  await stubJson(context, `${API}/admin/dashboard`, {
    tenant_count: 3,
    active_tenant_count: 2,
    organization_count: 1,
    running_job_count: 0,
    failed_job_count: 1,
    open_maintenance_window_count: 0,
    overall_health: "healthy",
  });
  await stubJson(context, `${API}/admin/health`, { overall_status: "healthy", components: [] });
  await stubJson(context, `${API}/admin/settings*`, { settings: [], total: 0 });
  await stubJson(context, `${API}/admin/feature-flags*`, { feature_flags: [], total: 0 });
  await stubJson(context, `${API}/admin/jobs*`, { jobs: [], total: 0 });
  await stubJson(context, `${API}/admin/diagnostics*`, { diagnostics: [], total: 0 });
  await stubJson(context, `${API}/admin/statistics*`, { windows: [], total: 0 });
  await stubJson(context, `${API}/admin/reports*`, { reports: [], total: 0 });

  await page.goto("/settings");
  await page.getByRole("link", { name: "System" }).click();

  await expect(page).toHaveURL(/\/settings\/system$/);
  await expect(page.getByText("Failed jobs")).toBeVisible();
});

test("registering a connector navigates to its detail page, where a real test-connection result is shown", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await stubJson(context, `${API}/integrations/connectors?*`, []);
  await context.route(`${API}/integrations/connectors`, (route) => {
    if (route.request().method() === "POST") {
      return route.fulfill({
        status: 201,
        contentType: "application/json",
        body: envelope({
          id: "conn-1",
          organization_id: "e2e-org",
          name: "Kubernetes prod",
          description: null,
          category: "container_platforms",
          connector_type: "kubernetes",
          status: "registered",
          auth_method: "bearer_token",
          config: {},
          owner_id: null,
          enabled: false,
          consecutive_failures: 0,
          last_validated_at: null,
          last_health_check_at: null,
          last_sync_at: null,
          tags: [],
          created_at: "2026-01-01T00:00:00Z",
        }),
      });
    }
    return route.fallback();
  });
  await stubJson(context, `${API}/integrations/connectors/conn-1`, {
    id: "conn-1",
    organization_id: "e2e-org",
    name: "Kubernetes prod",
    description: null,
    category: "container_platforms",
    connector_type: "kubernetes",
    status: "registered",
    auth_method: "bearer_token",
    config: {},
    owner_id: null,
    enabled: false,
    consecutive_failures: 0,
    last_validated_at: null,
    last_health_check_at: null,
    last_sync_at: null,
    tags: [],
    created_at: "2026-01-01T00:00:00Z",
  });
  await context.route(`${API}/integrations/connectors/conn-1/test`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: envelope({
        id: "test-1",
        connector_id: "conn-1",
        credential_id: null,
        status: "failed",
        tested_at: "2026-01-01T00:00:00Z",
        latency_ms: null,
        error: "Connector has no configuration",
        attempt_number: 1,
      }),
    }),
  );

  await page.goto("/settings/integrations");
  await page.getByRole("button", { name: "Register connector" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Name*").fill("Kubernetes prod");
  await dialog.getByLabel("Connector type*").fill("kubernetes");
  await dialog.getByLabel("Category*").selectOption("container_platforms");
  await dialog.getByRole("button", { name: "Register connector" }).click();

  await expect(page).toHaveURL(/\/settings\/integrations\/conn-1$/);
  await page.getByRole("button", { name: "Test connection" }).click();

  await expect(page.getByRole("main").getByText("Connector has no configuration")).toBeVisible();
});
