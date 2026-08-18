# Alerting

The Enterprise Alerting & Incident Experience built in Prompt 007, on
top of the Dashboard's `organization/` context (Prompt 005) and the
application shell (Prompt 003). See `docs/frontend/rfi/alerting.md`
for the implemented-vs-planned split and
`docs/frontend/backend-v1-integration-limitations.md` for every gap
discovered building this.

## Feature structure

```
features/alerting/
├── api/            alerts-api.ts, alert-statistics-api.ts, maintenance-windows-api.ts
├── hooks/          one useQuery wrapper per read, one useMutation wrapper per action
├── components/     AlertingSubNav, AlertSummary, AlertFilters, AlertTable,
│                    AlertDetailView, AlertLifecycleTimeline, AlertAcknowledgementsList,
│                    AlertCorrelationsList, AlertNotificationsList, AlertActions,
│                    MaintenanceWindowsList
├── types/          response types mirroring the real V1 schemas
├── lib/            severity.ts (tone/rank/label maps), format-duration.ts
└── pages/          alerting-overview-page.tsx, alerting-alerts-page.tsx,
                     alerting-alert-detail-page.tsx
```

Follows §27's flow: `Page → Hook → API module → apiClient → real V1 endpoint`.

## Consolidated from `features/dashboard`

Prompt 005 built a minimal, self-contained `Alert` type and fetch path
inside `features/dashboard` purely to back the "Attention Required"
section. §24 of this prompt required reusing one alert-fetching layer
instead of maintaining two, so `features/dashboard/api/alerts-api.ts`
and `features/dashboard/hooks/use-alerts.ts` were deleted and their
logic moved here — expanded from the Dashboard's minimal 8-field
`Alert` to the full 14-field shape confirmed by source inspection
(`projectId`, `ruleId`, `fingerprint`, `sourceReference`, `assignedTo`,
`closedAt` added). `AttentionRequiredSection` now imports from
`@/features/alerting` like any other consumer.

## Real endpoint inventory

Confirmed by direct source inspection of `services/alerting-service`,
never inferred from route names:

| Endpoint | Purpose |
|---|---|
| `GET /alerts` | List, filtered by `organization_id` (required), `status`, `severity` — no pagination/search/sort |
| `GET /alerts/{id}` | One alert, same shape as the list |
| `PUT /alerts/{id}` | Update severity/title/message/assigned_to (not used by any UI this prompt — not in §11-§14's action list) |
| `DELETE /alerts/{id}` | A status transition to `closed`, per the route's own docstring — **not a row deletion** |
| `POST /alerts/{id}/acknowledge` | Body `{comment?}` — also writes an `AlertAcknowledgement` row |
| `POST /alerts/{id}/resolve` | Body `{resolution_notes?}` |
| `POST /alerts/{id}/escalate` | Body `{policy_id?, reason?}` |
| `GET /alerts/{id}/history` | Real per-alert audit trail, auto-populated on every transition |
| `GET /alerts/{id}/acknowledgements` | Separate table — potentially multiple rows per alert |
| `GET /alerts/{id}/correlations` | Only children correlated *to* this alert; no group/cluster endpoint |
| `GET /alerts/{id}/notifications` | Delivery attempts per routed channel |
| `GET /alert-statistics` | Org-scoped, real backend-computed aggregates |
| `GET /maintenance-windows` | `active_only` flag; only `GET`/`POST` exist, no creation UI built |

Confirmed **not** to exist: a reopen route, an unsuppress route,
pagination/search/sort params on `GET /alerts`, and any role/permission
check on any of the above (all use only `Depends(get_current_user_id)`).
See `backend-v1-integration-limitations.md` for detail and citations.

## Client-side search/sort — why it's honest here

`GET /alerts` returns its complete result set for the active
`status`/`severity` filter, with no pagination. The Alerts page
therefore applies free-text search and column sorting entirely
client-side, over that complete result — there is no hidden remainder
a client-side operation could silently miss. This is a materially
different (stronger) guarantee than Monitoring's `CriticalIssuesSection`,
which explicitly documents its own client-side scan as *bounded and
incomplete* because its source endpoint **is** paginated.

## Mutation architecture

Each of `use-acknowledge-alert.ts`, `use-resolve-alert.ts`,
`use-escalate-alert.ts`, `use-close-alert.ts` wraps one `useMutation`
around the matching `alertsApi` method. None applies an optimistic
update — the UI waits for the backend's confirmed response before
showing an alert as acknowledged/resolved/escalated/closed, since a
failed mutation must never make an alert appear to have changed state
when it hasn't. `onSuccess` invalidates every query keyed under
`"alerts"` (list, this alert's detail, and every sub-resource share
that prefix), so nothing shows stale state after a successful action.

`AlertActions` renders each button behind `usePermissions().can(...)`
(`update` for Acknowledge/Resolve/Close, `execute` for Escalate) — a
pure UX convenience, since §25 confirms the backend performs no
permission check on any of these routes today. Every button also
disables (via `Button`'s own `loading` prop) while its mutation is
pending, preventing duplicate submission. Once an alert reaches
`resolved`/`closed`/`expired`, `AlertActions` renders nothing — there's
no backend route to undo any of those states.

## Severity vs. status — two independent taxonomies

`AlertSeverity` (`critical`/`high`/`medium`/`low`/`info`) and
`AlertStatusValue` (`new`/`open`/`acknowledged`/`investigating`/
`suppressed`/`escalated`/`resolved`/`closed`/`expired`) are independent
fields on `Alert` — severity doesn't change as an alert moves through
its lifecycle. `features/alerting/lib/severity.ts` centralizes the
severity→tone/rank/label maps (previously duplicated inline in
`attention-required-section.tsx`, now a single source both consume).

## Detail architecture

`AlertDetailView` composes Identity → Severity/Status → Timestamps →
Description → Actions → Lifecycle → Acknowledgements → Correlated
alerts → Notifications, per §9's own hierarchy. No separate "Metadata"
section: unlike `Asset`, `AlertResponse` has no arbitrary key/value
metadata field. `source_reference` (a free-form `dict[str, Any]`, no
fixed key guaranteed) is rendered as raw key/value pairs under
Identity, the same treatment Asset Detail gives its own
unresolvable ids.

## Permission handling

Same mechanism as Monitoring/Dashboard: every section's `SectionState`
(reused, not reimplemented) shows `AccessDeniedState` for a 403,
distinct from a generic retryable error. Mutation button visibility
additionally uses the coarse role capability model — see "Mutation
architecture," above.

## Error handling

Every section (summary, maintenance windows, the alert table, alert
detail, lifecycle, acknowledgements, correlations, notifications) is
its own `useQuery` + `SectionState` — one failing independently never
blanks the rest of the page (§20).

## Navigation / information architecture

`lib/route-registry.ts`: `alerting` (path `/alerting`) is the only
entry shown in the primary sidebar; `alerting-alerts` is registered
`"implemented"` (so the command palette can find it) but
`showInNav: false` — reachable via `AlertingSubNav` instead of a
deeper sidebar nesting level, mirroring Monitoring's own pattern
exactly. The dynamic `/alerting/alerts/[id]` route isn't registered at
all (a dynamic id has no meaningful static breadcrumb in the flat
registry) — its page renders its own "Back to Alerts" action instead.

## Dashboard integration

`AttentionRequiredSection` now links each alert card to its own
`/alerting/alerts/{id}` detail page, and the "Attention required"
section heading carries a "View in Alerting" link to `/alerting/alerts`
— both previously non-interactive since Alerting didn't exist until
this prompt.
