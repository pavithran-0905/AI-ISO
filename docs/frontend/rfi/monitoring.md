# Monitoring

Per Prompt 006 §38, this honestly separates **IMPLEMENTED** from
**PLANNED**/**UNAVAILABLE** for the Monitoring & Observability
experience. Nothing here claims future functionality as currently
available. See `../rfi/README.md` and `../rfi/dashboard.md` for the
foundation this builds on.

## Monitoring UX — IMPLEMENTED

A five-page experience (Overview, Assets, Asset Detail, Services,
Events) covering the operator workflow §1 sets out: understand
infrastructure health, inspect assets, identify degraded/failed
resources, move from summary to detail, filter/search large datasets,
and understand recent changes. Every data point traces to a specific,
source-confirmed V1 endpoint across three backend services
(`inventory-service`, `observability-platform-service`,
`api-gateway-service`) — see `../developer-guide/monitoring.md` for
the full endpoint list and the important note that these three
services use three genuinely different health-enum vocabularies and
organization-scoping conventions, never conflated.

## Operational visibility — IMPLEMENTED

Health Summary (real backend-computed distribution, not client-counted),
Critical Issues (client-filtered from real per-asset health, bounded
and documented as such), Service Health (real dependency-topology
health per service), and an Events timeline (real, chronologically
ordered) together answer "what's healthy, what's failed, what needs
investigation, what changed recently" from real data only.

## Scalable data presentation — IMPLEMENTED

The Assets table uses real server-side search, filtering
(status/type), sorting, and pagination (`GET /inventory/search`) — not
a client-side filter over an unbounded fetch. Table density
(comfortable/compact) is a persisted user preference. Filter/sort/page
state lives in the URL, making any specific view shareable and
survivable across navigation (§14).

## Responsive behaviour — IMPLEMENTED

The Assets table renders as a real `<table>` at `md`+ and a stacked
card list below it (§32) — not a horizontally-scrolling table.

## Accessibility — IMPLEMENTED (foundation, unchanged this prompt)

Built entirely on already-accessible primitives from Prompts 002/003/005
(`StatusIndicator`, `EmptyState`, `ErrorState`, native `<table>`/`<select>`/`<input>`,
`SectionState`) — no new bespoke interactive pattern requiring dedicated
accessibility work was introduced. Sortable column headers are real
`<button>`s with a visible sort-direction icon, not a div with a click
handler.

## Permission-aware data — IMPLEMENTED (mechanism, unchanged this prompt)

Every section distinguishes a 403 (shown as "Access denied") from any
other failure, via the same `SectionState` component the Dashboard
uses — not reimplemented, not a new pattern.

## Partial failure handling — IMPLEMENTED

Every section (health summary, critical issues, service health,
events, the asset table, asset detail, related assets) fails
independently — a single unavailable backend service degrades only its
own section, with a clear message and Retry, never the whole page
(§20).

## Performance — IMPLEMENTED

Real server-side pagination/filtering/sorting (never fetches more than
one page for the table); `keepPreviousData` avoids a full-page loading
flash on filter/sort/page changes; no virtualization yet (page sizes
don't currently justify it).

## What's PLANNED / UNAVAILABLE

- **Metrics/charts.** `GET /observability/metrics` is real, but
  requires a `series_id` the caller must already know — no
  series-discovery/list endpoint exists in Backend V1. A generic
  "browse and chart any metric" experience can't be built honestly
  against this contract; building one against a guessed series id
  would be exactly the "inferring response fields from endpoint names"
  §2 forbids. Deferred until a discovery endpoint exists.
- **Events linked to a specific asset.** `ObservabilityEventResponse`
  has no asset-id reference field (only an optional `service_name`
  string) — event-to-asset correlation isn't possible from this
  endpoint today.
- **Category/class/location names for an asset.** `inventory-service`
  has no REST endpoint to resolve `category_id`/`class_id`/`location_id`
  to human-readable names (the underlying service/repository code
  exists internally but isn't wired to any API router) — Asset Detail
  shows these as raw ids.
- **Organization-wide "critical issues" beyond one bounded page.**
  `GET /inventory/search` has no `health` filter parameter, so
  Critical Issues scans a bounded, sorted page rather than the full
  dataset — documented in the section's own UI copy when truncated.

See `../backend-v1-integration-limitations.md` for the full,
cross-prompt list with source citations.
