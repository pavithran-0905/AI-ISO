# Dashboard

Per Prompt 005 §38 and Prompt 020, this honestly separates
**IMPLEMENTED** from **PARTIALLY IMPLEMENTED**/**PLANNED**/
**UNAVAILABLE** for the enterprise Dashboard / Executive Command
Center. Nothing here claims functionality as available that isn't.
See `../rfi/README.md` and `../developer-guide/dashboard.md` for the
full technical reasoning.

## Enterprise dashboard architecture — IMPLEMENTED

A real business feature under `features/dashboard/`, originally
replacing the Prompt 001 `modules/dashboard/` placeholder (Prompt 005)
and evolved into the full Executive Command Center (Prompt 020). Every
data point traces to a specific, source-confirmed V1 endpoint
(`docs/frontend/developer-guide/dashboard.md` lists every one) —
nothing is inferred from a service's name, and nothing is fabricated
when real data isn't available.

## Executive visibility — IMPLEMENTED

A dedicated header ("AI Infrastructure OS", current scope, last
updated, refresh, and a real platform-health badge computed only from
loaded asset-health data — never fabricated when there's no data yet),
an Executive Summary of real organization counts, and Executive-mode-
only Reporting and AI Insight widgets.

## Operational visibility — IMPLEMENTED

Asset Health (new in Prompt 020: real, org-wide asset health
distribution — the first prompt to surface this on the Dashboard),
Operational/System health (gateway reachability, Prompt 005), Active
Alerts, Automation Status, and an Operations-mode Operations Workspace
bridge — all sourced from real, already-built feature queries, never a
second implementation.

## Modularity — IMPLEMENTED

Every foundational section is an independent `useQuery` + component
pair sharing one loading/error/permission wrapper (`SectionState`) — a
failure in one never blanks the others. Every optional widget shares
`DashboardWidget`, built on the same primitive. Adding a new section or
widget is additive (see the developer guide's Extension guidelines),
not a rewrite.

## Cross-module integration — IMPLEMENTED, real sources only

Audit (Prompt 015, via `RecentActivityTimeline` reused directly, zero
duplication), Notifications (Prompt 016, the same bounded recent page
the shell bell already fetches), Reporting (real execution-status
counts), Infrastructure (real inventory size and relationship count),
Operations Workspace (Prompt 019, a navigational bridge only — the
real correlation logic stays exclusively in that workspace), Global
Search (Prompt 017 — unchanged, the shell's own search remains the
only search surface; no second search box was added), Resource Detail
(Prompt 018 — MetricCard's asset count links into the real Assets
list).

## Topology Summary — UNAVAILABLE (confirmed, not unbuilt)

No org-wide topology summary/health endpoint exists on this backend —
every topology query requires a specific `assetId`. The one honest,
real, org-wide topology-adjacent number available,
`InventoryStatistics.totalRelationships`, is surfaced inside the
Infrastructure widget instead of as its own thin card.

## Permission-aware presentation — IMPLEMENTED (mechanism real, mostly latent today)

Every section distinguishes a 403 (shown as "Access denied") from any
other error (Prompt 005, unchanged). Prompt 020 adds a complementary
layer for the six *optional* widgets: each one's visibility is gated
by the exact `roles` restriction on the real route it links into
(`getRouteById(id)?.roles`), via a pure, independently unit-tested
filter function. Five of the six optional widgets' linked routes
(`/infrastructure`, `/reporting`, `/notifications`, `/intelligence`,
`/operations`) carry no role restriction, so this mechanism is
currently a no-op for them — but Recent Activity's own linked route
(`/audit`, `roles: ["super_admin", "organization_admin"]`, Prompt 015)
*is* restricted, so that widget is a real, live demonstration of this
mechanism today, not merely a latent one: a `viewer`/`operator`/etc.
never sees it, an admin does.

## Scalable widget architecture — IMPLEMENTED

`DashboardWidget` (one shared Card/loading/error shell, reusing
`SectionState`) and a typed `DashboardWidgetDefinition[]` registry —
adding a future optional widget means one new component plus one new
registry entry, never a change to the page's own layout logic.

## Widget failure isolation — IMPLEMENTED

Every widget owns its own query and its own `DashboardWidget`/
`SectionState` instance; one failing (e.g. Reporting's statistics call
failing) never blanks any sibling widget or the six foundational
sections.

## Extensibility — IMPLEMENTED

A future widget: implement `ComponentType<{ organizationId: string }>`,
add one entry to `DASHBOARD_WIDGET_REGISTRY` with its own `modes`/
`roles`/`defaultVisible`. No page-level change required.

## AI-assisted insights — IMPLEMENTED (redirect only, never inline analysis)

AI Insight never renders generated text inline — no dashboard-
summarization endpoint exists on this backend (confirmed absent). It
shows a real, already-generated recommendation count plus a redirect
into a genuinely separate Assistant conversation, mirroring Operations
Workspace's own established precedent (Prompt 019).

## Data integrity — IMPLEMENTED

No fabricated metric exists anywhere on this page. KPI cards show no
trend/percentage-change, since the backend doesn't provide the
historical data to compute one honestly. "Recent activity" is now a
real, narrow, audit-based feed (Prompt 015/019), clearly distinct from
"Recent automation activity" — no cross-platform activity feed exists
in Backend V1 (confirmed by source inspection, still true after this
prompt's own re-check).

## Responsive design — IMPLEMENTED

Mobile stacking order follows §41's own priority list (Health →
Critical Alerts → Attention → Activity → other summaries) via plain
DOM order, not extra reordering CSS — Asset Health is the first
health-related section on the page. The dashboard's grid otherwise
uses the same responsive utilities established in Prompts 001-003.

## Accessibility — IMPLEMENTED (foundation, extended)

Built entirely on already-accessible primitives (`SectionState`,
`StatusIndicator`, `StatusBadge`, `EmptyState`, `ErrorState`,
`Skeleton`, `PageHeader`, `MetricCard`) plus two new ones this prompt:
a native `radiogroup` for the mode switch (deliberately not a
repurposed `Tabs`, which owns a single `tabpanel` a multi-widget mode
switch doesn't have) and `DistributionBar` with an `aria-label`
summary and a plain-text legend (§40 — never color alone).

## Degraded-service handling — IMPLEMENTED

A single unavailable backend service degrades only its own section
(clear message + Retry), never the whole dashboard. Verified via
`SectionState`/`DashboardWidget`'s own unit tests (loading, retryable
error, 403, success) and the dashboard-page integration test.

## What was PLANNED in Prompt 005, now delivered by Prompt 020

- **Charts/visualizations** — Prompt 005 deliberately left this
  PLANNED (no charting library existed, and the richer aggregate
  fields available then were untyped `dict[str, Any]`). Prompt 020
  builds `DistributionBar` against a now-real, fully-typed dataset
  (`InventoryStatistics.healthDistribution`) — still no chart library
  added (§58), since a single proportional bar doesn't need one.
- **Quick actions / click-through navigation from dashboard tiles** —
  every target module now has a real, implemented page; Quick Access
  (§23) links to all of them, filtered by role.

## What's still PLANNED / UNAVAILABLE

- **Time-range / historical filtering** (§13/§14 in Prompt 005's own
  numbering) — still not backed by real time-series data support.
- **A true cross-platform "recent activity" feed** — still doesn't
  exist in Backend V1; the new Recent Activity widget (Audit's
  compliance trail) is the richest real, narrow substitute available,
  clearly labeled as such, not conflated with a platform-wide feed.
- **Topology Summary** — see above, confirmed unavailable.
- **Dashboard-generated AI summaries** — see AI Insight above,
  confirmed unavailable; only a real recommendation count and a
  redirect are shown.

See `../backend-v1-integration-limitations.md` for the full,
cross-prompt list with source citations.
