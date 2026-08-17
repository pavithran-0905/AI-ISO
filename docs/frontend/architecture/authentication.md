# Authentication

## The real backend contract (confirmed by source inspection, not assumed)

- **Entry service**: `services/api-gateway-service` (port 8027) — the
  single entry point for every backend service. `services/gateway/` is
  a separate, unrelated stub (health/readiness only) — the frontend
  does not call it. Route forwarding on the gateway is dynamic/DB-registered
  (`app/models/route.py`), so there is no fixed `/api/v1/...`
  path prefix convention to hardcode; `NEXT_PUBLIC_API_BASE_URL`
  (`config/env.ts`) is deliberately just a base URL, nothing more
  opinionated.
- **Auth endpoints** live on `services/authentication-service`:
  - `POST /auth/register` — `{email, password, display_name?}` → `UserSummary`.
  - `POST /auth/login` — `{email, password, remember_me, device_fingerprint?, mfa_code?}`
    → either a `TokenResponse` (`access_token, refresh_token, token_type, expires_in`)
    or an `MfaChallengeResponse` (`mfa_required: true, mfa_challenge_id`).
  - `POST /auth/refresh` — `{refresh_token}` → `TokenResponse`.
  - `POST /auth/logout` — `{refresh_token?}` → `{success: true}`.
  - `GET /auth/profile` — → `ProfileResponse` (`id, email, display_name,
    is_email_verified, mfa_enabled, last_login_at, created_at`).
- **Bearer tokens only. No cookies.** `services/authentication-service`
  never sets `Set-Cookie` anywhere in its auth routes. There is no
  cookie-based session convention anywhere in the gateway either.
- **JWT claims**: `iss: "ai-ios"`, RS256, TTL 900s (access) / 604800s
  (refresh). No `aud` claim.

## The documented backend gap this frontend was built around

`services/authentication-service/app/services/authentication.py`'s
login flow issues the access token via `TokenService.issue(user.id,
session_id=session.id)` — **with no `extra_claims`**. A real access
token today therefore carries only `sub`, `iss`, `iat`, `exp`, `jti`.

`services/api-gateway-service/app/services/auth.py`, on the consuming
side, reads `claims.get("role")` (**singular** — one role, not a list)
and `claims.get("organization_id")` from every incoming token,
expecting them to be there. They are not populated at login time in the
code as it stands, so in the running system today, a freshly-logged-in
user's `role` and `organization_id` are **always absent**.

This frontend does not paper over that gap or assume it will be fixed:
`auth/types.ts`'s `TokenClaims.role`/`organization_id` are typed
`Role | null | undefined`, `auth/store.ts` reads them defensively, and
`permissions/capabilities.ts` treats a `null` role as least-privilege
(equivalent to `viewer`) rather than throwing or granting broad access
by default. See `authorization.md` for how that plays out.

**This is the one frontend-blocking backend issue this prompt
discovered and is explicitly flagging**, per Prompt 001's own
instruction to document rather than silently work around it. The fix
belongs in `services/authentication-service/app/services/authentication.py`'s
login flow (pass `extra_claims={"role": user.role, "organization_id": ...}`
to `TokenService.issue`) — out of scope for this frontend prompt to
implement, since it's a backend service change.

## Session architecture

- **Storage**: `localStorage`, via Zustand's `persist` middleware
  (`auth/store.ts`). This is a deliberate trade-off, not an oversight:
  the backend supports no `httpOnly` cookie to restore a session from,
  so there is no lower-risk storage option available against the
  backend as it exists today. An XSS vulnerability could read these
  tokens — standard mitigations (strict CSP, dependency hygiene) apply
  as they would to any bearer-token SPA.
- **Token decoding**: `auth/jwt.ts` decodes (never verifies) the JWT
  payload client-side, for UX only — reading `exp` and the (possibly
  absent) `role`/`organization_id`. The backend
  (`shared_core.security.jwt.decode_token`) remains the only
  authoritative verifier; nothing here makes a security decision.
- **Wiring**: `auth/session.tsx`'s `AuthBootstrap` (mounted in
  `AppProviders`) connects the store to `api/client.ts` — see
  `dependency-boundaries.md`.
- **`useSession()`** (`auth/session.tsx`) is the one hook every
  component should use for "am I logged in, and as whom" — never read
  `useAuthStore` directly outside of `auth/`.

## What's NOT built yet

No login page exists (Prompt 001 §13 explicitly forbids building the
complete login UI in this prompt). `auth/guards.tsx`'s `AuthGuard` is
real, tested code, but is **not wired into any route** —
`app/(app)/layout.tsx` documents exactly why in a comment: gating the
one existing page (the dashboard) with no login page to redirect to
would break the one thing that currently works. Wire `<AuthGuard>` into
`app/(app)/layout.tsx` once a login flow ships.
