import { expect, test } from "@playwright/test";

import { seedAuthenticatedSession } from "./support/seed-session";

const API = "http://localhost:8027";

function envelope(data: unknown) {
  return JSON.stringify({ success: true, message: "ok", data, meta: {} });
}

async function stubJson(context: Parameters<typeof seedAuthenticatedSession>[0], pattern: string, body: unknown) {
  await context.route(pattern, (route) => route.fulfill({ status: 200, contentType: "application/json", body: envelope(body) }));
}

function notificationBody(overrides: Record<string, unknown> = {}) {
  return {
    id: "n1",
    organization_id: "e2e-org",
    user_id: "e2e-user",
    category: "alert",
    priority: "critical",
    status: "sent",
    subject: "Disk usage above threshold",
    body: "Disk usage on edge-01 exceeded 90%.",
    template_id: null,
    source_service: "monitoring-service",
    source_event_type: null,
    correlation_id: null,
    expires_at: null,
    read_at: null,
    acknowledged_at: null,
    tags: [],
    notification_metadata: {},
    created_at: "2026-08-01T10:00:00Z",
    updated_at: "2026-08-01T10:00:00Z",
    ...overrides,
  };
}

test("the notification bell shows an unread indicator and lists real notifications", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await stubJson(context, `${API}/notifications?*`, [notificationBody()]);

  await page.goto("/");
  await expect(page.getByRole("button", { name: "Notifications, unread items" })).toBeVisible();

  await page.getByRole("button", { name: "Notifications, unread items" }).click();
  await expect(page.getByText("Disk usage above threshold")).toBeVisible();
});

test("View all from the bell opens the Notification Center, where the notification can be opened and marked read", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  let markedRead = false;

  await stubJson(context, `${API}/notifications?*`, [notificationBody()]);
  await context.route(`${API}/notifications/n1?*`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: envelope(notificationBody(markedRead ? { read_at: "2026-08-01T10:05:00Z", status: "read" } : {})) }),
  );
  await stubJson(context, `${API}/notifications/n1/deliveries?*`, []);
  await context.route(`${API}/notifications/n1/read*`, (route) => {
    markedRead = true;
    return route.fulfill({ status: 200, contentType: "application/json", body: envelope(notificationBody({ read_at: "2026-08-01T10:05:00Z", status: "read" })) });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Notifications, unread items" }).click();
  await page.getByRole("link", { name: "View all" }).click();

  await expect(page).toHaveURL(/\/notifications$/);
  await expect(page.getByText(/checks no identity for reading or changing notifications/)).toBeVisible();

  await page.getByRole("link", { name: "Disk usage above threshold" }).first().click();
  await expect(page).toHaveURL(/\/notifications\/n1$/);
  await page.getByRole("button", { name: "Mark read" }).click();

  await expect(page.getByRole("button", { name: "Mark read" })).not.toBeVisible();
});

test("Notification Center filters by category and switches to the Unread quick view", async ({ page, context }) => {
  await seedAuthenticatedSession(context);
  await stubJson(context, `${API}/notifications?*`, [
    notificationBody({ id: "n1", subject: "Unread alert" }),
    notificationBody({ id: "n2", subject: "Already read", read_at: "2026-08-01T09:00:00Z", status: "read" }),
  ]);

  await page.goto("/notifications");
  await expect(page.getByText("Unread alert").first()).toBeVisible();
  await expect(page.getByText("Already read").first()).toBeVisible();

  await page.getByRole("tab", { name: "Unread" }).click();
  await expect(page.getByText("Unread alert").first()).toBeVisible();
  await expect(page.getByText("Already read")).toHaveCount(0);

  await page.getByRole("link", { name: "Preferences" }).click();
  await expect(page).toHaveURL(/\/settings\/notifications$/);
});
