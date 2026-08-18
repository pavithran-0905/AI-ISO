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

## No metric-series-discovery endpoint (`observability-platform-service`)

**Discovered**: Prompt 006.

`GET /observability/metrics` is real and well-typed (`MetricsResponse`
with real `series`/`samples` fields), but requires `series_id: UUID`
as a required query parameter — and no endpoint exists to list/discover
what series ids are available for an organization or service. The
series' own descriptive fields (`name`, `metric_type`, `unit`,
`service_name`) are only returned *after* querying with an already-known
id, which doesn't help with discovery.

**Frontend behavior**: no Metrics/charts UI was built at all this
prompt (`docs/frontend/rfi/monitoring.md`'s own "What's PLANNED").
Building a metric selector against a guessed-at series id would be
exactly the kind of endpoint/field invention Prompt 006 §2 forbids.
Revisit once a discovery endpoint exists (e.g. `GET /observability/metrics/series`
or similar) or a confirmed way to enumerate series ids is found.

## `observability-platform-service` events have no asset correlation

**Discovered**: Prompt 006.

`ObservabilityEventResponse` (`GET /observability/events`) has no
asset-id reference field — only an optional `service_name: str | None`.
There is no reliable way to determine which `inventory-service` asset
(if any) a given event relates to.

**Frontend behavior**: the Monitoring Events timeline and Asset Detail
page are built independently — Asset Detail does not attempt to show
"events for this asset," and the Events page never claims an
asset-level scope it can't back with real data.

## `inventory-service` has no category/class/location name-resolution endpoint

**Discovered**: Prompt 006.

`AssetResponse.category_id`/`.class_id`/`.location_id` are bare UUIDs.
The underlying category/asset-class/location service and repository
code exists internally (`app/services/category.py`,
`app/services/asset_class.py`, `app/services/location.py`) but none of
it is wired to an API router (`app/api/__init__.py`'s registered
routers: `analytics, asset, export, group, health, import_,
relationship, search, statistics, topology` — no `category`/`class`/`location`
router among them).

**Frontend behavior**: Asset Detail shows these three fields as raw,
clearly-labeled ids ("Category id: `<uuid>`") rather than inventing
resolved names. Add a category/class/location router to
`inventory-service` (a backend change, out of scope for this frontend
prompt) to unblock resolving them to human-readable labels.

## `GET /inventory/search` has no `health` filter parameter

**Discovered**: Prompt 006.

Confirmed by reading the route handler directly
(`services/inventory-service/app/api/search.py`): the only filters are
`asset_type`, `status`, `owner_id`, `project_id`, and free-text `q` —
`health` isn't one of them, even though `AssetResponse.health` is a
real, distinct field from `status`.

**Frontend behavior**: the Monitoring Overview's "Critical issues"
section fetches one bounded, sorted page (100 most-recently-updated
assets) and filters by `health` client-side, rather than issuing an
unbounded fetch or fabricating server-side filtering that doesn't
exist. The UI notes explicitly when this scan was truncated relative
to the organization's total asset count.

## `GET /alerts` has no pagination, search, or sort parameters

**Discovered**: Prompt 007.

Confirmed by reading `services/alerting-service/app/api/alerts.py`'s
route signature and the `AlertService.list_for_org` method it calls
(`app/services/alert.py`): the only accepted parameters are
`organization_id` (required), `status`, and `severity`. There is no
`page`/`page_size`/`sort`/`q`.

**Frontend behavior**: `features/alerting`'s Alerts page applies
free-text search and column sorting entirely client-side, over the
endpoint's own complete (not paginated) result for the active
status/severity filter — this is honest specifically because nothing
is hidden behind a page boundary the client can't see, unlike a
bounded scan over a paginated endpoint (contrast with Monitoring's
"Critical issues," above, which *is* a documented incomplete scan).
`status`/`severity` themselves are still sent as real server-side
query parameters.

## No Reopen or Suppress/Unsuppress action on an alert instance

**Discovered**: Prompt 007.

`AlertInstance`'s internal state machine
(`services/alerting-service/app/services/alert.py`'s `_TRANSITIONS`)
permits `RESOLVED → OPEN` and `SUPPRESSED → OPEN`, but no route in
`app/api/alerts.py` ever calls `transition(..., AlertStatus.OPEN,
...)` — there is no `POST /alerts/{id}/reopen` or equivalent. Likewise,
suppression is a separate resource (`GET/POST /alert-suppressions`,
evaluated at ingestion time) with no corresponding
"unsuppress this specific alert instance" endpoint — a grep for
"unsuppress" across the service returns nothing.

**Frontend behavior**: `AlertActions` exposes exactly the four
mutations that are real routes — Acknowledge, Resolve, Escalate, Close
— and hides every action once an alert reaches
`resolved`/`closed`/`expired`, since there is no backend way to move it
back. No "Reopen" or "Unsuppress" button was built.

## No permission/role distinction on any `alerting-service` route

**Discovered**: Prompt 007.

Every route across `app/api/alerts.py`, `app/api/maintenance_windows.py`,
`app/api/alert_configuration.py`, and `app/api/alert_analytics.py` uses
only `Depends(get_current_user_id)` — which decodes the JWT for a user
id and nothing else. No route checks a role or a fine-grained
permission before allowing a read or a mutation (acknowledge, resolve,
escalate, close all included).

**Frontend behavior**: `AlertActions` still gates each mutation button
behind the existing coarse capability model
(`@/permissions`, `usePermissions().can(...)`) as a pure UX
convenience — hiding a button saves a read-only viewer a wasted click
and a backend 403, per §25's own framing ("frontend checks are UX
only"). It does not simulate or claim any real backend authorization
that doesn't exist.

## `AlertStatistics` has several untyped nested fields

**Discovered**: Prompt 007. Same pattern as the Prompt 005 entry
above ("Several V1 statistics endpoints have untyped nested fields").

`AlertStatisticsResponse.top_sources`, `.top_rules`, `.trend_data`, and
`.escalation_statistics` are `dict[str, Any]` at the Pydantic schema
level, with no further-confirmed internal shape.

**Frontend behavior**: `features/alerting/types#AlertStatistics` only
declares the well-typed scalar fields (counts, ratios, durations,
`computed_at`) — the four untyped fields are never fetched into a
frontend type or rendered.

## An alert's `source_reference` is a free-form object with no fixed key — and no route resolves it to an inventory asset

**Discovered**: Prompt 007.

`AlertResponse.source_reference` is `dict[str, Any]`
(`app/schemas/alert.py`), populated by whatever the ingesting caller
passed to `AlertIngestionService.ingest` at creation time
(`app/services/ingestion.py`) — there is no fixed key (such as an
`asset_id`) guaranteed to exist in it. Separately,
`app/clients/inventory_client.py` defines an `InventoryClient` with a
real `get_asset(asset_id)` method reading `inventory-service`'s own
`GET /inventory/assets/{id}` — but nothing in the service ever
constructs or calls it outside its own isolated unit test
(`tests/test_clients.py`); no route wires it into an alert response.

**Frontend behavior**: Alert Detail shows `source_reference` as raw,
labeled key/value pairs (matching how Asset Detail already shows its
own unresolvable ids) rather than assuming a particular key exists.
No Alerting↔Monitoring cross-link was built from an alert to a
specific asset — there is no real, confirmed relationship to link
through today. Wiring `InventoryClient` into a real route (a backend
change, out of scope for this frontend prompt) would be a prerequisite
for building that link honestly.

## `reporting-service` performs no tenant isolation on `organization_id`

**Discovered**: Prompt 008.

Every dependency-injection factory in `services/reporting-service/app/api/deps.py`
(`get_job_service`, `get_template_service`, `get_schedule_service`,
`get_archive_service`, `get_statistics_service`, and every repository
factory) constructs its repository with **no `tenant_scope` argument** —
e.g. `ReportJobRepository(session)` (`deps.py:196`) — even though
`shared_core.database.repository.BaseRepository` accepts one and only
applies row-level org scoping when it's actually passed
(`packages/shared-core/src/shared_core/database/repository.py:54-80`).
`organization_id` is therefore a plain, caller-supplied, unchecked
query/body parameter on nearly every endpoint (reports, templates,
schedules, recipients, distributions, archive, statistics) — nothing
in this service stops an authenticated caller from passing a different
organization's id and reading its reports, templates, schedules, or
archive. This is a strictly worse gap than the "no permission checks"
pattern already seen in `alerting-service`: that one only means every
authenticated user can act on data they can already see; this one
means the `organization_id` filter itself isn't enforced at all.
Confirmed no auth/tenant middleware fills the gap either — the
service's own middleware stack (`app/core/factory.py:184-197`)
registers only CORS/Timing/RequestContext/Localization/RequestValidation/
SecurityHeaders.

**Frontend behavior**: every Reporting API call still sends the real,
currently-selected `organization_id` (never a hardcoded or guessed
value) — the frontend does not exploit or route around this gap. This
is flagged here as a backend authorization issue for
`reporting-service` to fix (scoping every repository construction with
its `tenant_scope`), not something a frontend change can or should
paper over.

## `reporting-service` performs no permission/role check on any route

**Discovered**: Prompt 008. Same pattern as the Prompt 007 entry above
("No permission/role distinction on any `alerting-service` route").

Every router (`app/api/reports.py`, `app/api/templates.py`,
`app/api/delivery.py`) uses only `Depends(get_current_user_id)`, which
decodes the JWT for a user id and nothing else — confirmed across
every route in all three files.

**Frontend behavior**: `features/reporting` gates every mutation
button behind the existing coarse role capability model
(`@/permissions`) as a pure UX convenience, mapped onto the closest of
the 9 real actions (`generate`→`execute`, schedule management→`execute`,
distribution/archive/share→`export`, template approval→`approve`) —
never a simulation of real backend authorization.

## `GET /reports` has no pagination, search, or sort parameters

**Discovered**: Prompt 008. Same pattern as the Prompt 007 `GET /alerts`
entry above.

Confirmed by reading `app/api/reports.py:136-150`: the only accepted
parameters are `organization_id` (required), `category`, and
`enabled_only`. Likewise `GET /reports/templates` (only `category`),
`GET /reports/schedules` (only `report_id`), and `GET /reports/distributions`/
`GET /reports/archive` (a `limit` up to 1000 but no offset/cursor —
first-N only, no true pagination).

**Frontend behavior**: the Reports list applies free-text search and
column sorting entirely client-side over the endpoint's own complete,
unpaginated result for the active `category`/`enabled_only` filter —
honest because nothing is hidden behind a page boundary the client
can't see, the same reasoning already established for Alerting's own
list page.

## Reports/templates/schedules expose no `version` field — no reachable optimistic-locking conflict

**Discovered**: Prompt 008.

`BaseRepository.update()` (`packages/shared-core/.../repository.py:113-140`)
supports an `expected_version` argument and increments every entity's
real `version` column on write — but `ReportResponse`, `TemplateResponse`,
and `ScheduleResponse` never expose that column, and no service method
in `app/services/report.py`/`template.py`/`schedule.py` ever passes
`expected_version=` when calling `.update()`. Concurrent edits to the
same report/template/schedule are silently last-write-wins; there is
no reachable 409 to react to.

**Frontend behavior**: §30 asks the frontend to "respect the actual
version/concurrency contract" and show "Your report changed elsewhere.
Reload the latest version before continuing" on a real conflict —
since no such conflict is ever reachable through this API today, no
version-conflict UI was built. Every write waits for the backend's
confirmed response before updating what's shown (no optimistic
update), which is the concurrency safeguard this contract can actually
support.

## No way to re-fetch a past generation's results — `POST /reports/generate` is the only place they're visible

**Discovered**: Prompt 008.

There is no `GET /reports/{id}/executions` and no
`GET /reports/executions/{execution_id}` endpoint (confirmed: neither
exists in `app/api/reports.py`). An execution and its export artifacts
are only ever visible in the single `GenerateResponse` returned by the
`POST /reports/generate` call that produced them (or indirectly, as a
one-line summary, via `GET /reports/history`).

**Frontend behavior**: Report Detail keeps the most recent
`GenerateResult` in local component state and shows it right below the
report's own Actions section — it is honestly described as "Latest
generation," not a browsable list of past runs, and disappears on
navigating away or reloading the page. History (`ReportHistorySection`)
is the only durable record of past generations, and it only carries a
summary string, not artifacts.

## No revoke endpoint for a share link

**Discovered**: Prompt 008.

`POST /reports/exports/{id}/share` mints a token
(`app/services/distribution.py`); the only way it stops working is its
own `expires_at`, checked lazily on the next redemption attempt
(`resolve_share_token()`). No endpoint exists to invalidate a link
before that.

**Frontend behavior**: `ShareExportDialog` shows the minted token and
its real expiry, but offers no "revoke" action — building one would
require inventing a capability the backend doesn't have.

## `GET /reports/archive` cannot be filtered by report id

**Discovered**: Prompt 008.

Confirmed by reading `app/api/delivery.py:465-486`: the only filters
are `search` (title substring) and `status`, plus a `limit`. There is
no `report_id`/`job_id` parameter.

**Frontend behavior**: Report Detail does not attempt an "Archive for
this report" section — it would require fetching the organization's
entire archive and filtering client-side against an unbounded,
`limit`-capped result, which could silently miss entries beyond the
cap. The org-wide Archive page (`/reporting/archive`) is the only
place archived reports are browsable, consistent with not fabricating
a per-report view the backend can't back reliably.

## AI-narrative sections have no independent loading/generating state

**Discovered**: Prompt 008.

An `AI_SUMMARY` designer section is rendered inline as part of the
single synchronous `POST /reports/generate` call
(`app/renderer/engine.py`'s `_render_ai_section`) — there is no
separate endpoint to poll a narrative's own generation progress. It
resolves to exactly one of two real backend states: success (prose
text, optionally with a citations table) or failure (an error message,
surfaced in `degraded_sections` without failing the rest of the
report).

**Frontend behavior**: the Generate dialog shows one loading state for
the whole pipeline (§13/§21's "loading"/"unavailable"/"error" — no
separate "generating narrative…" sub-state exists to show, since the
backend has none). A degraded AI section is visible via
`degradedSections`, labeled honestly, never presented as if it
succeeded. The narrative's actual rendered text is only visible by
downloading/opening the generated artifact — there is no JSON view of
rendered section content (`GenerateResponse` returns only execution
metadata and export artifacts, never per-section rendered output).
