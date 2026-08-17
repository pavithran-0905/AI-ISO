import { expect, test } from "@playwright/test";

import { seedAuthenticatedSession } from "./support/seed-session";

test("login page loads with an accessible form", async ({ page }) => {
  await page.goto("/login");

  await expect(page.getByRole("heading", { name: "Sign in to AI-IOS" })).toBeVisible();
  await expect(page.getByLabel(/^Email/)).toBeVisible();
  await expect(page.getByLabel(/^Password/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign In" })).toBeVisible();
});

test("protected route redirects to /login when unauthenticated", async ({ page }) => {
  await page.goto("/");

  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByRole("heading", { name: "Sign in to AI-IOS" })).toBeVisible();
});

test("invalid login displays a safe error, never the backend's own message", async ({ page }) => {
  // Simulates the real `POST /auth/login` 401 response shape
  // (`docs/frontend/architecture/authentication.md`) without needing a
  // live backend — same reasoning as the network-failure spec below.
  await page.route("**/auth/login", (route) =>
    route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({
        success: false,
        message: "Invalid email or password for user sarun@example.com",
        error: { code: "AIIOS-AUTH-0001", details: [] },
        meta: {},
      }),
    }),
  );
  await page.goto("/login");

  await page.getByLabel(/^Email/).fill("sarun@example.com");
  await page.getByLabel(/^Password/).fill("wrong-password");
  await page.getByRole("button", { name: "Sign In" }).click();

  await expect(page.getByText("Unable to sign in with those credentials.")).toBeVisible();
  await expect(page.getByText("Invalid email or password", { exact: false })).toHaveCount(0);
});

test("an unreachable authentication API shows a safe, non-technical error", async ({ page }) => {
  // Simulates the documented §19 network-failure path without requiring
  // (or being blocked by the absence of) a live backend — the point
  // under test is the frontend's own error presentation, not the real
  // authentication contract, which `docs/frontend/architecture/authentication.md`
  // already confirms by source inspection.
  await page.route("**/auth/login", (route) => route.abort("connectionrefused"));
  await page.goto("/login");

  await page.getByLabel(/^Email/).fill("sarun@example.com");
  await page.getByLabel(/^Password/).fill("hunter2");
  await page.getByRole("button", { name: "Sign In" }).click();

  await expect(
    page.getByText("Unable to connect to the authentication service. Please try again."),
  ).toBeVisible();
});

test("logout clears the session and returns to /login", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();

  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();

  await expect(page).toHaveURL(/\/login/);

  // §11 "prevent returning to protected pages through stale client
  // state": confirm the persisted session was actually cleared, not
  // just that this one redirect happened. A second `page.goto("/")`
  // isn't a valid check for this in isolation — `seedAuthenticatedSession`'s
  // `addInitScript` deliberately re-seeds a fresh session on every new
  // navigation in this context (that's what makes it useful for the
  // other specs), which would re-authenticate this page too and hide a
  // real regression here.
  const stored = await page.evaluate(() => localStorage.getItem("aiios-auth"));
  const persisted = JSON.parse(stored ?? "{}");
  expect(persisted.state?.accessToken).toBeNull();
  expect(persisted.state?.refreshToken).toBeNull();
});

/**
 * Not implemented: a full successful-login E2E (docs/frontend Prompt 004
 * §28's "successful login flow when a valid test environment is
 * available"). That requires a live `services/authentication-service`
 * plus an approved seeded test account — neither exists in this
 * repository's checked-in test setup, and inventing credentials or
 * standing up backend state is explicitly out of scope (§28: "never
 * commit credentials," §32: backend V1 freeze). Documented here as a
 * validation environment limitation, not a gap in frontend coverage —
 * `login-form.test.tsx`'s unit tests cover the same success path against
 * a mocked API response.
 */
