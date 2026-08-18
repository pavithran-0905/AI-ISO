# Dashboard

Per Prompt 005 §38, this honestly separates **IMPLEMENTED** from
**PLANNED** for the enterprise dashboard — the platform's first real
business feature. Nothing here claims future functionality as
currently available. See `../rfi/README.md` and
`../rfi/application-shell.md` for the foundation this builds on.

## Enterprise dashboard architecture — IMPLEMENTED

A real business feature under `features/dashboard/`, replacing the
Prompt 001 `modules/dashboard/` placeholder it was explicitly built to
prove out. Every data point traces to a specific, source-confirmed V1
endpoint (`docs/frontend/developer-guide/dashboard.md` lists every
one) — nothing is inferred from a service's name, and nothing is
fabricated when real data isn't available (§6/§7/§9/§10/§16's shared
requirement, followed throughout).

## Operational visibility — IMPLEMENTED

Answers the five questions §1 sets out — overall state, what's
unhealthy, what needs attention, what's running, what changed
recently — from real data: aggregated per-service health
(`GET /gateway/health`), active alerts (`GET /alerts`), and recent
automation runs (`GET /automation/executions`), all genuinely scoped
to the user's own organization.

## Modularity — IMPLEMENTED

Every section is an independent `useQuery` + component pair sharing
one loading/error/permission wrapper (`SectionState`) — a failure in
one never blanks the others (§16/§19). Adding a new section or KPI is
additive (see the developer guide's Extension guidelines), not a
rewrite.

## Responsive design — IMPLEMENTED (foundation, unchanged this prompt)

The dashboard's grid (KPI row, two-column attention/activity split,
full-width health/status sections) uses the same responsive utilities
established in Prompt 001-003 (`sm`/`lg` breakpoints, stacking on
narrow viewports) — no new responsive infrastructure was needed.

## Accessibility — IMPLEMENTED (foundation, unchanged this prompt)

Built entirely on already-accessible primitives (`StatusIndicator`,
`StatusBadge`, `EmptyState`, `ErrorState`, `Skeleton`, `PageHeader`) —
no new bespoke interactive pattern was introduced that needed its own
accessibility work. Chart/visualization accessibility (§25) is not
yet relevant: no charts were built this prompt (see What's PLANNED).

## Permission-aware presentation — IMPLEMENTED (mechanism)

Every section distinguishes a 403 (shown as "Access denied," not a
generic failure) from any other error. Broader role-based section
hiding wasn't implemented beyond that, because the frontend's coarse
role model doesn't currently support a real distinction for a
read-only page — see the developer guide's "Permission handling"
section for the full reasoning.

## Data integrity — IMPLEMENTED

No fabricated metric exists anywhere on this page. KPI cards show no
trend/percentage-change, since the backend doesn't provide the
historical data to compute one honestly (§7). "Recent activity" is
explicitly labeled as automation activity, not generic "platform
activity," because no cross-platform activity feed exists in Backend
V1 (confirmed by source inspection, not assumed).

## Degraded-service handling — IMPLEMENTED

A single unavailable backend service degrades only its own section
(clear message + Retry), never the whole dashboard (§16). Verified via
`SectionState`'s own unit tests (loading, retryable error, 403,
success) and the dashboard-page integration test.

## What's PLANNED

- **Charts/visualizations** — no chart library exists in this
  repository (§40 forbids adding one without a genuine need), and
  several of the richer aggregate fields the backend does expose
  (`alert-statistics`' `top_sources`/`trend_data`,
  `automation-statistics`' `execution_heatmap`) are untyped
  (`dict[str, Any]`) at the schema level — building a chart against an
  unconfirmed shape would risk exactly the "silently transforming
  unknown data" §28 forbids. A future prompt should pick a library
  against a real, now-typed requirement.
- **Quick actions / click-through navigation from dashboard tiles** —
  every target page (Monitoring, Alerting, Automation, etc.) is still
  `"planned"` in `lib/route-registry.ts`; §12/§26 both require linking
  only to routes that actually exist, so none of these buttons or
  links exist yet.
- **Time-range / historical filtering** (§13/§14) — not backed by
  real time-series data support today.
- **A cross-platform "recent activity" feed** — doesn't exist in
  Backend V1; automation executions stand in as the closest honest
  substitute, clearly labeled as such.

See `../backend-v1-integration-limitations.md` for the full,
cross-prompt list with source citations.
