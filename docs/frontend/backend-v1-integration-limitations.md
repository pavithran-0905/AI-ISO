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

**One service enforces this gap as a hard block, not a silent no-op**:
`observability-platform-service/app/api/deps.py#get_organization_id`
derives `organization_id` strictly from the JWT's own claims (never a
query param or header, unlike every other service) and raises a `403`
when the claim is absent — which, given the gap above, is always.
`/observability/topology` and `/observability/events` (Monitoring's
Services and Events tabs) are therefore unreachable for any caller
under the current login flow, not a permissions issue with any
specific account. Closing it for real means either populating
`organization_id` at login (benefits every service, the more correct
fix) or making this one service accept a caller-supplied value like
the rest of the platform does (narrower, but moves it away from its
own more-defensible design). Deliberately left unfixed pending that
decision — every other Monitoring tab (Assets, Overview) is unaffected.

Full detail: `architecture/authentication.md`.

## No confirmed `notification-center-service` read/list REST contract

**Discovered**: Prompt 003. **Resolved**: Prompt 016.

The service's existence and general capability are documented in
`backend-feature-matrix.md`, but its exact per-notification
read/list/mark-read route shapes weren't confirmed during that prompt.

**Frontend behavior (Prompt 003)**: `components/navigation/notification-area.tsx`
implemented the full UI (unread badge, panel, loading/error states) but
never triggered a fetch — the panel always showed its honest empty
state.

**Resolution (Prompt 016)**: the contract is now confirmed
(`GET /notifications`, `GET /notifications/{id}`,
`POST /notifications/{id}/read`, `.../acknowledge`,
`GET /notifications/{id}/deliveries` — `services/notification-center-service/app/api/notifications.py`)
and `NotificationArea` now calls it for real. See
`docs/frontend/developer-guide/notifications.md` for the full
architecture and the severe permission finding this route set carries.

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

**Discovered**: Prompt 006. **Reconfirmed**: Prompt 011, which also
found `owner_id` in the same situation (`app/services/owner.py` exists,
unrouted) — Asset Detail shows all four as raw ids for the same reason.

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

## `automation-service` and `scheduler-service` perform no tenant isolation; `scheduler-service` leaves most routes unauthenticated entirely

**Discovered**: Prompt 009. Same pattern as the Prompt 008
`reporting-service` entry above, found again in two more services.

`automation-service`: every DI factory in `app/api/deps.py` constructs
its repositories with `session` only, never the `tenant_scope`
argument `BaseRepository` accepts — confirmed by grepping `tenant_scope`
across the whole service; the only hits are the pass-through parameter
in `app/repositories/*.py` itself. Worse than Reporting's version of
this gap: `GET /automation/jobs/{id}`, `PUT`, `DELETE`, and
`POST .../execute|cancel|pause|resume` take **no `organization_id` at
all** — they resolve purely by primary key with zero ownership check,
so any authenticated user can execute or delete any job on the
platform by id, not just read across tenants.

`scheduler-service` has the identical no-`tenant_scope` gap, and
additionally: of its 42 non-health routes, only 8 use any auth
dependency at all (`create_job`, `update_job`, `delete_job`, `run_job`,
`pause_job`, `resume_job`, `cancel_job`, `recover_failure`,
`create_window`, `generate_report`) — every list/get/logs/trigger/
dependency/retry-policy/analytics route (30 of 42) has no
`Depends(...)` for identity at all, confirmed by parsing every route
function's signature and finding no global `dependencies=[...]` on the
app or router. `scheduler-service` was not built against in this
prompt (see the next entry) specifically because of this and the
absent automation link.

**Frontend behavior**: `features/automation`/`features/workflows`
still always send the real, currently-selected `organization_id` on
every call that accepts one. This is flagged as a backend
authorization issue for both services to fix, not something a frontend
change can or should route around.

## `scheduler-service` never actually dispatches an `automation_job`

**Discovered**: Prompt 009.

`scheduler-service`'s own execution service states outright (its
module docstring): it dispatches by publishing a `JobStarted` event
with the job's payload and records success once that publish succeeds
— it does not perform the job's own work. Grepping `automation` across
the entire `scheduler-service` app tree returns zero hits beyond the
`JobType.AUTOMATION_JOB` enum member's literal value; there is no
`AutomationClient`, no HTTP call into `automation-service`, and
`automation-service` has no consumer for whatever `scheduler-service`
publishes. A scheduled job of type `automation_job` reports
`completed` regardless of whether any automation ever ran.

**Frontend behavior**: `scheduler-service` isn't integrated into this
feature at all — `automation-service`'s own executions (the real
signal for "did an automation run and how did it go") are what
Automation/Executions shows. Building a "scheduled automations" view
against `scheduler-service` would show a real-looking but functionally
meaningless completion status.

## `automation-service` has full parameter and target models with zero routes

**Discovered**: Prompt 009.

`AutomationParameter` (model, schema, service, DI wiring) and
`AutomationTarget` (same) are both fully implemented server-side.
Neither has a single `@router`-decorated endpoint — confirmed by
enumerating every route in `app/api/jobs.py`, `executions.py`,
`templates.py`, `statistics.py`, `reports.py`. `AutomationParameter.parameter_type`
is a plain unvalidated `str(32)` (default `"string"`), not an enum —
there is no `ParameterKind`/`ParameterType` enum anywhere in the
service, and no `is_secret`/`allowed_values`/`min`/`max`/`pattern`
field on it at all. `AutomationTarget` (with real `target_type`/
`connector_type` enums, `credential_ref` via secrets-management) is
equally real and equally unreachable.

`AutomationJob.target_selector: dict[str, Any]` is also confirmed
write-only — no execution code path ever reads it. The only working
way to attach targets to a run is `POST .../execute`'s own
`target_ids: list[UUID]`, resolved against rows that, per the above,
can only be created by direct database access — there is no create
route for a target either.

**Frontend behavior**: `VariablesEditor` is a plain free-form key/value
editor, not a schema-driven typed form — building one against a schema
that cannot be fetched would be exactly the "do not hardcode
parameters" invention §13 forbids. No target picker was built for the
same reason: there is nothing real to populate it with. Runs execute
with no targets, on the automation-service host itself, which
`RunAutomationDialog`'s confirmation step states explicitly.

## `automation-service` has full schedule and rollback/approval models with zero routes, and its cron engine never starts

**Discovered**: Prompt 009.

`AutomationSchedule` (model, schema, fully-implemented
`AutomationScheduleService` with `list_for_job`/`create`/`set_enabled`/
`record_run`/`delete`, DI-wired as `ScheduleSvc`) has zero routes.
Separately, `app/scheduling/scheduler_integration.py` builds a
`shared_core.scheduler.Job` from a schedule, but nothing ever
constructs the actual `SchedulerManager` that would run it — confirmed
by reading `app/core/factory.py`'s startup sequence (`_lifespan`),
which starts the database, cache, events, notifications, HTTP client,
connector manager, and queue worker, and never touches the scheduler
integration module at all, despite that module's own docstring
claiming otherwise. `next_run_at` is therefore never computed by
anything.

Approvals (`ExecutionMode.APPROVAL_REQUIRED` exists as an enum value,
but `create_execution` never checks for an approval before dispatching)
and rollback (`AutomationRollbackService`, `RollbackSvc`) are the same
pattern: fully implemented, DI-wired, zero routes.

