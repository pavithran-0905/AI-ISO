import type { BrowserContext } from "@playwright/test";

/**
 * Seeds a signed-in session directly into `localStorage` before any page
 * script runs, so specs that exercise shell UI (not the login flow
 * itself — see `auth.spec.ts`) don't depend on a live backend's
 * `POST /auth/login` for an area they're not testing. The token's
 * signature is fake — `auth/jwt.ts` never verifies it client-side, only
 * the backend does (`docs/frontend/architecture/authentication.md`).
 *
 * Also stubs `GET /auth/profile` at the context level: on a machine
 * where a real `authentication-service`/gateway happens to be running
 * (true on this one — confirmed by direct request during development),
 * the real backend correctly rejects the fake token's signature with a
 * 401, which triggers the very real `AuthGuard` session-expiry flow
 * (Prompt 004 §8) mid-test and races whatever the test was actually
 * checking. Stubbing this one endpoint keeps these UI-only specs
 * deterministic regardless of what happens to be reachable locally,
 * without touching the backend itself.
 */
export async function seedAuthenticatedSession(context: BrowserContext): Promise<void> {
  const payload = { sub: "e2e-user", iss: "ai-ios", iat: 0, exp: 9999999999, jti: "e2e-token" };
  const accessToken = `header.${Buffer.from(JSON.stringify(payload)).toString("base64url")}.sig`;

  await context.addInitScript(
    ([token]) => {
      localStorage.setItem(
        "aiios-auth",
        JSON.stringify({
          state: {
            accessToken: token,
            refreshToken: "e2e-refresh-token",
            userId: "e2e-user",
            role: null,
            organizationId: null,
          },
          version: 0,
        }),
      );
    },
    [accessToken],
  );

  await context.route("**/auth/profile", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        message: "ok",
        data: {
          id: "e2e-user",
          email: "e2e@example.com",
          display_name: "E2E User",
          is_email_verified: true,
          mfa_enabled: false,
          last_login_at: null,
          created_at: "2026-01-01T00:00:00Z",
        },
        meta: {},
      }),
    }),
  );

  await context.route("**/auth/logout", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, message: "ok", data: { success: true }, meta: {} }) }),
  );

  // Same reasoning as `/auth/profile` above, extended to the dashboard's
  // own organization-scoped calls (Prompt 005): a real backend would
  // reject the fake token for every one of these too. Fulfilling them
  // gives dashboard specs one deterministic organization with real-shaped
  // (if empty) data, regardless of what's reachable locally.
  const envelope = (data: unknown) => JSON.stringify({ success: true, message: "ok", data, meta: {} });

  await context.route("**/organizations/e2e-org/analytics", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: envelope({
        organization_id: "e2e-org",
        user_count: 3,
        project_count: 2,
        asset_count: 14,
        workflow_count: 1,
        automation_count: 5,
        validation_count: 0,
        computed_at: "2026-01-01T00:00:00Z",
      }),
    }),
  );
  await context.route("**/organizations", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: envelope([
        { id: "e2e-org", name: "e2e-org", display_name: "E2E Org", short_name: null, slug: "e2e-org", status: "active" },
      ]),
    }),
  );
  await context.route("**/gateway/health*", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: envelope({ overall_status: "healthy", instances: [] }) }),
  );
  // Scoped to the real API origin (`config/env.ts`'s default,
  // `.env`'s `NEXT_PUBLIC_API_BASE_URL`) — a bare `**/alerts*` glob
  // would also match the frontend's OWN page navigations to
  // `/alerting/alerts` and `/alerting/alerts/[id]` (Prompt 007;
  // Playwright routes intercept document navigations too, not just
  // XHR/fetch), silently replacing the whole page with this stub's raw
  // JSON instead of the app shell.
  await context.route("http://localhost:8027/alerts*", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: envelope([]) }),
  );
  // Scoped to the real API origin for the same reason as `/alerts*`
  // above — Automation (Prompt 009) now has a real frontend page at
  // this exact path (`/automation/executions`), which a bare glob
  // would also intercept.
  await context.route("http://localhost:8027/automation/executions*", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: envelope([]) }),
  );
  // The notification bell (`components/navigation/notification-area.tsx`,
  // Prompt 016) renders in the shell header on every authenticated
  // page, so every spec — not just `notifications.spec.ts` — triggers
  // this call. Scoped to the real API origin for the same reason as
  // `/alerts*`/`/automation/executions*` above: `/notifications` is
  // also a real frontend page path a bare glob would intercept.
  // Without this, an unstubbed request on every page load was slowing
  // unrelated specs under parallel workers — a real, confirmed
  // regression, not a coincidence.
  await context.route("http://localhost:8027/notifications?*", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: envelope([]) }),
  );
  // The gateway's own unauthenticated liveness check (`GatewayLivenessCard`)
  // — stubbed too, since the real endpoint's `service` field is the real
  // deployment's own name ("ai-ios"), not the fixed "gateway" these specs
  // assert on.
  await context.route("**/health", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: envelope({ status: "healthy", service: "gateway", version: "0.1.0", environment: "development" }),
    }),
  );

  // Monitoring (Prompt 006) — same reasoning, extended to inventory-service
  // and observability-platform-service's real endpoints.
  await context.route("**/inventory/statistics*", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: envelope({ total_assets: 0, health_distribution: {} }) }),
  );
  await context.route("**/inventory/search*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: envelope({ items: [], pagination: { total: 0, page: 1, page_size: 25, total_pages: 0, has_next: false, has_previous: false } }),
    }),
  );
  await context.route("**/inventory/assets/*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: envelope({
        id: "e2e-asset",
        organization_id: "e2e-org",
        project_id: null,
        name: "e2e-server",
        display_name: "E2E Server",
        hostname: "e2e-server.internal",
        fqdn: null,
        ip_address: null,
        vendor: null,
        manufacturer: null,
        model: null,
        operating_system: null,
        environment: "production",
        asset_type: "physical_server",
        category_id: null,
        class_id: null,
        location_id: null,
        owner_id: null,
        status: "managed",
        health: "healthy",
        lifecycle_state: "operational",
        criticality: "medium",
        metadata: {},
        tags: [],
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      }),
    }),
  );
  await context.route("**/inventory/relationships*", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: envelope([]) }),
  );
  await context.route("**/observability/topology*", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: envelope({ environment: "production", nodes: [] }) }),
  );
  await context.route("**/observability/events*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: envelope({ events: [], page: { next_cursor: null, has_more: false } }),
    }),
  );
}
