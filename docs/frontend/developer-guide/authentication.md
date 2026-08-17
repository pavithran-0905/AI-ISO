# Authentication

The login flow, session lifecycle, and logout built in Prompt 004, on
top of Prompt 001's `auth/` foundation. See
`docs/frontend/architecture/authentication.md` for the real backend
contract this was built against (confirmed by source inspection) and
the documented `role`/`organization_id` JWT-claims gap.

## Login architecture

```
app/(auth)/login/page.tsx        Server component: reads/validates
                                  ?from=/?reason=, wraps GuestGuard
  app/(auth)/login/login-form.tsx  LoginForm (client) — the actual form
    auth/use-login.ts              useLogin() — the mutation hook
      auth/api.ts                  authApi.login()
        api/client.ts               apiClient (the only fetch() caller)
```

Matches §23's required flow exactly:
`LoginForm → useLogin → auth API function → shared API client → backend`.
No component calls `fetch()` directly.

`app/(auth)/layout.tsx` wraps the route group in `AuthLayout`
(chrome-free, centered — Prompt 001 §16), separate from
`app/(app)/layout.tsx`'s `MainLayout` + `AuthGuard`.

### Validation

`login-form.tsx` defines a Zod schema (required fields, email format)
and calls `schema.safeParse` inside `onSubmit`, wiring failures to
React Hook Form's `setError` — deliberately *without*
`@hookform/resolvers` (not a repository dependency; two trivial rules
don't justify adding one — §33). When a field fails multiple checks
(e.g. an empty email fails both "required" and "valid format"), only
the first issue per field is applied, so the more useful message
("Email is required") isn't overwritten by a less useful one ("Enter a
valid email address").

### Error presentation

`auth/login-error.ts`'s `getLoginErrorMessage(error)` maps every
failure shape (`ApiRequestError` by status, `ApiNetworkError`,
`ApiTimeoutError`, anything else) to one of a small set of safe,
generic messages — §7: 400 and 401 deliberately produce the *identical*
message ("Unable to sign in with those credentials.") so a failed
login never reveals whether the email exists. No backend message,
stack trace, or internal code ever reaches the UI.

### MFA

`POST /auth/login` can return an `MfaChallenge` instead of tokens
(`auth/types.ts`, confirmed by source inspection). `login-form.tsx`
checks `isMfaChallenge(result)` and shows a message explaining this
interface doesn't support entering a code yet, rather than silently
failing or inventing an MFA UI — see Backend V1 limitations below.

## AuthGuard

`auth/guards.tsx`. Wired into `app/(app)/layout.tsx` this prompt
(§10) — every route in that group is now gated:

```tsx
export default function AppRouteGroupLayout({ children }) {
  return (
    <AuthGuard>
      <MainLayout>{children}</MainLayout>
    </AuthGuard>
  );
}
```

`AuthGuard` renders nothing while `status !== "authenticated"` and
redirects (via a `useEffect`, not during render) to:

```
/login?from=<pathname>&reason=expired
```

- `from` is set whenever the pathname isn't `/` — the "return-to
  destination," read by the login page and passed through
  `GuestGuard`'s `redirectTo` and `LoginForm`'s post-login `router.push`.
- `reason=expired` is set only when `useAuthStore`'s `lastClearReason`
  is `"expired"` — i.e. the *last* `clear()` call was triggered by a
  real 401 from the API client (see Session expiration below), never
  guessed at for a visitor who was simply never signed in.

This remains a UX convenience only, not a security boundary — every
protected backend call still independently verifies its own bearer
token (`docs/frontend/architecture/authorization.md`).

## Session state

`auth/store.ts`'s `useAuthStore` — unchanged shape from Prompt 001,
plus one new field:

- `lastClearReason: "expired" | "manual" | null` — set by `clear()`,
  excluded from `persist`'s `partialize` (transient, only meaningful
  for the redirect happening in the current page load). `setTokens()`
  resets it to `null` on a fresh sign-in.

`useSession()` (`auth/session.tsx`) is unchanged — still the one hook
components should read `isAuthenticated`/`role`/`user` from.

## Session expiration

