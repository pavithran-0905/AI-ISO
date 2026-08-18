# Backend V1 Integration Limitations

A running, cross-prompt log of real backend limitations discovered
during frontend implementation — never fixed from the frontend (Backend
V1 is frozen), always documented and worked around honestly. Each entry
names the prompt that discovered it, the limitation, and the frontend
behavior built around it. See each entry's linked doc for the full
detail and source-inspection evidence.

## `role` / `organization_id` JWT claims not populated at login

**Discovered**: Prompt 001. **`role` still open**: Prompts 003, 004,
005. **`organization_id` worked around**: Prompt 005 (see below).

`services/authentication-service/app/services/authentication.py`'s
login flow issues the access token via `TokenService.issue(user.id,
session_id=...)` with no `extra_claims` — a real access token carries
only `sub`/`iss`/`iat`/`exp`/`jti`. `services/api-gateway-service`
reads `claims.get("role")`/`claims.get("organization_id")` expecting
them anyway.

**Frontend behavior**: every `TokenClaims`/`AuthUser` field that
depends on `role` is typed nullable and handled defensively — the user
menu shows "Not assigned" rather than guessing; permission-aware
navigation (Prompt 003) treats a `null` role as visible-to-all rather
than throwing or granting broad access.

`organization_id` specifically was unblocked in Prompt 005: almost
every real business endpoint (alerts, assets, automation, reports, org
analytics) requires it, and having *no* way to obtain one would have
made most of the dashboard un-buildable against real data. `GET /organizations`
itself needs only auth, no `organization_id` — the new `organization/`
module (`docs/frontend/developer-guide/dashboard.md`) uses that to let
the user pick which organization to view (auto-selected when they only
have one), entirely frontend-side, no backend change. `role` has no
equivalent workaround since nothing analogous to "list my roles" exists
to select from.

Full detail: `architecture/authentication.md`.

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

## No cross-platform "recent activity" / audit feed

**Discovered**: Prompt 005.

Every audit/activity endpoint found by direct source inspection is
scoped narrowly: `GET /users/activity` is explicitly the *caller's
own* recent activity, not organization- or platform-wide
(`services/user-management-service/app/api/activity.py`'s own
docstring); `GET /gateway/audit`, `GET /policies/audit`,
`GET /dashboards/audit` are each one service's own internal audit
trail of actions taken through that service specifically, not general
business activity. No single endpoint aggregates "what changed
recently" across the platform.

**Frontend behavior**: the dashboard's "Recent Activity" section
(`docs/frontend/user-guide/dashboard.md`) is explicitly labeled
"Recent automation activity" and sourced from
`GET /automation/executions` — the closest honest substitute, never
presented as a general activity feed it isn't.

## Several V1 statistics endpoints have untyped nested fields

**Discovered**: Prompt 005.

`AlertStatisticsResponse.top_sources`/`.trend_data` and
`AutomationStatisticsResponse.execution_heatmap`/`.resource_usage` (and
similarly-shaped fields on other `*StatisticsResponse` schemas) are
typed `dict[str, Any]` at the Pydantic schema level — real fields with
no further-confirmed internal shape.

**Frontend behavior**: the dashboard doesn't render any chart or table
built from these fields (Prompt 005 §28 explicitly forbids "silently
transforming unknown data" to paper over an inconsistent contract).
Only individually-typed, scalar fields from `OrganizationStatisticsResponse`
(user/project/asset/workflow/automation/validation counts) back the
KPI cards. Building a trend chart against these fields is possible
once their real internal shape is confirmed (by reading the
statistics-computation code, not guessed at) — see
`docs/frontend/rfi/dashboard.md`'s "What's PLANNED."

## Gateway's own GET analytics/services/reports/audit endpoints have no visible auth enforcement

**Discovered**: Prompt 005.

`services/api-gateway-service`'s `GET /gateway/services`,
`GET /gateway/statistics`, `GET /gateway/reports`, `GET /gateway/audit`
route handlers take no `CurrentUserId`/auth dependency, and the
service's own middleware stack (`app/factory.py`) registers no
authentication middleware — unlike every other org-scoped endpoint
this prompt used (alerts, assets, automation, reports, org analytics),
which all do enforce a bearer token. This wasn't independently
re-verified further (e.g. via a gateway-level API-key mechanism this
review didn't check) — flagged as a possible gap, not a confirmed one.

**Frontend behavior**: the dashboard never calls any of these four
endpoints — only `GET /gateway/health` (which similarly has no visible
auth dependency, but is read-only, non-sensitive per-service health
data) and `GET /health` (deliberately unauthenticated by design, the
liveness check). If this turns out to be a real gap, it's a backend
authorization issue to fix in `services/api-gateway-service`, not
something the frontend should route around by inventing its own
access check.
