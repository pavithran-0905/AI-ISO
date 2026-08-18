# Dependency Boundaries

## The enforced direction

```
app/**/page.tsx  →  features/<feature>  →  components/  →  api/ + auth/ + permissions/ + state/ + lib/ + utils/
```

Never the reverse. `components/` (generic, reusable) never imports from
`features/` or `modules/` (business-specific). `api/client.ts` never
imports from `auth/` directly — see below.

## The one deliberate circular-import avoidance

`api/client.ts` needs the current bearer token and needs to react to a
401 by clearing the session. `auth/api.ts` needs `api/client.ts` to make
the actual HTTP calls (`POST /auth/login`, etc.). A direct import in
either direction would be circular.

Resolved via dependency injection, not a shared "core" module:
`api/client.ts` exports `setAuthTokenProvider(fn)` and
`setUnauthorizedHandler(fn)`; `auth/session.tsx`'s `AuthBootstrap`
component calls both once, on mount, wiring the real auth store in
without `api/client.ts` ever importing `@/auth/*`. See
`tests/unit/auth/session.test.tsx` for the integration test that
verifies the wiring actually works end-to-end (token attached to a real
request, 401 clears the session) — this specific pattern is exactly the
kind of thing that looks correct per-file but silently breaks at the
seam, which is why it's tested as a seam, not just as two units.

## features/dashboard/ and the rest of the app

`features/dashboard/` (Frontend Prompt 005) is the first real occupant
of the `features/<feature>/` pattern — the earlier `modules/dashboard/`
placeholder it replaced (see `docs/frontend/README.md`) was migrated
in, not left as a second, competing convention. It follows the
boundary rules exactly like every future `features/<feature>/` module
will: its own `api/`, `components/`, `hooks/`, `types/`, reaching into
shared code only through `@/components/data-display/card`,
`@/api/client`, and the new foundation-level `organization/` module
(sibling to `auth/`/`permissions/`, not itself a feature — see
`docs/frontend/developer-guide/dashboard.md` for why it exists).
