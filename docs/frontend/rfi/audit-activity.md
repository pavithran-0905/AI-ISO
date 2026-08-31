# Audit & Activity

Per Prompt 015 §52, this honestly separates **IMPLEMENTED** from
**PLANNED**/**UNAVAILABLE** for the Enterprise Audit & Activity
Experience, built against three real, separate audit trails with no
platform-wide equivalent. See `../rfi/README.md` and
`../developer-guide/audit-activity.md` for the full technical
reasoning.

**This document does not claim regulatory compliance, certification,
platform-wide immutable storage, or a retention guarantee.** Where
immutability is stated below, it is scoped to one specific service's
own audit trail, confirmed by direct repository-layer inspection — it
is never generalized to the other two sources or to "the platform."

## Enterprise audit visibility — PARTIALLY IMPLEMENTED (three real, never-merged sources)

Real, server-paginated, server-filtered audit trails against
`compliance-service`, `integration-hub-service`, and
`notification-center-service` — the only three services in AI-IOS with
a general-purpose, `AuditAction`-typed audit route. **There is no
platform-wide audit log**: six other services record audit-shaped data
with zero route to read it back, and none of the three real sources
consumes events from any other service. A source-selector presents all
three through one shared table/timeline UI, never silently combined
into one list or one page count.

## Operational activity tracking — IMPLEMENTED (Activity page, real filters per source)

Search-by-field (not full-text — none of the three routes offers
full-text search), a real date-range preset for `compliance` (relative
windows only, no absolute date range exists), a real action filter for
`notifications` (populated only from that service's own confirmed
enum), and real offset/limit pagination for all three. `integrations`
has no filter beyond its fixed organization scope, shown as a plain
note rather than disabled-looking controls pretending to work.

## Permission-aware access — IMPLEMENTED (mechanism; the session's most severe finding to date)

`compliance-service`'s audit route requires a valid session token and
nothing else. **`integration-hub-service`'s and
`notification-center-service`'s audit routes require no authentication
at all** — confirmed absent, not merely unenforced (neither route even
declares a caller-identity parameter). A permanent, per-source
on-page warning states exactly which gap applies to the source
currently being viewed. This page's own nav restriction (administrator
role) is a frontend convenience; the backend remains the sole
authority, and two of the three sources don't check it at all.

## Event investigation — IMPLEMENTED (drawer, not a route)

Event Detail opens as an in-page drawer built entirely from the
already-loaded row — actor, action, resource, timestamp, status, and
masked metadata. Not built as the prompt's own suggested
`/audit/events/[id]` route: **no service exposes a single-event-by-id
GET**, confirmed across all three, so there is nothing such a route
could fetch on its own.

## Resource traceability — UNAVAILABLE (confirmed, not merely unbuilt)

No cross-module link from an audit event to a User, Automation
execution, or Infrastructure asset exists. An event's `actor_id` is
the authenticating identity's raw id, with **no confirmed shared id
space** with `user-management-service`'s own separately-keyed user
records (that service is never called during registration or
anywhere else, confirmed by grep) — a link here would risk silently
resolving to the wrong account. None of the three real sources records
an Automation or Infrastructure action at all (those services' own
audit tables are among the six unrouted ones), so there is no
`entity_type` to link from in either direction.

## Export — PARTIALLY IMPLEMENTED (compliance only, its own separate pipeline)

`compliance-service` has a real, synchronous report-generation route
(`kind:"audit"`) producing a downloadable CSV/Markdown/JSON — offered
here with a note that its rows are narrower than the live table.
`integrations` and `notifications` have no export or report-generation
route of any kind, so none is offered for those sources. This
pipeline is compliance-service's own; despite sharing the word
"report," it has no technical relationship to Prompt 008's Reporting
feature, so this experience does not route audit export through
Reporting.

## Accessibility — IMPLEMENTED (foundation)

Built on already-accessible primitives (`Tabs`, `Drawer`, `Alert`, the
same responsive table/card pattern used since Infrastructure). The
timeline is a real `<ol>`/`<li>` structure — itself the accessible
structured equivalent the prompt requires, not a purely visual layout
needing a separate hidden fallback.

## Scalability — IMPLEMENTED (real pagination, honestly incomplete)

Server-side paging is real for every source; none of the three
backends returns a total count, so a real Previous/Next pager was
built rather than a page-count picker that would have to guess.

## Security UX — IMPLEMENTED

No secret-shaped field is ever displayed unmasked: `changes`/`context`
are masked by key name before rendering (password/token/secret/API
key/private key/credential), erring toward over-masking since no
backend-confirmed field allowlist exists to narrow it. Nothing in this
feature logs an audit payload to the browser console.

## Immutability — CONFIRMED for compliance-service's own audit trail only

`compliance-service`'s `AuditRepository` has no update or delete
method at all, confirmed by direct source inspection — its audit rows
cannot be altered through this service's own code path. This is
**not** stated or implied for `integrations`/`notifications`, and no
retention period, archive status, or guaranteed historical range is
claimed for any of the three sources — none is exposed by any of them.

See `../backend-v1-integration-limitations.md` for the full,
cross-prompt list with source citations.
