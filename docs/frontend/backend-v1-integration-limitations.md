# Backend V1 Integration Limitations

A running, cross-prompt log of real backend limitations discovered
during frontend implementation — never fixed from the frontend (Backend
V1 is frozen), always documented and worked around honestly. Each entry
names the prompt that discovered it, the limitation, and the frontend
behavior built around it. See each entry's linked doc for the full
detail and source-inspection evidence.

## `role` / `organization_id` JWT claims not populated at login

**Discovered**: Prompt 001. **Still open**: Prompts 003, 004.

`services/authentication-service/app/services/authentication.py`'s
login flow issues the access token via `TokenService.issue(user.id,
session_id=...)` with no `extra_claims` — a real access token carries
only `sub`/`iss`/`iat`/`exp`/`jti`. `services/api-gateway-service`
reads `claims.get("role")`/`claims.get("organization_id")` expecting
them anyway.

**Frontend behavior**: every `TokenClaims`/`AuthUser` field that
depends on this is typed nullable and handled defensively — the user
menu shows "Not assigned"/"No organization" rather than guessing;
permission-aware navigation (Prompt 003) treats a `null` role as
visible-to-all rather than throwing or granting broad access. Full
detail: `architecture/authentication.md`.

## No confirmed `notification-center-service` read/list REST contract

**Discovered**: Prompt 003.

The service's existence and general capability are documented in
`backend-feature-matrix.md`, but its exact per-notification
read/list/mark-read route shapes weren't confirmed during that prompt.

**Frontend behavior**: `components/navigation/notification-area.tsx`
implements the full UI (unread badge, panel, loading/error states) but
never triggers a fetch — the panel always shows its honest empty
state. Wire `features/notifications` to a real API function once the
contract is confirmed.

## No unified global-search backend endpoint

**Discovered**: Prompt 003.

**Frontend behavior**: the command palette (`Ctrl`/`Cmd+K`) searches
only the pages a user can navigate to (`ROUTE_REGISTRY`), not records
inside a feature. This is documented as today's global-search entry
point, not a placeholder for a real cross-feature search.

## MFA challenge has no frontend entry UI

**Discovered**: Prompt 004.

`POST /auth/login` can return `{mfa_required: true, mfa_challenge_id}`
instead of tokens (confirmed by source inspection,
`architecture/authentication.md`) — but the exact contract for
*submitting* an MFA code (which endpoint, what payload) wasn't
confirmed or exercised in this prompt.

**Frontend behavior**: `auth/types.ts#isMfaChallenge` detects this
result and the login form shows a plain message explaining that
multi-factor sign-in isn't supported by this interface yet, rather
than inventing a code-entry flow against an unconfirmed second-step
contract.

## No approved E2E test credentials

**Discovered**: Prompt 004.

**Frontend behavior**: `tests/e2e/auth.spec.ts` covers every login-flow
behavior that doesn't require a real successful authentication (page
load, protected-route redirect, error presentation via mocked
responses, logout) but does not attempt a full successful-login E2E
against a live backend, per §28's explicit "never commit credentials."
The same success path is covered by a unit test against a mocked API
response instead.