**Frontend behavior**: no automation scheduling UI was built (§22/§23)
— it would be entirely decorative against an engine that never starts.
No approval-gate UI for Automation either (unlike Workflows, where
approvals are real and routed — see below); `approval_required` as an
execution mode is offered in the create/edit form's dropdown (it's a
real enum value the backend accepts) but nothing in the UI implies it
actually pauses for approval, since nothing backend-side enforces it.

## An execution's selected targets are only recoverable from an internal `_target_ids` key inside its `variables`

**Discovered**: Prompt 009.

`AutomationExecutionResponse` has no `target_ids`/`targets` field.
`AutomationExecutionService.create_execution` instead writes the
caller's selected target ids into the execution's own `variables` dict
under the key `"_target_ids"` (`app/services/execution.py`), so it
round-trips back mixed in with the operator's real variables on every
read.

**Frontend behavior**: `features/automation/lib/execution-variables.ts#splitExecutionVariables`
strips this key out before showing "Variables" to a user, and surfaces
it separately as "Targets" — neither section is contaminated by the
other's data.

## `PUT /automation/jobs/{id}` is a full replace whose schema defaults `status` to draft

**Discovered**: Prompt 009.

`AutomationJobUpdateRequest.status: JobStatus = JobStatus.DRAFT`
(`app/schemas/job.py`) — a genuine default, not merely optional. Since
the endpoint is a full replace (not a partial patch), any update that
doesn't explicitly resend the current status silently demotes a live
(`active`) automation to `draft`. Separately, `POST /automation/jobs`
hard-codes the new job's status to `active` and ignores any
client-supplied value — there is no `status` field on the create
request at all.

**Frontend behavior**: `AutomationJobUpdateInput` (the frontend type)
makes every field required, and the edit form always sends the job's
current status explicitly; the create form never offers a status
control, since the backend would ignore it.

## Neither `automation-service` nor `workflow-runtime-service` exposes real-time execution updates

**Discovered**: Prompt 009. Same pattern already established for
Alerting/Reporting, confirmed again for both of these services.

Grepped `websocket|EventSourceResponse|StreamingResponse|text/event-stream`
across both service trees — zero hits in either. Both publish real
domain events to RabbitMQ (`AutomationStarted`, `AutomationCompleted`,
etc. on one side; workflow-equivalent events on the other), but
neither bridges them to an HTTP-reachable stream.

**Frontend behavior**: `useExecution`/`useWorkflowInstance` and their
log/step counterparts poll every 5 seconds while the run is active
(`ACTIVE_EXECUTION_STATUSES`/`ACTIVE_INSTANCE_STATUSES`) and stop
polling once it reaches a terminal status — no follow/pause-streaming
control is offered, since there is no stream to pause.

## No Retry endpoint on either service

**Discovered**: Prompt 009.

Grepped `retry` across both services' `app/api/` trees — the only hits
are repository imports for retry-history rows that are written
backend-side during dispatch but have no route to read, on either
service. No `POST .../retry` or `.../rerun` exists anywhere.

**Frontend behavior**: no Retry action was built. Re-running is done
through Run Automation/Run Workflow, which the UI describes as a fresh
run, never implying it resumes or reuses the failed attempt's own
history.

## No Monitoring or Alerting relationship from either automation service

**Discovered**: Prompt 009. Same discipline as the Prompt 007/008
cross-link findings.

Grepped `alert|monitoring_service|incident` across both
`automation-service` and `workflow-runtime-service` — zero hits beyond
enum *labels* that happen to contain those words (e.g.
`AutomationType.MONITORING_ACTIONS`). No job/execution/workflow/
instance schema carries an inventory-asset or alert reference, and
`automation-service`'s own `InventoryClient` (a real, fully-implemented
dynamic-inventory client) is dead code — wired into `app/api/deps.py`
but never called by any route or service method, the same dead-code
pattern already found in `alerting-service` during Prompt 007.

**Frontend behavior**: no Automation↔Monitoring or Automation↔Alerting
cross-links were built (§26/§27) — there is no real relationship to
link through today.

## `ai-assistant-service` applies no tenant filter on any by-id lookup — the worst instance of this pattern found all session

**Discovered**: Prompt 010.

Every prior "tenant isolation" finding this session (Reporting,
Automation) was at least the caller-supplied-but-unchecked pattern —
`organization_id` was accepted as a parameter but never verified
against the fetched row. `ai-assistant-service` goes one step further:
`ConversationService.get_by_id(self, conversation_id: UUID)`
(`app/services/conversation.py:34`) and `PromptService.get_by_id(self,
prompt_id: UUID)` (`app/prompts/service.py:90`) don't even *accept* an
`organization_id` parameter — both call straight through to
`require_by_id(id)` on a generic base repository with zero tenant
scoping anywhere in the call chain. A valid UUID for any
organization's conversation or prompt (obtained by guessing,
enumeration, or simply having seen it once) returns that
organization's real data to any authenticated caller, regardless of
which organization they belong to.

**Frontend behavior**: this frontend always sends the real,
currently-selected `organization_id` on every *list* call (the one
place a filter is genuinely applied server-side,
`list_for_org`/`list_for_user`), and never fabricates a client-side
tenant check for the by-id routes the backend itself doesn't enforce.
No workaround is possible from the frontend for a backend
authorization gap.

## `caller_permissions` / `allow_mutating_tools` are trusted from the request body with no cross-check against the caller's real role

**Discovered**: Prompt 010.

`ChatRequest.caller_permissions: list[str]` and `allow_mutating_tools:
bool` (`app/schemas/chat.py`) are read directly by the tool-execution
authorization gate to decide whether a model-requested tool call is
allowed — confirmed by source inspection of the executor, which checks
a tool's `required_permission` against exactly this client-supplied
list. Neither value is cross-checked against the caller's actual
JWT-derived identity in any way; a client can claim any permission
set, or set `allow_mutating_tools: true`, regardless of role.

**Frontend behavior**: `derivedCallerPermissions()`
(`features/ai-assistant/lib/caller-permissions.ts`) still populates
`caller_permissions` from the existing coarse capability model, purely
for consistency with how every other feature already sends permission
context — documented on the type itself as never a security boundary.
The mutating-tools toggle is additionally hidden client-side for a
role the coarse model denies `execute` to, which prevents an
accidental opt-in through this UI but does nothing to stop a crafted
request.

## `POST /ai/chat/stream` does not provide real token-level streaming

**Discovered**: Prompt 010.

The route's own module docstring (`app/api/chat.py`) is explicit: it
is a genuine `StreamingResponse` emitting real SSE frames, but the
underlying provider call is awaited to full completion first
(`turn = await chat.send(...)`) before the finished answer is chopped
into fixed 256-character `delta` chunks and dripped out. Total latency
to the last byte is identical to the synchronous `POST /ai/chat` — the
only difference is a cosmetic typewriter effect.

**Frontend behavior**: `chat-api.ts` deliberately consumes only
`POST /ai/chat`. Building a UI against `/chat/stream` would imply real
incremental generation the backend doesn't provide, which §10
explicitly forbids faking.

## No interactive per-tool-call confirmation endpoint

**Discovered**: Prompt 010.

`ChatRequest` carries `allow_mutating_tools` as a single whole-turn
flag; there is no endpoint or field anywhere that would let a client
pause a turn mid-flight to approve or deny one specific tool call the
model is about to make. A mutating tool is authorized for the entire
turn or denied outright within it — there is no narrower grain.

