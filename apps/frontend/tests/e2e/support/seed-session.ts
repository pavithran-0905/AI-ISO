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
}
