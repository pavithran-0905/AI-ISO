# Routing

Next.js App Router's routes are file-system-defined
(`app/**/page.tsx`) — see `frontend-architecture.md` for why this
project uses it instead of React Router. This document covers the
architecture built *around* that routing: layout composition, route
metadata, and the 404/401/403/error destinations.

## Route groups and layout composition

```
app/layout.tsx            <html>/<body> + AppProviders only — no visible chrome.
app/(app)/layout.tsx        MainLayout (header/content/footer) for every route in the group.
app/(app)/page.tsx           The dashboard (modules/dashboard/DashboardPage).
```

The root layout deliberately does **not** render `MainLayout`: a route
group needing a different shell (a future `(auth)` group with
`AuthLayout`, once a login page exists) must not inherit navigation
chrome it shouldn't show. Route groups (`(app)`, and eventually
`(auth)`) don't add a URL segment — `/` still resolves to the
dashboard.

## Centralized route metadata

`lib/route-registry.ts` is the single source of truth for what a route
is *about* — title, breadcrumb, required roles, owning feature, nav
visibility — independent of Next's own file-system routing. A future
primary-navigation component and breadcrumb trail both read from here,
so they can never disagree about a route's name or who can see it. Only
routes that actually exist are registered (`/` today) — a future
feature's route is added here when its `page.tsx` ships, not before.

## The reusable destinations

- `app/not-found.tsx` — Next's own convention, the 404 primitive.
- `app/error.tsx` — segment-level error boundary (`ErrorState`).
  `app/global-error.tsx` — the boundary for when the root layout itself
  throws (must render its own `<html>`/`<body>`, unlike `error.tsx`).
- `app/unauthorized/page.tsx` (401) / `app/forbidden/page.tsx` (403) —
  both render `AccessDeniedState`, parameterized by variant rather than
  duplicated.

## Guards: not yet wired, by design

`auth/guards.tsx`'s `AuthGuard`/`GuestGuard` and `permissions/guards.tsx`'s
`RequireRole`/`RequirePermission` are real, tested components. None are
currently applied to a route — see `authentication.md` for exactly why
(no login page exists yet, so gating the one working page would break
it). `app/(app)/layout.tsx` documents where `<AuthGuard>` goes once a
login flow ships.
