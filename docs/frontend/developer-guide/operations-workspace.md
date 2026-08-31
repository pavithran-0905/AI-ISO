# Operations Workspace

Built in Prompt 019 as a frontend-only correlation view over Alerting
and Automation's own real data — never an incident-management system,
per this prompt's own explicit instruction (§2): no service in this
backend exposes an `/incidents` route, model, or lifecycle of any
kind. See `docs/frontend/rfi/operations-workspace.md` for the
implemented-vs-planned split and
`docs/frontend/backend-v1-integration-limitations.md` for the full gap
list with citations.

## Two real signal sources, never a fabricated third

`features/operations/components/alert-signals-list.tsx` and
`automation-signals-list.tsx` reuse the exact same real queries and
"attention"/"recent" interpretation Dashboard already established
(`features/dashboard/components/attention-required-section.tsx` and
`recent-activity-section.tsx`, Prompts 005/006) — `useAlerts`,
`RESOLVED_ALERT_STATUSES`, `SEVERITY_RANK`/`SEVERITY_TONE`,
`useExecutions`. The one genuine difference: clicking a signal here
*selects* it (for the context panel) instead of navigating away, which
is a different interaction, not a second copy of the fetch/derive
logic (§41: "do not create a fake incident API").

**"Unhealthy Assets" was deliberately not built as a third signal
source.** `GET /inventory/search` has no `health` query parameter
(confirmed absent by reading `AssetSearchParams`), and the only
unfiltered alternative, `useAllAssets`, carries its own explicit
warning in its own docstring: "never use as a primary list view."
Building an unhealthy-assets signal would require either fetching an
entire, unbounded organization's asset list to filter 1% of it
client-side (violating §45's own "do not request large datasets
unnecessarily"), or pretending a filter exists that doesn't. Neither
is acceptable — the signal source is documented as confirmed
unavailable rather than approximated.

## What can genuinely be correlated — and what cannot

§42 permits frontend correlation only when the relationship is
explicit. This prompt's own research (extending Prompt 018's findings
about Infrastructure Assets specifically) settles this precisely:

| Relationship | Real? | Evidence |
|---|---|---|
| Alert ↔ Alert (correlation) | **Yes** | `GET /alerts/{id}/correlations`, a real, already-built endpoint and component (`AlertCorrelationsList`, Prompt 007) |
| Execution → target asset ids | **Yes, but unverified** | `AutomationExecution.variables._target_ids`, real and recoverable via `splitExecutionVariables()` (Prompt 009) — but no run-automation UI in this codebase populates it from a validated asset picker, so these ids are not confirmed to correspond to a currently-existing `inventory-service` asset |
| Alert → resource/asset | **No** | `Alert.source_reference` is unstructured JSON with no schema-enforced foreign key (confirmed by `alert_instance.py`'s own model docstring) |
| Automation target → resource (via the separate "targets" API) | **No route** | `AutomationTargetResponse.inventory_asset_id` is a real, persisted field with zero router ever registered to reach it (Prompt 018's own finding) |
| Any signal → Audit event | **No** | None of Audit's three real sources (Prompt 015) records infrastructure, alerting, or automation actions |
| Notification → operations context | **No** | `Notification` has no structured entity reference at all (Prompt 016) |

**Frontend behavior**: "Related alerts" (§11) reuses the real
correlation endpoint and its own established, careful language ("no
group_id or standalone grouping endpoint... only this alert's own
children" — already documented in `AlertCorrelationsList`'s own
docstring). An execution's target ids are shown as plain, unlinked
mono-font identifiers, mirroring the exact treatment
`ExecutionDetailView` (Prompt 009) already established — not changed
here, since linking them would overstate a relationship this frontend
has never confirmed. An alert's `source_reference` is never rendered
as if it identified a specific resource.

## Investigation context lives entirely in the URL

`?signal=alert:<id>` / `execution:<id>` (§24/§25) — never local
`useState`. The selected alert/execution is *derived* from this param
plus the already-loaded `useAlerts`/`useExecutions` data already
rendering the signal columns, not a second fetch. This means reloading
or sharing the URL reopens the exact same investigation (§26), and no
extra request is needed to resolve a selection — confirmed by a test
asserting the context panel renders correctly from a cold page load
with `?signal=` already in the URL.

## Activity Timeline — one real, narrow source, not a cross-platform feed

`RecentActivityTimeline` shows `compliance-service`'s own audit trail
only (Prompt 015's primary/richest real source), the last 24 hours,
via the already-built `useAuditEvents("compliance", ...)` hook —
reused unchanged. Showing all three of Audit's real, unrelated sources
here would just re-implement Audit & Activity's own source-selector at
a smaller size; "View full activity" links out to `/audit/activity`
instead.

## Evidence vs. AI Analysis (§22/§23)

This workspace renders no AI-generated content inline at all — nothing
here needed the "Observed" vs. "AI Analysis" labeling distinction to
be applied within a single view, because there is no AI-generated view
to distinguish from. "Investigate with AI" (header) and each context
panel's own "Ask AI" reuse the existing `AskAiButton` pattern
unchanged (Prompt 010): a pre-filled, never-auto-sent draft built only
from real, already-loaded counts/fields (e.g. "N active alerts,
highest severity: X"), opening a genuinely separate Assistant
conversation — never inline generated analysis presented alongside
observed data.

## Refresh (§27) — scoped, not whole-application

Invalidates exactly `["alerts"]`, `["automation", "executions"]`, and
`["audit"]` — the three real query-key prefixes this workspace's own
sections use — then calls the shared `useRefreshAction` for its
timestamp bookkeeping. Never the page-wide `invalidateQueries()`
Dashboard/Monitoring/Reporting use for a page with one dominant query;
this workspace composes several independent sources, so a page-wide
invalidate would be proportionally more wasteful here.

## Cross-module integration (§37-§40)

- **Global Search → Operations Workspace**: real, for free — the route
  is registered in `lib/route-registry.ts` like every other
  implemented route, so it's already searchable/navigable through
  Prompt 017's palette without any new code.
- **Resource Detail → Operations Workspace**: **not built.** No
  correlation exists that would let this workspace show anything
  meaningfully scoped to one specific asset (confirmed absent, see the
  table above) — a generic, unscoped link would imply a filtered view
  that doesn't exist.
- **Notification → Operations context**: confirmed absent (Prompt
  016's own finding, reconfirmed here).
- **Audit event → Operations context**: confirmed absent — no audit
  entity type in any of the three real sources maps to an alert or
  execution id.

## Performance

Alerts, executions, and the audit feed are three independent,
parallel `useQuery` calls (§44/§45) — no waterfall. Selecting a signal
never triggers a new fetch (the object is already in memory from the
list query); only the correlation/history sub-sections inside
`AlertContextPanel` issue their own real, small, id-scoped requests.