**Frontend behavior**: `MutatingToolsToggle` is a composer-level,
pre-emptive, OFF-by-default consent sent *with* the request, never a
fake mid-conversation "the assistant wants to do X, allow?" dialog
that the backend has no way to actually pause for.

## No agent-attribution field on any chat/message/conversation response

**Discovered**: Prompt 010.

`ChatRequest.agent_type` is accepted as a hint on every call, but
`ChatResponse`, `MessageResponse`, and `ConversationResponse`
(`app/schemas/chat.py`) carry no `agent_id`/`agent_type` field back —
confirmed by reading every field on all three schemas. There is no way
to ask "which agent actually produced this answer?" after the fact.

**Frontend behavior**: the agent picker in `Composer` is offered only
when starting a brand-new conversation (`isNewConversation`), and no
part of this feature ever renders an agent name as confirmed post-hoc
attribution — `AGENT_TYPES`' own docstring in `features/ai-assistant/types`
states this explicitly.

## No context-injection API for cross-module references

**Discovered**: Prompt 010.

Nothing in `ChatRequest` or any other schema accepts a structured
reference to an external entity (an alert id, an automation job id,
an asset id) that the model could be given as grounded context beyond
plain conversation text. The only way to give the assistant that
context is to say it in the message itself.

**Frontend behavior**: `AskAiButton` (§41) opens a new conversation
with a plain-text draft referencing the real entity's real name/id
(e.g. `Tell me about alert "Disk almost full" (id: a1).`) — never a
fabricated structured payload the assistant doesn't actually receive.

## Uniform `502`/`AIIOS-AI-0001` error for every chat failure mode

**Discovered**: Prompt 010.

A guardrail-infrastructure failure, every configured model provider
failing in the fallback chain, and an embedding-provider failure all
surface as the identical `502` status and `AIIOS-AI-0001` error code —
confirmed by source inspection of the exception handling in
`app/services/chat.py`. A client cannot distinguish "the AI is
misconfigured" from "every provider is down" from "the guardrail
service itself broke" without a raw backend log.

**Frontend behavior**: the composer surfaces the backend's own error
message via `ApiRequestError` on a failed send, without inventing a
more specific category the backend itself can't provide — and keeps
the typed message in the box so retrying is just pressing Send again.

## `GET /ai/models`'s `is_default` field is computed, not a real configured default

**Discovered**: Prompt 010.

`ModelProviderResponse.is_default` (`app/api/agents.py`) is set via
`index == 0` over `enumerate(registry.available_providers)` — i.e.
"alphabetically/insertion-order first configured provider" — not any
operator-configured default setting. Confirmed by source inspection;
no such setting exists anywhere in the model registry.

**Frontend behavior**: `catalogApi.listModels()` keeps the field on
its return type for completeness but this feature never renders it as
a "default" badge or otherwise treats it as meaningful, per its own
code comment.

## No delete/expire endpoint for assistant memory despite an `expires_at` column

**Discovered**: Prompt 010.

`AiMemory.expires_at` exists as a column and `MemoryCreateRequest`
accepts one, but no route reads or acts on it, and there is no
`DELETE`/clear endpoint of any kind on `/ai/memory` — confirmed by
reading every route in `app/api/insights.py`. A memory entry, once
created, is permanent and unexpiring in practice regardless of what
`expires_at` was set to.

**Frontend behavior**: `MemoryList` is read-only — this feature never
calls `POST /ai/memory` at all, since the assistant is the realistic
writer of its own memory and exposing a manual "remember this" form
with no way to undo it would be a one-way door.

## No permission/role check on any `ai-assistant-service` route

**Discovered**: Prompt 010. Same pattern as every service audited this
session (Alerting, Reporting, Automation, Workflow Runtime).

Every route across `chat.py`, `insights.py`, `knowledge.py`,
`agents.py`, and `prompts.py` depends only on
`Depends(get_current_user_id)` — none checks a role or fine-grained
permission, including the prompt-approval and rollback routes, which
one might expect to be more tightly held than a plain conversation.

**Frontend behavior**: mutation controls throughout this feature are
gated by the coarse role capability model (§25) — generate/ingest →
`create`, decide a recommendation → `approve`, prompt admin actions →
the administrative check, the mutating-tools toggle → `execute` — a
UX convenience only, consistent with every prior prompt's identical
finding.

## `inventory-service` applies no tenant filter on any by-id route, and no cross-check on any list route — the worst instance of this pattern found all session

**Discovered**: Prompt 011.

Every by-id route — `GET/PATCH/DELETE /inventory/assets/{id}`,
`GET/DELETE /inventory/relationships/{id}`,
`GET /inventory/groups/{id}/members`, `GET /inventory/topology`,
`GET/POST /inventory/import/{id}`, `GET /inventory/export/{id}` —
resolves purely by primary key, with **no `organization_id` parameter
of any kind** (confirmed by reading every route handler directly).
`shared_core.database.tenant.enforce_tenant_match` exists specifically
for this "defense in depth for an entity fetched by id" scenario — its
own docstring describes this exact case — but is never called anywhere
in this service. Separately, every *list* route
(`GET /inventory/assets`, `/search`, `/statistics`, `/analytics`,
`/groups`) takes `organization_id` as a client-supplied parameter with
zero cross-check against the caller's actual identity, and every
`AssetRepository`/`AssetRelationshipRepository`/etc. construction in
`app/api/deps.py` passes `tenant_scope=None` — `BaseRepository`'s own
automatic tenant-scoping mechanism (used correctly elsewhere in the
platform) is never engaged. Net effect: any authenticated user from
any organization can read or mutate any other organization's assets,
relationships, groups, or import/export jobs by id. This is a superset
of every prior "caller-supplied, unchecked `organization_id`" finding
this session (Reporting, Automation, AI Assistant) — this service adds
the by-id routes having no tenant parameter at all.

**Frontend behavior**: `features/infrastructure` always sends the
real, currently-selected `organization_id` on every list call (the one
place a filter is genuinely applied server-side) and fabricates no
client-side tenant check for the by-id routes the backend itself
doesn't enforce.

## `inventory-service` has full group-delete and membership-editing service methods with zero routes

**Discovered**: Prompt 011.

`AssetGroupService.delete`/`.add_member`/`.remove_member`
(`app/services/group.py` L98-119) are real, implemented methods — but
`app/api/group.py` only ever calls `list_for_org`, `create`, and
`resolve_members`. No `DELETE /inventory/groups/{id}` and no
add/remove-member route exist. The same "fully-implemented-but-unrouted"
pattern found repeatedly this session (categories/classes/locations/
owners in this same service; parameters/targets/schedules in
`automation-service`; memory-expiry/multi-agent-attribution in
`ai-assistant-service`).

**Frontend behavior**: `features/infrastructure/pages/groups-list-page.tsx`
offers create and list-with-membership-view only — no delete button,
no member-editing UI, since neither has anywhere to send a request.

## `inventory-service` silently builds a full asset history/audit/version trail with no route to read any of it

**Discovered**: Prompt 011.

