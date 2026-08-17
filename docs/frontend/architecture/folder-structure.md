# Folder Structure

All paths are relative to `apps/frontend/`.

```
app/                    Next.js App Router routes only — no business logic.
  (app)/                Route group: pages wrapped in MainLayout. Currently just page.tsx (the dashboard).
  layout.tsx             Root layout: <html>/<body> + AppProviders. No visible chrome — see routing.md.
  error.tsx               Segment error boundary (ErrorState).
  global-error.tsx         Root-layout error boundary (must render its own <html>/<body>).
  not-found.tsx            404.
  unauthorized/page.tsx     401 destination.
  forbidden/page.tsx        403 destination.
  globals.css               Design tokens (see the design-system doc referenced in the app README).

api/
  client.ts               The shared API client — the only fetch() call site in the app.

auth/
  types.ts, jwt.ts, api.ts, store.ts, session.tsx, guards.tsx, index.ts
                           See authentication.md.

permissions/
  types.ts, capabilities.ts, hooks.ts, guards.tsx, index.ts
                           See authorization.md.

components/
  ui/                     Generic primitives with no business logic (Button, ThemeToggle).
  data-display/           Card and future data-display primitives (Table, Chart wrappers).
  feedback/                Loading/Skeleton/Empty/Error/AccessDenied/Offline/PartialData + StatusBadge.
  forms/                   Empty — first form-heavy feature populates it (see its README).
  navigation/               Empty — populated when primary navigation is built.
  overlays/                 Empty — populated when the first Modal/Drawer/Popover is needed.

layouts/
  main-layout.tsx, main/header.tsx, main/footer.tsx
  auth-layout.tsx, fullscreen-layout.tsx, split-pane-layout.tsx,
  wizard-layout.tsx, settings-layout.tsx
                           The six layouts Prompt 001 §16 requires.

lib/
  route-registry.ts        Centralized route metadata (title/breadcrumb/roles/nav visibility).

features/                 Empty — the pattern for every future business module. See its own README.

modules/dashboard/        Pre-existing, untouched — see docs/frontend/README.md.

state/
  theme-store.ts            The one genuine client-state store today (persisted theme preference).

providers/
  app-providers.tsx, query-provider.tsx, theme-provider.tsx

config/
  env.ts                   The one place `process.env` is read.

utils/
  cn.ts                    Class-name joining (no clsx dependency — see technology-stack rationale below).

tests/
  unit/                    Mirrors the source tree above.
  e2e/                      Playwright specs.
  setup.ts, query-test-utils.tsx
```

## Rules

- No `src/modules/` **and** `src/features/` both holding live feature
  code — `modules/dashboard/` is the one deliberate, documented
  exception (pre-existing, untouched), not a second active convention.
- Generic components (`components/`) never import from `features/`,
  `modules/`, `auth/`, or `permissions/` for anything business-specific.
- `lib/` stays small — a thing that isn't a pure function (`utils/`) and
  isn't feature-specific (`features/<feature>/utils/`). If it grows
  feature-specific branches, it belongs in a feature module instead.
