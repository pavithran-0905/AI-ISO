# Audit & Activity

Built in Prompt 015, against three real, separate, never-merged audit
trails: `compliance-service`, `integration-hub-service`,
`notification-center-service`. This is the session's clearest instance
yet of a prompt asking for a single unified concept ("audit log") that
does not exist in the backend at all — **there is no platform-wide
audit log anywhere in AI-IOS.** See
`docs/frontend/rfi/audit-activity.md` for the implemented-vs-planned
split and `docs/frontend/backend-v1-integration-limitations.md` for
the full gap list with citations.

## Ten services touched, three real routes, six dead tables

Confirmed by full source inspection, service by service:

| Service | Real audit table? | Real general-purpose route? |
|---|---|---|
| `compliance-service` | Yes | **Yes** — `GET /compliance/audit`(+`/summary`) |
| `integration-hub-service` | Yes | **Yes** — `GET /integrations/audit` |
| `notification-center-service` | Yes | **Yes** — `GET /notifications/audit`(+`/summary`) |
| `authentication-service` | Yes, actively written | No route reads it back |
| `rbac-service` | Yes, but only for `/authorization/evaluate` decisions | No route reads it back |
| `administration-portal-service` | Yes (`SystemAuditRepository`) | No route reads it back |
| `automation-service` | Yes | No route reads it back |
| `inventory-service` | Yes | No route reads it back |
| `observability-platform-service` | Yes, not even wired for writes | No route reads it back |

Two more services have something *audit-adjacent* that is explicitly
**not** a general audit trail, and this feature does not treat it as
one: `alerting-service`'s `GET /alerts/{id}/history` is one alert's own
status-transition changelog; `reporting-service`'s `GET
/reports/history` is a distinct `ReportHistory` model, unrelated to
that same service's own write-only `ReportAudit`.

This feature's entire architecture follows from that table: a
**source-selector** over the three real routes (`features/audit/pages/audit-activity-page.tsx`,
using `components/navigation/tabs.tsx`), never a client-side merge into
one combined list — merging would mean fabricating a single "page N of
M" that doesn't correspond to any real backend query, which this
session has consistently refused to do.

## Why Event Detail is a drawer, not `/audit/events/[id]`

The prompt's own recommended IA (§8) asks for a route at
`/audit/events/[id]`. **No route on any of the three services returns
a single event by its own id** — confirmed across all three research
passes. `EventDetailDrawer` (`features/audit/components/event-detail-drawer.tsx`)
is built entirely from the row already loaded in the list/timeline,
never a second fetch. This also means a deep link to one event's
detail cannot exist: there is nothing to fetch if the list hasn't
already been loaded client-side.

The same reasoning collapses the IA's "Activity"/"Audit Events" into
one page (`/audit/activity`): §21's timeline is explicitly "an
alternate representation" of the same data the table shows, so table
and timeline are one dataset behind `AuditViewToggle`, never two
separate fetches (§22).

## API architecture

```
Audit Page → Audit Hooks (features/audit/hooks/use-audit.ts)
           → Audit API module (features/audit/api/audit-api.ts)
           → apiClient (@/api/client)
           → Backend V1