`AssetHistoryService`, `AssetStatusHistoryService`,
`AssetHealthHistoryService`, `AssetLifecycleHistoryService`,
`AssetVersionService`, and `InventoryAuditService` are all real,
populated as side effects of every `AssetService.create`/`.update`
call (`app/services/asset.py` L226-378) — every status change, health
change, lifecycle transition, and version bump is durably recorded.
**Confirmed absent**: no route anywhere in this service reads any of
it back — no `/inventory/assets/{id}/history`, `.../status-history`,
`.../health-history`, `.../lifecycle-history`, `.../versions`, or
`/inventory/audit`. The backend is quietly building a complete audit
trail that is currently unreachable over HTTP.

**Frontend behavior**: Asset Detail shows only the current
`current_version` number (a plain integer, §21/§23's "respect
version/optimistic-lock information") and the current `updatedAt`
timestamp — no history/timeline view was built, since there is no
endpoint to build one against. `AssetResponse` also has no
`is_active`/`deleted_at` field, so a soft-deleted asset simply stops
appearing everywhere — there is no way for the frontend to distinguish
"never existed" from "deleted" via any response this service returns.

## No bulk-mutation route on any `inventory-service` router

**Discovered**: Prompt 011.

`shared_core.database.repository.BaseRepository.bulk_create`/
`.bulk_update`/`.bulk_delete` exist generically in the framework, but
`AssetService`/`AssetRepository` never call them, and no route (on
`asset.py`, `search.py`, or any other router) exposes a bulk-mutation
endpoint — no `PATCH /inventory/assets/bulk`, no bulk-enable/disable/
delete route of any kind.

**Frontend behavior**: no bulk-selection UI was built on the Assets
table (§24: "only implement bulk actions if V1 explicitly supports
them") — every mutation in this feature acts on exactly one asset at a
time, via its own real single-item route.

## `ImportJobResponse` has no `created_asset_ids` field, despite the backend model tracking them for rollback

**Discovered**: Prompt 011.

`app/models/asset_import_job.py`'s `AssetImportJob.created_asset_ids`
is a real column the rollback logic reads internally, but
`ImportJobResponse` (`app/schemas/import_export.py`) never exposes it.
A completed, non-preview import can be rolled back by job id (a real
route, `POST /inventory/import/{id}/rollback`), but there is no way
for a caller to see in advance *which* assets a given import job
actually created.

**Frontend behavior**: `ImportDialog` offers the real rollback action
after a completed, non-preview import, but never lists the specific
assets that would be undone — only the job's own row counts
(processed/succeeded/failed/duplicate), which is all the response
schema provides.

## `dependencies`/`impact` topology queries return no parent linkage — a multi-hop graph can't be reconstructed

**Discovered**: Prompt 012.

`GET /inventory/topology?query_kind=dependencies|impact` is real and
backed by a genuine Neo4j traversal (`app/topology/graph.py`'s
`get_dependency_graph`/`get_impact_analysis`), but each Cypher query's
own `RETURN` clause only ever selects `id`, `name`, `asset_type`, and
`length(path) AS distance` — no relationship type, no direction, and
no reference to any intermediate node on the path. The response is a
flat, deduplicated, distance-tagged node list; nothing in it says
which node connects to which beyond the root. `query_kind=neighbors`
is the only kind that returns real edge data (`type(r)`/
`startNode(r).id = a.id AS outgoing`), and it is hard-capped at 1 hop.

**Frontend behavior**: the interactive graph canvas
(`TopologyGraphCanvas`) only ever renders a `neighbors` result (one
root, real 1-hop directed edges). `dependencies`/`impact` are rendered
as a distance-grouped structured list (`TopologyListView`) instead —
never a graph — since drawing a multi-hop edge would mean inventing
one the backend never actually computed.

## `query_kind=neighbors` silently ignores the `depth` query parameter

**Discovered**: Prompt 012.

`GET /inventory/topology` accepts `depth` (validated `1..5` by
FastAPI) for every `query_kind`, but `app/api/topology.py#get_topology`
only ever forwards it to `TopologyService.get_dependency_graph`/
`.get_impact_analysis` — the `neighbors` branch calls
`topology.get_neighbors(asset_id, organization_id=...)` with no depth
argument at all, and `get_neighbors`'s own Cypher (`app/topology/graph.py`)
has no depth/hop-count concept, only a single `-[r]-` (exactly one
edge). A caller can pass any `depth` value alongside
`query_kind=neighbors` and the backend will silently return the same
1-hop result regardless.

**Frontend behavior**: the depth selector is hidden entirely on the
Neighbors tab of `TopologyListView`, with a note explaining depth
doesn't apply there, rather than shown and silently no-op'd.

## No source→target topology path-query endpoint exists

**Discovered**: Prompt 012.

`inventory-service`'s topology router exposes exactly one route
(`GET /inventory/topology`, three `query_kind` values, all rooted at a
single asset). No endpoint accepts two asset ids and returns the path
or relationship chain between them.

**Frontend behavior**: no path/dependency-chain-between-two-assets UI
was built — documented as unavailable rather than approximated with a
client-side graph-traversal algorithm layered on top of repeated
`neighbors` calls, which would silently duplicate logic this backend
is supposed to own.

## `GET /inventory/topology` accepts no filter parameters of any kind

**Discovered**: Prompt 012.

Confirmed by source inspection of `app/api/topology.py#get_topology`'s
full parameter list (`asset_id`, `query_kind`, `depth` only) — no node
type, relationship type, status, health, environment, or site filter
exists on this route.

**Frontend behavior**: `TopologyFilters`' "Show relationship types"
control is a client-side display toggle over the already-loaded,
single-root/1-hop response only, explicitly not presented as a backend
capability.

## `automation-service` has a real asset-linking field with zero route that ever reaches it

**Discovered**: Prompt 012 (refines the Prompt 011 finding that no
Alerting/Automation cross-link exists, which checked only from the
Asset side).

`app/schemas/target.py`'s `AutomationTargetCreateRequest`/
`AutomationTargetResponse` both have a real `inventory_asset_id: UUID
| None` field, and `app/models/automation_target.py` persists it — but
`app/api/__init__.py` never registers a router for targets at all
(confirmed: no `targets.py` exists under `app/api/`, and neither
`AutomationTargetResponse` nor `AutomationTargetCreateRequest` is
referenced anywhere under `app/api/`). The service/model layer fully
supports asset-to-automation-target linking; there is no way to
create, list, or query a target by asset id over HTTP.

**Frontend behavior**: no Topology→Automation or Automation→Topology
cross-link was built, in either direction — reconfirms Prompt 011's
"Automation integration: N/A" finding for Infrastructure, and extends
it with the more precise root cause (a real field, but an entirely
unrouted service) rather than "no relationship exists at all."

## No topology-specific export route exists

**Discovered**: Prompt 012.

`inventory-service` has real `export.py`/`import_.py` routers (Prompt
011), but neither accepts a topology/graph-shaped payload — export is
scoped to asset records, not a graph traversal result.

**Frontend behavior**: no "export this graph" action was built on
Topology. Prompt 011's asset export remains the only real export
capability in this feature area.

## No real-time/push mechanism for topology (or any) data

**Discovered**: Prompt 012 (consistent with every prior prompt this
session — no WebSocket/SSE/push mechanism was found anywhere in this
platform).

**Frontend behavior**: Topology re-queries on every focus change and
via each section's own manual retry action. The backend's own 5-minute
server-side cache (`app/services/topology.py`'s `_CACHE_TTL`) is the
only "freshness" mechanism in play; no client-side polling was added
on top of it.

## No optimistic locking on any Settings mutation, despite every table having a real `version` column

**Discovered**: Prompt 013.

Confirmed by direct inspection of `OrganizationService.update`,
`OrganizationSettingsService.update`, `OrganizationBrandingService.update`,
`OrganizationLicenseService.update`, `OrganizationQuotaService.update`
(`organization-service`), `ProjectService.update`/`.patch`,
`ProjectSettingsService.update` (`project-service`), and
`UserPreferencesService.update`/`UserSettingsService.update`
(`user-management-service`): every one of these mutates the
SQLAlchemy-tracked entity's attributes directly and relies on the
session's own autoflush/commit — none calls
`shared_core.database.repository.BaseRepository.update(entity,
expected_version=...)`, the one method in the shared framework that
actually checks/increments the `version` column every one of these
tables carries via `BaseEntityMixin`/`VersionMixin`. No request schema
in any of these services even exposes a `version` field to the client.
Two concurrent saves to the same resource silently last-write-wins,
with no conflict ever detected.

**Frontend behavior**: no "this changed elsewhere, reload before
saving" UX was built (§22 of Prompt 013 explicitly asks for one) —
there is no signal to detect the conflict with, and fabricating one
client-side (e.g. comparing timestamps) would be exactly the kind of
invented safety net this session has consistently refused to build.
Documented as the largest concurrency gap found this session.

## `PATCH /users/{id}` has no ownership check

**Discovered**: Prompt 013.

`services/user-management-service/app/api/user.py`'s `PATCH`/`PUT
/users/{user_id}` handlers accept `_caller: CurrentUserId` but never
compare it to the `{user_id}` path parameter — any authenticated
caller can in principle edit any other user's `displayName`/
`firstName`/`lastName`/`phoneNumber`/`timezone`/`language`/`locale`/
`status` by id.

**Frontend behavior**: `features/settings/api/preferences-api.ts#patchIdentity`
is called exclusively with `userId` sourced from `useSession()` (the
real, current caller's own id) — never a value a user could type into
a field. The gap is documented, not exploited or fixed client-side (a
frontend can't add a server-side authorization check).

## Three incompatible, client-unverifiable authorization shapes across the Settings backend surface

**Discovered**: Prompt 013.

Confirmed by direct source inspection across the seven services this
prompt integrates: `organization-service`/`project-service` gate
writes on a real *per-resource membership role* looked up from the
database per request (`require_admin`/`require_project_admin`), never
from the JWT; `administration-portal-service` gates writes on a JWT
`roles` **array** claim (`{admin, administrator, platform_admin,
super_admin}`) that this platform's login flow never populates
(`POST /auth/login` issues tokens with no `extra_claims` — the
existing documented Prompt 001 gap, now shown to make every System
mutation 403 unconditionally); `user-management-service`,
`authentication-service`, `integration-hub-service`, and
`notification-center-service`'s user-preference routes require only a
valid JWT, no check at all.

**Frontend behavior**: every edit control gated by the existing coarse
`isAdministrative` role heuristic (`@/permissions/hooks`), documented
explicitly as a UX convenience with no security value — the real 403
each backend returns on a mismatch is always shown as a real error.

## `administration-portal-service`'s own docs claim capabilities that have zero HTTP route

**Discovered**: Prompt 013.

Confirmed by full read of `app/api/admin.py` (16 routes total) and a
grep of every service class against it: `SystemConfigurationService`
(richer runtime config than the plain key/value `PlatformSetting`
`/admin/settings` actually exposes), `OrganizationService` (create/
transition an organization — meaning `POST /admin/tenants` depends on
an organization that must already exist in this service's own
database, with no route in this service to put one there),
`SecuritySettingService`/`SecurityEventService` (the docs' own
"security admin" claim — zero route), `MaintenanceService`/
`AnnouncementService`, `ApiKeyService` (administrative API key
issuance, distinct from `authentication-service`'s own user-facing
one), `AdminSessionService`/`AdminActionService`, and — worth flagging
specifically — `AuditService`: wired as an optional constructor
argument on `TenantService` but `get_tenant_service` in `app/api/deps.py`
never actually passes it, so **no audit row is ever written for any
tenant provision/transition/delete performed through this service's
real, live HTTP API**, despite the class's own docstring describing it
as the platform's audit trail.

**Frontend behavior**: none of the above was built or implied
available. `/admin/tenants*` itself was deliberately not built against
at all (real and RBAC-enforced, but cross-organization operator
tooling dependent on an org that must be seeded out-of-band — see
`../developer-guide/settings.md`).

## `notification-center-service` echoes organization channel config back completely unmasked

**Discovered**: Prompt 013.

`GET/PUT /notifications/channels/{channel}`'s `config` field
(`ChannelConfigResponse`) is stored and returned verbatim
(`app/services/channel.py`'s `set_config` does `dict(config or {})`,
no redaction) — a Slack webhook URL or SMTP password placed in this
dict comes back in plain text on every subsequent read, unlike every
other secret-shaped field in this feature's backend surface (API keys
and integration-hub credentials are both genuinely never re-exposed).

**Frontend behavior**: `NotificationChannelsSection` warns explicitly
in its own UI copy ("Values here are echoed back unmasked by the
backend") rather than silently displaying whatever's stored, since
this field is edited as raw JSON, not enumerable key/value rows (where
Prompt 011's `maskMetadataValue` heuristic could apply row-by-row, as
it does in `ConnectorConfigForm` for `integration-hub-service`'s own
free-form connector `config`).

## `configuration-management-service` is almost entirely unrouted — including a real Ansible/Kubernetes service in the wrong place

**Discovered**: Prompt 013.

Full service-layer implementations exist for environment/variable/
policy/baseline/approval/change-set/TOSCA management, and — notably —
`ConfigurationAnsibleService` (real Ansible inventory-bundle
validation, `app/ansible/validator.py`) and
`ConfigurationKubernetesService` (real Kubernetes manifest/Helm/
Kustomize validation) — the two capabilities a Settings "Integrations"
page would most expect to find. **None of the eleven have a route**:
confirmed by grepping every `*Svc` dependency-injection name in
`app/api/deps.py` against every router file in `app/api/`. This
service's only *routed* purpose is configuration-profile/version/
drift/compliance/GitOps management for managed assets (a
`managed_asset_id` field with no real foreign-key relationship, only
an opaque UUID). `GET /configurations/reports` also has a real, worth-
flagging anomaly: it generates and persists a new report as a side
effect of a GET request (`report.py`'s `generate(...)` call), unlike
the identically-named, properly-idempotent GET/POST report pair in
every other service in this feature's surface.

**Frontend behavior**: nothing was built against this service.
Integrations (§10) is built entirely against `integration-hub-service`'s
own generic connector framework instead — real, but with no dedicated
Ansible/Kubernetes form, since the service that actually validates
those doesn't expose one.

## `OrganizationPreferences`/`ProjectPreferences` remain fully unrouted (reconfirmed from a new angle)

**Discovered**: Prompt 011 (organization-service's own settings
sub-resources); reconfirmed and extended in Prompt 013 from the
Settings-page angle.

Both services' own `docs/033`/`docs/034`-derived test suites
(`test_services_no_rest_surface.py`) explicitly document this as
intentional: `dashboard_layout`/`notification_preferences`/
`ui_preferences` exist as full model/service/repository layers, per
organization and per project, with zero route reaching either.

**Frontend behavior**: this feature's own "Organization"/"Projects"
settings pages never reference either — they're built entirely
against the real, routed `organization_settings`/`project_settings`
sub-resources instead, which are a different (and real) set of fields.

## No route lists a connector's already-assigned credentials, and no credential revoke route exists

**Discovered**: Prompt 013.

`integration-hub-service`'s `CredentialService.list_for_connector`
(`app/services/credential.py`) has zero route reaching it (confirmed
by grep of `app/api/credentials.py`, which only exposes create/get/
rotate). `CredentialStatus.REVOKED` exists as a real enum value, but
no route ever sets a credential to it.

**Frontend behavior**: `ConnectorCredentialSection` can only track a
credential it assigned within the current browser session — it
explicitly tells the user this rather than implying a full credential
history exists. No "revoke credential" action was built, since no
route performs one.

## `user-management-service` enforces no authorization on any route — the most severe finding this session

**Discovered**: Prompt 014.

Confirmed by full source inspection of every file under
`services/user-management-service/app/api/`: `GET /users`,
`POST /users/search`, `GET/PUT/PATCH/DELETE /users/{id}`,
`POST /users/invite` and its siblings, `POST/GET/DELETE
/users/{id}/notes`, and every self-scoped router (profile, preferences,
settings, metadata, tags, addresses, contacts, avatar) all depend only
on `CurrentUserId` (`app/api/deps.py:104-124`) — decode the JWT, return
the subject, nothing else. Zero role/permission dependency exists
anywhere in this service (confirmed by grep of the whole `app/` tree
for role/permission-shaped identifiers, matching only an unrelated
`session_scope(` false positive). This extends and generalizes the
earlier Prompt 013 finding that `PATCH /users/{id}` has no ownership
check — the entire service has no authorization concept at all, not
just that one route.

**Frontend behavior**: the Users administration page's primary nav
entry is restricted to `super_admin`/`organization_admin` via
`lib/route-registry.ts`'s `roles` field — real enforcement inside
`PrimaryNavigation`, but only controlling link visibility, not the
underlying API. A permanent, on-page `Alert` banner states this
plainly (not just a code comment), since the risk of a false sense of
security here is unusually high.

## Four services define four separate, unsynchronized role vocabularies

**Discovered**: Prompt 014.

The frontend's own JWT `role` claim (6 values), `organization-service`'s
`MemberRole` (`member`/`admin`/`owner`, 3-tier ranked), `project-service`'s
`project_roles` table (8 seeded system codes, ranked 10–100), and
`rbac-service`'s own role catalog (10 seeded system roles) are four
independent systems — none references another, no service consults
another service's role table when making an authorization decision.

**Frontend behavior**: never conflated — every type and component that
touches a role concept names explicitly which of the four it means
(`OrganizationMemberRoleValue`, `ProjectRoleCodeValue`, `RbacRole`, the
existing platform `Role`). See the developer guide's comparison table.

## `rbac-service`'s role/permission-assignment routes are real, and confirmed to have zero live effect

**Discovered**: Prompt 014.

`POST/DELETE /users/{id}/roles` genuinely persists/removes a role-
assignment row in `rbac-service`'s own tables. Confirmed by grepping
every other service in the monorepo for any client call into
`rbac-service`: none exists. `services/api-gateway-service/app/services/auth.py`,
`services/organization-service/app/organizations/membership.py`, and
every other service's own authorization guard explicitly document
choosing local, self-contained enforcement over calling `rbac-service`.
The only place `rbac-service` enforces anything is against its own
mutating routes, via its own `AuthorizationEvaluator` querying its own
tables — a real, self-consistent system nothing outside this one
service ever queries. `RoleAssignmentService.list_for_user()` is also
unrouted — there is no way to view what's already assigned to a user
either.

**Frontend behavior**: `RoleAssignmentSection` builds the real
workflow Prompt 014 asks for (§20), but with a permanent, unmissable
warning (not a tooltip or docstring) that assigning a role here has no
live effect on the user's actual access anywhere else in AI-IOS today.

## No route lists an organization's members, anywhere

**Discovered**: Prompt 014.

`organization-service`'s `OrganizationMemberService.list_for_org()`
and `.remove()` (`app/services/member.py:50-60`) are both fully
implemented — neither has a route. No `app/api/member.py` file exists
in this service at all. `.add()` is only ever called internally, once,
from `POST /organizations` (making the creator the owner) — never
exposed as a general "add a member directly" endpoint (membership is
otherwise only created via invitation accept).

**Frontend behavior**: no "organization members" list/management UI
was built anywhere — not in Administration, not in Settings. A user's
organization membership cannot be shown on their detail page for this
reason (see the "Access & Membership" gap below).

## No route reverses project membership from a user's perspective, and no team-membership endpoint exists at all

**Discovered**: Prompt 014.

`GET /projects/{id}/members` only works in the forward direction
(given a project, list its members) — no route in `project-service`
answers "which projects does user X belong to." Separately,
`organization-service` has no team-members endpoint of any kind
(confirmed: no `app/api/*.py` file exposes team membership) — the only
place it's even recorded is `OrganizationMember.team_id`, itself
unreachable per the organization-members finding above.

**Frontend behavior**: `UserDetailView`'s "Access & Membership" section
states this gap explicitly, citing all four services checked, rather
than showing a partial or misleading membership list.

## `project-service` member/role routes have no self-lockout protection, and `role_code: "owner"` is a hidden ownership transfer

**Discovered**: Prompt 014.

`ProjectMemberService.remove`/`.update_role` (`app/services/member.py`)
have no last-owner, last-admin, or self-removal guard of any kind — a
caller can remove a project's only Owner, or remove themselves, and
the backend will comply. Separately, `PUT /projects/{id}/members/{userId}/roles`
with `role_code: "owner"` is special-cased server-side
(`app/api/project_member.py:111-143`) into a full ownership transfer —
the prior `project.owner_id` holder is automatically demoted to
Administrator — not a plain role edit.

**Frontend behavior**: `ProjectMembersSection` (Settings → Projects)
blocks removing/demoting a project's sole Owner client-side, with a
message stating this is the frontend's own guard since the backend has
none. Setting a role to `"owner"` shows a distinct "Transfer project
ownership?" confirmation, never a plain role-change dropdown.

## `GET /users` and `POST /users/search` discard their own computed pagination metadata; two request fields are silently dead

**Discovered**: Prompt 014.

Both routes compute real `PaginationMetadata` (`total`/`page`/
`page_size`/`has_next`/`has_previous`) via the shared framework
internally, then discard everything except the bare item array before
responding (confirmed: `app/api/user.py`'s route handlers only ever
emit `data=[...]`, never `meta`). Separately, `UserSearchRequest`'s
`department`/`tags` fields are accepted by the schema but never
referenced anywhere in the route handler — confirmed dead on the wire.

**Frontend behavior**: `UserTable` renders a real Previous/Next pager,
never a page-count picker (no total exists to build one against).
`UserFilters` exposes only `query`/`status`, the two fields that
actually filter anything.

## Two separate invitation systems exist; neither supports listing, and only one supports resending

**Discovered**: Prompt 014.

`user-management-service`'s `/users/invite` (email/message only, no
role/team) has a real, working `/resend` but no list and no revoke.
`organization-service`'s `/organizations/{id}/invite` (email/role/
department/team, admin-enforced) has a fully-implemented but unrouted
`InvitationService.resend()` and `UserInvitationRepository.list_pending()`,
and no revoke/cancel method exists in its service layer at all
(`InvitationStatus.REVOKED` is a defined enum value with zero code
path that ever assigns it).

**Frontend behavior**: built against `organization-service`'s system
(role-carrying, admin-enforced — the more appropriate one for an
access-administration page). `InvitationsPage` is a send-only form
with a permanent banner explaining nothing can be listed afterward on
either system — not a placeholder for a future list.

## `DELETE /users/{id}` is a soft delete via `is_active`, not a `status` transition to `"deleted"`

**Discovered**: Prompt 014.

Confirmed: the route calls `BaseRepository.delete` → `mark_deleted`,
which sets `deleted_at`/`deleted_by`/`is_active=False` — a separate
mechanism from `UserService.patch`'s real `status`-transition state
machine (`transition_status`, checked against `_VALID_TRANSITIONS`).
The user then 404s from every other route in this service (list/
search/get all filter `is_active=True`), but a direct row inspection
would still show whatever `status` value it had before deletion.

**Frontend behavior**: `usersApi.remove`'s own docstring and
`UserStatusActions`' delete confirmation both describe this accurately
— a removal, not a status change — rather than implying the two are
the same operation.

## No platform-wide audit log exists; six services have a real, populated audit table with zero route reaching it

**Discovered**: Prompt 015.

Confirmed by full source inspection across ten services. Only three
expose a real, general-purpose, `AuditAction`-typed audit route:
`compliance-service` (`GET /compliance/audit`+`/summary`),
`integration-hub-service` (`GET /integrations/audit`),
`notification-center-service` (`GET /notifications/audit`+`/summary`).
Six more have a real, actively-written audit table with no route at
all: `authentication-service` (`AuthenticationAuditEntry`, written on
register/login/MFA/logout events), `rbac-service`
(`AuthorizationAuditEntry`, written only for
`/authorization/evaluate` decisions — role/permission/policy CRUD
writes no audit row at all), `administration-portal-service`
(`SystemAuditRepository`, real working `list_recent`/`list_for_entity`
methods, unrouted; only `TENANT_OPERATION` is ever referenced in code
and even that path is dead), `automation-service`, `inventory-service`
(both have real service/repository-layer `list_for_*` methods,
unrouted), and `observability-platform-service` (not even wired into
`deps.py` for writing, let alone reading). Separately,
`alerting-service`'s `GET /alerts/{id}/history` and
`reporting-service`'s `GET /reports/history` are real but narrower,
single-entity-scoped changelogs — not general audit trails, and this
feature never treats them as one.

None of the three real sources consumes events from any other
service (`compliance-service`'s `app/clients/__init__.py` is empty, no
message-queue consumer exists anywhere in any of the three) — each can
only ever audit actions taken through its own API.

**Frontend behavior**: Prompt 015 (`docs/frontend/developer-guide/audit-activity.md`)
builds a source-selector over the three real routes, never merged into
one list. The six unrouted tables and two narrower changelog routes
are documented, not worked around — there is nothing to build against.

## Two of the three real audit routes require no authentication at all

**Discovered**: Prompt 015.

`integration-hub-service`'s `GET /integrations/audit`
(`app/api/analytics.py`) and `notification-center-service`'s `GET
/notifications/audit`+`/audit/summary` (`app/api/analytics.py`) do not
declare `CurrentUserId` (or any caller-identity dependency) as a route
parameter — FastAPI enforces no authentication on them, not merely no
authorization. `compliance-service`'s `GET /compliance/audit` requires
a valid JWT but checks no role or permission beyond that (consistent
with, but more severe than, Prompt 014's finding that
`user-management-service` checks no authorization while still
requiring a valid token).

**Frontend behavior**: a permanent, per-source `Alert` on the Activity
page names exactly which gap applies to the source currently selected
— never a single generic warning implying all three are equally
exposed. The feature's own nav entry is restricted to
`super_admin`/`organization_admin`, stated plainly as a frontend
convenience that does not close this gap.

## `compliance-service`'s audit trail is genuinely immutable; the other two real sources were not confirmed either way

**Discovered**: Prompt 015.

`AuditRepository` (`compliance-service`) has no update or delete
method at all, confirmed by direct source inspection — a real,
enforced immutability at the repository layer, not a documentation
claim. `AuditService.record_failure()` exists but is never called by
any caller in the service (confirmed by grep) — failed/refused actions
therefore produce zero audit rows today, only successes are audited.
No retention period, archive status, or historical-range limit is
exposed by any of the three real audit routes; a separate,
unrelated *evidence* retention concept exists in `compliance-service`
and is never conflated with the audit trail.

**Frontend behavior**: the developer guide and RFI state the
immutability finding scoped specifically to `compliance-service`'s own
audit trail, never generalized to `integrations`/`notifications` or to
"the platform" — per the prompt's own explicit prohibition on claiming
retention guarantees or immutable storage without backend
confirmation.

## No route on any of the three real audit services returns a single event by its own id

**Discovered**: Prompt 015.

Confirmed across all three: `compliance-service`, `integration-hub-service`,
and `notification-center-service` each expose only a list route for
audit entries — none has a `GET /.../audit/{id}`-shaped route.

**Frontend behavior**: Event Detail (`EventDetailDrawer`) is built
entirely from the row already present in the loaded list/timeline,
rendered as an in-page drawer rather than the prompt's own suggested
`/audit/events/[id]` route — there is nothing such a route could fetch
on a fresh page load.

## Compliance's audit-report export pipeline has no relationship to Prompt 008's Reporting feature

**Discovered**: Prompt 015.

`POST /compliance/reports {kind:"audit"}` → `GET
/compliance/reports/{id}/download` is a real, synchronous (no job
polling — the POST response already carries a terminal `status`)
report-generation pipeline, but it belongs entirely to
`compliance-service`'s own `ReportService`/`ComplianceReport` model —
unrelated to `reporting-service`'s `Report`/`ReportExecution` models
that back Prompt 008's Reporting feature, despite both being called
"reports." The exported row is also narrower than the live
`/compliance/audit` response — `_audit()`
(`compliance-service/app/services/reporting.py`) confirmed to omit
`id`, `entity_id`, `actor_type`, `changes`, and `context`.

**Correction (Prompt 016)**: this entry originally also claimed
`integration-hub-service` and `notification-center-service` have no
report-generation or export route of any kind. Prompt 016's own
research into `notification-center-service` found this incorrect for
that service: a real `POST/GET /notifications/reports`,
`GET /notifications/reports/{id}`, `GET
/notifications/reports/{id}/download` pipeline exists
(`app/api/analytics.py`, backed by a real `NotificationReport` model)
— either added after Prompt 015 shipped or simply missed during that
prompt's own research pass. `integration-hub-service` was not
re-checked during Prompt 016 and this entry makes no claim about it
either way. Prompt 015's Activity page was not retroactively updated
to add a `notifications`-source export control — that remains a
candidate for a small, separate follow-up, not done as part of this
correction (see `docs/frontend/developer-guide/notifications.md`).

**Frontend behavior**: export is offered only for the `compliance`
source, calling this pipeline directly rather than routing through
Reporting (the prompt's own §31 suggests an "Audit → Reporting"
integration; no such technical relationship exists in V1 to build it
against), with an inline note that the exported file has fewer columns
than the on-screen table.

## No confirmed identity-space link between an audit event's actor and `user-management-service`'s own user records

**Discovered**: Prompt 015.

Every audit entry's `actor_id` across all three real sources is
`str(caller)` — the JWT `sub` claim of whoever called the API, i.e.
the same identity `authentication-service` issues at login.
`user-management-service` maintains its own, separately-keyed `users`
table (`services/user-management-service/app/models/user.py`), and
`authentication-service` never calls `user-management-service` at
registration or anywhere else (confirmed absent by grep) — there is no
event that would keep the two id spaces in sync, and no route on
either service confirms they are.

**Frontend behavior**: no "Event Actor → User Detail" link is built
(Prompt 015 §32's own request) — resolving an unconfirmed id match
risks silently pointing at the wrong account, which is worse than
showing no link at all. Documented as a confirmed impossibility rather
than an unbuilt convenience, so a future prompt doesn't re-attempt it
without first confirming the identity spaces are unified.

## `notification-center-service`'s notification list/detail/read/acknowledge routes require no authentication at all

**Discovered**: Prompt 016.

`GET /notifications`, `GET /notifications/{id}`,
`POST /notifications/{id}/read`, `POST /notifications/{id}/acknowledge`,
and `GET /notifications/{id}/deliveries`
(`services/notification-center-service/app/api/notifications.py`) do
not declare `CurrentUserId` (or any caller-identity dependency) as a
route parameter — FastAPI enforces no authentication on them at all.
More severe than every prior finding on this axis (Prompt 014's
`user-management-service`, Prompt 015's two unauthenticated audit
routes on this same service): here the unauthenticated routes include
state-mutating ones, not only reads. `organization_id` and `user_id`
are both plain, caller-supplied query parameters on `GET /notifications`,
never derived from or cross-checked against the JWT.

**Frontend behavior**: a permanent, high-severity (`danger`-tone, not
`warning`) `Alert` on the Notification Center page states this
plainly. The feature still sends the real, currently-signed-in user's
own id (`useSession().userId`) as `user_id` — the only honest choice
available — documented everywhere as a convenience, never a fix.

## No unread-count route exists; a real repository method for it is simply never called

**Discovered**: Prompt 016.

`NotificationRepository.count_unread(organization_id, user_id) -> int`
(`app/repositories/notification.py`) is a real, working method — a
genuine `WHERE read_at IS NULL` count, not a placeholder — but is
never invoked from any service class, route, or test in the entire
service (confirmed by grep). No `/notifications/unread-count` route
exists, and no list response carries a total/count field (the
`SuccessResponse` envelope has none).

**Frontend behavior**: the notification bell never renders a number —
only a plain indicator dot derived from whether any item in a small,
bounded, already-fetched page (the same data shown in the popover) has
`readAt === null`, per §10's own explicit prohibition on computing a
total from paginated client data.

## `Notification` has no structured deep-link field to another service's entity

**Discovered**: Prompt 016.

Confirmed absent on both `Notification` and `NotificationAnnouncement`:
no `entity_type`/`entity_id` pair, no typed foreign key to an alert,
automation execution, report, or asset. Only free-text
`source_service`/`source_event_type`/`correlation_id` hints and an
unstructured `notification_metadata`/`tags` JSON blob with no
documented schema (`app/models/notification.py`).

**Frontend behavior**: §16's "Notification → Alert detail / Automation
execution / Report / Asset / Audit event" deep links are not built.
Source information is shown as plain text; clicking a notification
only ever opens its own real detail page.

## "Mark as unread" and "mark all read" are both confirmed absent

**Discovered**: Prompt 016.

No `mark_unread` method exists anywhere in `NotificationService`
(confirmed by grep), and no bulk-read route exists on
`app/api/notifications.py` — only the real, per-id `POST /{id}/read`.

**Frontend behavior**: neither is offered. "Mark all read" was
deliberately not composed from N individual `/read` calls — a
fragile pseudo-bulk operation would misrepresent a batch capability
the backend doesn't actually support as a single atomic one.

## `alerting-service` never creates a `notification-center-service` notification — "Alert → Notification" is not real

**Discovered**: Prompt 016.

Grepping `alerting-service`, `automation-service`, and
`reporting-service` for any call into `notification-center-service`
(by name or its port) returns zero matches. `alerting-service`
dispatches through its own, entirely separate
`AlertNotificationService`/`AlertNotification` model
(`services/alerting-service/app/notifications/alert_notifications.py`),
never `notification-center-service`'s API. `notification-center-service`
itself only publishes its own domain events for other services to
optionally consume — it consumes nothing inbound (no message-queue
consumer registered anywhere in `app/core/factory.py`).

**Frontend behavior**: §29's "Alert → Notification" integration is not
built — it would misrepresent a relationship that doesn't exist on
this backend. Documented as a confirmed impossibility, not an
oversight, so a future prompt doesn't re-attempt it without a real
backend change first.

## No real-time or push delivery mechanism exists for notifications

**Discovered**: Prompt 016.

Grepped the entire `notification-center-service` tree for
WebSocket/SSE/push route registrations — none exist. The service
publishes domain events to RabbitMQ for inter-service consumption
only; there is no client-facing channel a browser could open.

**Frontend behavior**: the notification bell uses a real, working
TanStack Query `refetchInterval` (60s) against the real list
endpoint — genuine periodic polling, never a fabricated push
mechanism, per §11's own instruction.

## No free-text search parameter exists on almost any resource's list route — reconfirmed platform-wide

**Discovered**: Prompt 003 (no unified search endpoint). **Extended,
resource by resource**: Prompt 017.

Checked every candidate resource type's real list route: only
`inventory-service`'s `GET /inventory/search` (`query`) and
`user-management-service`'s `POST /users/search` (`query`) accept a
free-text parameter. `alerting-service`'s `GET /alerts`,
`automation-service`'s `GET /automation/jobs`, `reporting-service`'s
`GET /reports`, and `ai-assistant-service`'s `GET /ai/conversations`
all support only `organization_id` plus a few exact-match filters — no
`query`/`q`/`search` parameter exists on any of them (each already
independently confirmed absent by the prompt that originally built
each one; re-confirmed here specifically for this prompt's own
composition strategy). Audit events and notifications were already
confirmed to have no free-text field either (Prompts 015/016).

**Frontend behavior**: Assets/Users get real, debounced, server-side
search. Alerts/Automations/Reports/AI Conversations get client-side
filtering over an already-fetched, organization-scoped list, fetched
once per palette session rather than per keystroke — the same pattern
`features/reporting/pages/reports-list-page.tsx` already established
for its own search box. Audit events and notifications are excluded
from live resource search entirely; both remain reachable only as
navigation commands to their own real pages.

## The command palette showed every implemented route regardless of the session's role — a real, pre-existing gap, now fixed

**Discovered**: Prompt 003 (built this way). **Fixed**: Prompt 017.

`components/navigation/command-palette.tsx`'s `NAVIGATION_COMMANDS`
list was never filtered by role, unlike `PrimaryNavigation`'s sidebar,
which has applied `route.roles === null || (role !== null &&
route.roles.includes(role))` since Prompt 003. This meant a
role-restricted route (e.g. Users, admin-only since Prompt 014) was
reachable through Ctrl+K by any session, even one the sidebar itself
hides it from.

**Frontend behavior**: the palette now applies the identical role
check before listing a route. This is a frontend-only tightening, not
a fix for any one backend service's own authorization gap — several of
those (`user-management-service` chief among them) remain confirmed to
enforce no server-side check at all, documented in their own separate
entries above.
