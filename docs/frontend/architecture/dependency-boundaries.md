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

## modules/dashboard/ and the rest of the app

`modules/dashboard/` is pre-existing (see `docs/frontend/README.md`)
and was left untouched rather than migrated to `features/dashboard/`.
It follows the boundary rules already (its own `components/`, `hooks/`,
`services/`, `types/`) and only reaches into shared code the same way a
`features/<feature>/` module would (`@/components/data-display/card`,
`@/api/client`, indirectly through `services/health-service.ts`). It is
not a second, competing convention — it is one deliberately-preserved
instance of an earlier one.