```

`audit-api.ts` is one module covering all three sources (rather than
one module per service, the pattern used elsewhere in this codebase)
because the three response shapes are near-identical
(`AuditEntryResponse`/`AuditResponse`) and sharing a single `toEvent()`
adapter keeps the one real structural difference — `compliance`'s
response has no `context` field at all, while `integrations`/
`notifications`' does — visible in one place instead of duplicated
across three files.

## Event model

`AuditEvent` (`features/audit/types/index.ts`) is the unified frontend
shape. Every field mirrors a real backend field; `context: null` for a
`compliance` event is not "loading" or "unavailable" — it's a
confirmed absence in that service's own response schema (the
underlying model has a `context` column; the route's response schema
simply omits it).

`AuditEventSearchParams` documents, field by field, that the three
sources' filters are genuinely different:

- **`compliance`**: `entityType`, `entityId`, `actorId`, `days` (a
  *relative* window from now, default 90, max 3650 — there is no
  absolute start/end date pair on this route). No `action` filter,
  despite `AuditAction` being a rich 20-value enum server-side.
- **`integrations`**: `organizationId` only. The service layer
  supports `entity`/`actor`/`action` filters internally; the route
  never wires them into query parameters. Sending them would be
  silently ignored, so this module doesn't send them.
- **`notifications`**: the richest — `action` (real enum), `entityId`,
  `actorId`.

None of the three exposes a status/`succeeded` filter, a client-controlled
sort field (all three are fixed `occurred_at desc`), or search beyond
exact-match field filters — there is no full-text search on any of
these routes, so no search box is offered.

## Pagination

All three routes are `limit`/`offset`, none returns a total count.
`AuditEventSearchResult.hasMore` is the same `items.length === limit`
heuristic used throughout this codebase (`UserTable`,
`ReportsListPage`), and `AuditEventTable` renders a real Previous/Next
pager, never a page-count picker that would have to guess.

## Permissions — the session's most severe finding yet

`compliance-service`'s `/audit` route requires a valid JWT and nothing
else (no role/permission check anywhere in the service, confirmed by
grep). `integration-hub-service`'s `/audit` and
`notification-center-service`'s `/audit`+`/audit/summary` are worse:
**neither declares `CurrentUserId` as a route parameter at all**,
meaning FastAPI enforces zero authentication on them — not merely zero
authorization. Compare this to Prompt 014's finding
(`user-management-service` has no *authorization* check but does
require a valid token); this is one level more severe.

**Frontend behavior**: the Activity page carries a permanent, per-source
`Alert` (`SOURCE_AUTH_NOTES` in `audit-activity-page.tsx`) naming
exactly which gap applies to the currently-selected source, not a
single generic warning. The nav entry (`id: "audit"` in
`lib/route-registry.ts`) is restricted to `super_admin`/
`organization_admin`, same convention as Users — a frontend
convenience only, stated as such, since the backend remains the sole
authority and two of the three routes don't even check that.

## Sensitive-data handling

`changes`/`context` are opaque `Record<string, unknown>` bags — none
of the three services' schemas declare what keys can appear.
`features/audit/lib/mask-sensitive.ts` masks any key matching
`/password|token|secret|api[_-]?key|private[_-]?key|credential/i`
recursively, replacing the value with a fixed placeholder before the
JSON is ever rendered. This errs toward masking more than a
backend-confirmed allowlist would, since no such allowlist exists to
consult. Nothing in this feature logs an audit payload to the browser
console.

## Immutability, retention, and export

`compliance-service`'s audit trail is confirmed genuinely immutable —
`AuditRepository` has no update/delete method at all, and
`AuditService.record_failure()` (present, but never called by any
caller — meaning failed/refused actions produce zero audit rows today
on this service) is the only other write path. **This confirmation is
specific to `compliance-service` alone** — the other two sources were
not confirmed immutable and this feature never states or implies they
are, and no source's audit trail exposes a retention period, archive
status, or historical-range guarantee of any kind. No retention
concept exists for the audit trail at all (compliance-service does
have a retention concept, but it's for *evidence*, an unrelated model,
and this feature never conflates the two).

Export (`ExportAuditControl`) is real but `compliance` only:
`POST /compliance/reports {kind:"audit"}` → `GET
/compliance/reports/{id}/download` (CSV/Markdown/JSON), confirmed
synchronous — the POST itself returns the finished, terminal-status
report, never a job handle to poll. This is compliance-service's own,
separate report-generation pipeline; it shares nothing with Prompt
008's `reporting-service` beyond the word "report." Despite the
prompt's own §31 suggesting an "Audit → Reporting" integration, no such
technical relationship exists in V1, so this feature does not link to
`/reporting` for export. The exported row is narrower than the live
table (`_audit()` in `reporting.py` confirmed: no `id`, `entity_id`,
`actor_type`, `changes`, or `context` — only `occurred_at, action,
entity_type, entity_reference, actor, summary, succeeded`), noted
inline on the export control itself.

## Cross-module integration — confirmed unavailable in every direction

The prompt's §32-35 ask for User Management, Automation, Infrastructure,
and AI integration. All four were researched and found unbuildable
against the real backend this feature actually has:

- **User Management**: an event's `actor_id` is the raw JWT `sub`
  claim recorded by `str(caller)` at write time — the same identity
  used platform-wide for authentication. `user-management-service`'s
  own `User.id` is a separate primary key with **no confirmed shared
  identity space**: `authentication-service` never calls
  `user-management-service` at registration or anywhere else
  (confirmed absent by grep), so there is no linking event. Building
  an "Event Actor → User Detail" link on an unconfirmed id match risks
  silently pointing at the wrong account — worse than no link at all.
- **Automation / Infrastructure**: none of the three real sources
  records actions taken through `automation-service` or
  `inventory-service` — those services' own audit tables are the
  unrouted ones in the table above. The `entity_type` values that
  *do* appear (compliance's frameworks/controls/findings/etc.,
  integration-hub's connectors/credentials, notification-center's
  templates/broadcasts) have no frontend detail page to link to in
  this codebase today (`integrations` and `notifications-admin` are
  both still `planned()` in the route registry; compliance's own full
  GRC surface is deliberately out of this prompt's own IA).
- **AI**: no route on any of the three services offers a contextual
  analysis hook of any kind — nothing to wire "Analyze with AI" to.

None of these four are built. This is stated here and in the RFI
rather than left silent, since a missing feature and a confirmed
impossibility read very differently to whoever plans the next prompt.

## Performance

Every list is server-paginated (`limit`/`offset`), every filter is
server-side, and switching Table/Timeline never re-fetches (§22/§48).
No client-side aggregation of a full dataset occurs anywhere in this
feature.

## A shared `Drawer` bug this prompt found and fixed (not audit-specific)

E2E testing this feature's Event Detail drawer surfaced a real,
pre-existing bug in `components/overlays/drawer.tsx`, used by four
other features (`role-detail-drawer.tsx`, `topology-detail-panel.tsx`,
`group-members-drawer.tsx`, this feature's own `event-detail-drawer.tsx`):
the closed `<dialog>` relied on the browser's own `dialog:not([open])
{ display: none }` user-agent rule, but the component's className also
carried an unconditional Tailwind `flex` utility. Author-origin CSS
(any class from a stylesheet, `@layer`ed or not) always wins over
user-agent-origin CSS of the same importance regardless of selector
specificity — so the closed drawer stayed laid out and full-height/
full-width, invisibly intercepting clicks on whatever sat underneath
its fixed right-hand region. Only reproducible against real Chromium;
jsdom's unit tests never exercise real CSS cascade/layout, so this
never surfaced in this session's existing `drawer.test.tsx`. Fixed by
switching to the standard `hidden open:flex` pattern (default closed
via an explicit author rule, `flex` only once `[open]` is actually
set) — confirmed via the full existing E2E suite (63/63 passed
afterward) that no other feature depended on the old, broken behavior.
