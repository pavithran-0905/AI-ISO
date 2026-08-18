# Frontend

The AI-IOS web client. Foundation phase (Frontend Prompt 001,
`docs/frontend/001-enterprise-frontend-architecture.txt`) — API/auth/
permissions/routing/layout/design-token/error-state architecture is in
place; the dashboard placeholder from the earlier bootstrap phase
(Prompt 011) is still the only business-facing page. See
[`docs/frontend/README.md`](../../docs/frontend/README.md) for the full
picture, including why this app stayed on Next.js rather than moving to
Prompt 001's literal Vite + React Router baseline.

## Architecture

See [`docs/frontend/architecture/`](../../docs/frontend/architecture/)
for the full set (folder structure, dependency boundaries, API/state/
auth/authorization/routing/error architecture). Summary:

- `app/` — Next.js App Router routes only; no business logic. `(app)/`
  is a route group wrapping every page in `MainLayout`.
- `api/` — `client.ts`, the only place allowed to call `fetch()`.
- `auth/` — session/token architecture, built against the real
  `services/authentication-service` contract (see
  `docs/frontend/architecture/authentication.md` for a documented
  backend gap: `role`/`organization_id` claims aren't populated at
  login today).
- `permissions/` — a deliberately coarse, presentation-only RBAC model
  (no live permission-resolution endpoint exists on the backend today).
- `components/` — reusable, presentation-only UI primitives (`ui`,
  `data-display`, `feedback`, `forms`, `navigation`, `overlays`).
- `layouts/` — the six reusable page shells (main, auth, fullscreen,
  split-pane, wizard, settings).
- `features/` — the pattern every business module follows (see its own
  README) — `dashboard/` is the first real occupant (Prompt 005);
  `modules/dashboard/`, the placeholder it replaced, no longer exists.
- `organization/` — foundation module (sibling to `auth/`, `permissions/`)
  for which organization's data is in view (Prompt 005).
- `lib/` — `route-registry.ts`, centralized route metadata.
- `state/` — Zustand stores (`theme-store.ts` today).
- `providers/` — React context providers composed once in `app/layout.tsx`.
- `config/` — centralized environment access. See the note in
  `config/env.ts` about `NEXT_PUBLIC_*` variables requiring static
  access for Next.js to inline them into the browser bundle, and the
  note below about how the repo-root `.env` actually reaches this app.

## Running Locally

```bash
pnpm install
pnpm dev
```

Requires **`services/api-gateway-service`** running — not
`services/gateway/`, which is a separate, unrelated health-only stub
(confirmed by reading both services' own READMEs; see
`docs/frontend/architecture/authentication.md`). Point
`NEXT_PUBLIC_API_BASE_URL` at it (defaults to `http://localhost:8027`,
see `.env.example` at the repository root).

**How the repo-root `.env` reaches this app**: `apps/frontend` has no
`.env` of its own — `dev`/`build`/`start` (see `package.json`) all run
through `dotenv -e ../../.env --` (the `dotenv-cli` package). This
isn't optional plumbing: Next.js's own env loading only looks in the
directory it's run in, and — confirmed empirically — neither a
`next.config.ts`-level `loadEnvConfig()` call nor the `env` config key
reliably propagates a value into whatever process actually renders a
page in `next dev`/`next build` (both were tried and both failed a
live test: setting `NEXT_PUBLIC_APP_ENV=production` in the root `.env`
had no effect on the `/design-system` gate under either approach, while
the same value set directly as a shell env var worked immediately).
`dotenv-cli` sidesteps this by making the root `.env`'s values *real*
process environment variables before `next` even starts, which is the
one thing every code path — dev server workers, the build compiler,
`next start` — reliably inherits. If `../../.env` doesn't exist (e.g. a
production container with real platform-injected env vars and no
checked-in file), `dotenv-cli` passes through harmlessly rather than
failing.

## Testing

```bash
pnpm typecheck
pnpm lint
pnpm test              # unit tests (Vitest + Testing Library)
pnpm test:coverage
pnpm test:e2e           # Playwright, requires `pnpm exec playwright install`
```

`pnpm test:e2e`'s third spec ("fetches live health data from the
gateway") requires the real `api-gateway-service` running — it's an
intentional integration test, not something to mock away.

## Docker

Build from the **repository root** (this app is a pnpm workspace member
and its lockfile resolves against the whole workspace):

```bash
docker build -f apps/frontend/Dockerfile -t aiios/frontend .
```
