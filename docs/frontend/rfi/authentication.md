# Authentication

Per Prompt 004 §31, this honestly separates **IMPLEMENTED** from
**PLANNED** for the authentication experience — nothing here claims
future functionality as currently available. See `../rfi/README.md`
and `../rfi/application-shell.md` for the foundation this builds on.

## Authentication UX — IMPLEMENTED

A production login page (`/login`): email/password with format
validation, a show/hide password toggle, a "keep me signed in" option,
loading and duplicate-submission-safe button states, and safe,
non-technical error messages for every failure class the backend can
return (invalid credentials, account not permitted to sign in, rate
limiting, server error, network failure, timeout). Built on the real
`POST /auth/login` contract confirmed by source inspection of
`services/authentication-service`, not guessed at.

**PLANNED**: registration and a multi-factor-authentication entry UI.
The backend supports both (`POST /auth/register`, and `POST /auth/login`
can return an MFA challenge) but neither has a UI in this prompt —
registration wasn't in this prompt's scope, and a real MFA-code UI is
deliberately not invented against a contract this prompt didn't build
out end-to-end (see Backend V1 limitations below).

## Session management architecture — IMPLEMENTED

Bearer-token session (`localStorage`, Zustand `persist` — Prompt 001's
documented trade-off, unchanged here), with reactive expiry detection:
any protected API call returning 401 clears the session and is
distinguishable from an explicit sign-out (`lastClearReason`), so the
login page can honestly tell a user their session expired rather than
showing a generic sign-in prompt every time. No session-refresh
polling exists — expiry is detected the next time it's actually
exercised, not preemptively.

## Protected routes — IMPLEMENTED

Every route under the main application shell now requires an
authenticated session (`AuthGuard`, wired into `app/(app)/layout.tsx`).
An unauthenticated visit redirects to `/login` with a validated
return-to destination (`?from=`) — validated specifically against
open-redirect: only a same-app absolute path is ever honored, never an
external or protocol-relative URL. This is UX routing, not a security
boundary — the boundary is, and remains, the backend independently
verifying every protected call's own token
(`../architecture/authorization.md`).

## Permission-aware frontend — IMPLEMENTED (mechanism, unchanged this prompt)

Carried over from Prompt 003 unchanged: navigation filters by role
when a route declares one, and every route today declares `roles: null`
(visible to all) because the backend doesn't populate a `role` claim
reliably at login — see Backend V1 limitations.

## Accessibility — IMPLEMENTED

WCAG 2.2 AA target: every form field has a real `<label>` (never
placeholder-only), the password-visibility toggle has an accessible
name that changes with its state ("Show password" / "Hide password")
and is fully keyboard-operable without submitting the form, errors are
associated with their field via `aria-describedby` and announced via
`role="alert"`, and focus/tab order follows visual order. Built on the
same accessible primitives established in Prompt 002/003 rather than
new bespoke focus code.

## Security boundaries — IMPLEMENTED

The frontend never invents, logs, or displays a credential, token, or
raw backend error message. Login failures are deliberately
under-informative by design (§7: identical messaging for a wrong email
vs. a wrong password) so the UI itself can't be used to enumerate valid
accounts. Every security-relevant decision (token validity, role,
permission) is made and re-verified by the backend on every request —
the frontend's guards exist to route the user correctly, not to
authorize anything.

## Backend/frontend separation — IMPLEMENTED

Zero backend files were touched implementing this prompt (verified —
see the commit's own scope). Every discovered limitation was
implemented around, not worked around by guessing at or extending the
backend contract.

## Backend V1 limitations (this prompt)

- **`role`/`organization_id` JWT claims absent at login** — carried
  over from Prompt 001/003, unchanged and still accurate: a real
  access token today carries only `sub`/`iss`/`iat`/`exp`/`jti`. The
  permission-aware navigation mechanism this enables stays untested
  against a real restricted route until the backend populates it.
- **MFA challenge has no frontend UI.** `POST /auth/login` can return
  `{mfa_required: true, mfa_challenge_id}` — the login form detects
  this and tells the user plainly that this interface doesn't support
  entering a code yet, rather than inventing an MFA-entry flow against
  an unconfirmed exact contract shape for step two of that exchange.
- **No approved E2E test credentials exist in this repository.** A
  full successful-login end-to-end test against a live backend isn't
  implemented for this reason (§28) — the same success path is covered
  by `login-form.test.tsx`'s unit tests against a mocked API response
  instead.

See `../backend-v1-integration-limitations.md` for the running,
cross-prompt log of every such limitation.
