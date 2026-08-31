# Resource Detail & Investigation Workspace

Per Prompt 018 §52, this honestly separates **IMPLEMENTED** from
**PLANNED**/**UNAVAILABLE** for the Enterprise Resource Detail &
Investigation Workspace, built as reusable shell primitives applied to
Infrastructure Assets — the only resource type in this backend with
enough real investigation depth to warrant the concept. See
`../rfi/README.md` and `../developer-guide/resource-investigation.md`
for the full technical reasoning.

## Unified resource investigation — IMPLEMENTED (one real resource type, reusable shell)

`components/resource/*` (`ResourceHeader`, `ResourceBreadcrumbs`,
`ResourceSection`, `ResourceNotFound`) are genuinely reusable, applied
first to Asset Detail as the reference implementation. "Machine" /
"VM" / "Service" / "Application" are not separate backend resources —
one real `Asset` model with an `asset_type` field covers all of them,
so one adapter was built, not four.

## Operational visibility — IMPLEMENTED (only where real)

Overview (identity, current state), Relationships, Topology, and
Configuration are real, each independently loaded, each independently
resilient to failure. Health is the asset's own real `health` field —
there is no metric-series endpoint on this backend at all, confirmed
absent, so no Metrics section exists.

## Cross-module navigation — PARTIALLY IMPLEMENTED

Topology ("View in Topology") and AI ("Ask AI about this resource")
are real. Alerts, Automation, Reports, and Monitoring integrations are
**not implemented — confirmed absent**, not merely unbuilt: no
structured foreign key exists from an Alert, Automation Target,
Report, or Monitoring event to an inventory-service asset id anywhere
in this backend (see the developer guide for the exact citation on
each). Global Search already links to a resource's real detail page
(Prompt 017, re-verified here). Notification and Audit Event links to
a resource are confirmed absent for the same reason (Prompts 015/016).

## Health visibility — PARTIALLY IMPLEMENTED

The asset's own real health/status/lifecycle/criticality fields, using
the platform's own canonical status system — never a recalculated or
invented health score.

## Activity visibility — UNAVAILABLE (confirmed, not unbuilt)

`inventory-service` has a real, populated audit table with zero route
reaching it (an already-documented finding from Prompt 015). No Audit
integration is shown on a resource's own page as a result.

## Permission-aware UX — IMPLEMENTED

Actions (Edit/Delete) are gated by the existing permission
architecture (`usePermissions().can(...)`), unchanged from Prompt
011 — the backend, per that prompt's own finding, still enforces its
own separate authorization (or lack thereof) independently; this
frontend gating remains a convenience, never a boundary.

## Scalability — IMPLEMENTED

Each section's query is independent and only fires once its own tab
is actually opened — switching to a tab never re-fetches an
already-cached section, and a section never opened never issues a
request at all.

## Accessibility — IMPLEMENTED (foundation)

Real `tablist`/`tab`/`tabpanel` semantics (the existing `Tabs`
primitive, unchanged), a dedicated not-found state instead of a
generic error for a real 404, and independent per-section
loading/error announcements via the existing `SectionState`.

See `../backend-v1-integration-limitations.md` for the full,
cross-prompt list with source citations.
