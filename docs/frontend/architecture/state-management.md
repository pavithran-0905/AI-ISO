# State Management

## Server state → TanStack Query, always

Anything that originates from the backend (health status, a future
feature's list/detail data, mutations) goes through `useQuery`/
`useMutation`, never duplicated into a Zustand store. `useSession`
(`auth/session.tsx`) is the one partial exception worth calling out:
token-derived identity fields (`role`, `organizationId`, `userId`) live
in the Zustand auth store (they come from decoding the JWT, not a
query), while the fetched profile (`GET /auth/profile`) is a real
TanStack Query, `enabled` only once authenticated. `useSession()`
returns both through one hook so a consumer never has to know which
half comes from where.

## Client state → Zustand, one store per genuine responsibility

Two stores exist today, each scoped to exactly one thing:

- `state/theme-store.ts` — the persisted light/dark/system preference.
  Unchanged from the pre-existing implementation.
- `auth/store.ts` — the session: tokens, decoded identity fields,
  status. Persisted to `localStorage` (see `authentication.md` for why,
  and the trade-off that entails).

No third, catch-all store exists. A future feature needing genuine
client-only state (sidebar collapse, a wizard's in-progress step, a
command-palette's open state) adds its own store — either in
`state/` if it's app-wide, or `features/<feature>/stores/` if it's
feature-scoped — never appended to an existing store for an unrelated
concern.

## Why the auth store isn't "just" server state

The tokens themselves aren't fetched via a query — they're the *result*
of a mutation (`login`) and then read synchronously by `api/client.ts`
on every subsequent request (see `dependency-boundaries.md`). Treating
them as a TanStack Query cache entry would mean the client's token
provider would need to reach into the query cache directly, coupling
`api/client.ts` to TanStack Query's internals instead of a plain
function. A small, purpose-built store is simpler and matches Prompt
001 §12's own guidance to use Zustand for exactly this kind of
client/application state.