`auth/session.tsx`'s `AuthBootstrap` wires `api/client.ts`'s
`unauthorizedHandler` to `() => clear("expired")` instead of a bare
`clear` — so a real 401 from any protected API call (an expired or
invalid token) is distinguishable from an explicit sign-out. `AuthGuard`
reads this to add `reason=expired`, and the login page shows "Your
session has expired" only in that case.

No polling or proactive expiry-checking exists — expiration is
detected reactively, the first time a protected API call returns 401.

## Return URL handling (redirect safety)

`auth/return-path.ts`'s `isSafeReturnPath(path)` — a plain (non-"use
client") module, deliberately kept out of `auth/guards.tsx`: every
export of a `"use client"` file becomes a client reference in Next.js,
which can't be invoked as a plain function from a server component
(`app/(auth)/login/page.tsx` needs to call it directly while reading
`searchParams`). Rejects anything that isn't a same-app absolute path
(`/...`) — a protocol-relative (`//evil.example`) or absolute URL
`from` value falls back to `/` instead of ever being used as a redirect
target (§9).

## Logout

`auth/use-logout.ts`'s `useLogout()`, wired into `UserMenu`'s "Sign
out" item (replacing Prompt 003's bare `clearSession()` call):

1. `authApi.logout(refreshToken)` — best-effort; a network failure here
   is caught and ignored, since staying "signed in" locally because the
   backend was unreachable is worse than a token that simply expires on
   its own.
2. `clear("manual")` — clears `useAuthStore` (and, since it's not
   persisted separately, `lastClearReason` is set to `"manual"`, not
   `"expired"`).
3. `queryClient.clear()` — see Cache clearing below.
4. `router.push("/login")`.

Clearing the store *before* navigating (rather than relying on the
route change alone) is what stops a stale-state return to a protected
page via the back button — combined with `AuthGuard` re-checking
`status` on every render, not just on mount.

## Cache clearing

Both `useLogin` (on a successful token result) and `useLogout` call
`queryClient.clear()` — the entire TanStack Query cache, not a
targeted invalidation. There's exactly one cached query in the app
today (`useSession`'s profile fetch), so a blanket clear is simplest
and correct; revisit if a second cached query type is ever added and a
full clear becomes too broad.

## Security rules followed

- No token, password, or credential is ever logged or rendered to the
  DOM outside the password `<input>` itself.
- `login-error.ts` never surfaces a backend response body verbatim.
- The access/refresh tokens live in `localStorage` (Prompt 001's
  existing, documented trade-off — no `httpOnly` cookie exists to use
  instead) — unchanged by this prompt.
- `robots: { index: false, follow: false }` on the login page's
  metadata.

## Testing

- `tests/unit/auth/login-error.test.ts` — every status/error-type
  mapping, including that 400/401 are identical.
- `tests/unit/auth/use-login.test.tsx` / `use-logout.test.tsx` — the
  mutation/hook layer against a mocked `fetch`.
- `tests/unit/app/(auth)/login/login-form.test.tsx` — validation,
  success, every error path, loading/duplicate-submission prevention,
  password visibility, label accessibility.
- `tests/unit/auth/guards.test.tsx` — `AuthGuard`'s `/login` redirect,
  `?from=`/`&reason=expired`, `GuestGuard`'s `redirectTo`,
  `isSafeReturnPath`.
- `tests/unit/app/(app)/layout.test.tsx` — the guard is actually wired
  into the route group (not just unit-testable in isolation).
- `tests/e2e/auth.spec.ts` — login page loads, protected-route
  redirect, invalid-login and network-failure error presentation
  (both via `page.route` mocking — no live backend required), and a
  full logout round-trip. See its own header comment for why a
  successful-login E2E isn't implemented (§28: no approved test
  credentials exist in this repository).
- `tests/e2e/support/seed-session.ts` — a shared helper for specs that
  need to start "already signed in" without exercising the login flow
  itself (`dashboard.spec.ts`, the logout spec). Also stubs
  `GET /auth/profile`: on a machine where a real backend happens to be
  reachable, it correctly rejects the helper's fake-signature token
  with a real 401, which triggers the very session-expiry flow this
  prompt built — stubbing keeps these UI-only specs deterministic
  regardless of local backend availability.
