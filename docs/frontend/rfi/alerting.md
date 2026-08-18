# Alerting

Per Prompt 007 §48, this honestly separates **IMPLEMENTED** from
**PLANNED**/**UNAVAILABLE** for the Enterprise Alerting & Incident
Experience. Nothing here claims future functionality as currently
available. See `../rfi/README.md`, `../rfi/dashboard.md`, and
`../rfi/monitoring.md` for the foundation this builds on.

## Alerting UX — IMPLEMENTED

A three-page experience (Overview, Alerts, Alert Detail) covering the
operator workflow the prompt sets out: see what's active, understand
its severity, work it through acknowledge/resolve/escalate, and
understand its full history. Every data point traces to a specific,
source-confirmed endpoint on `services/alerting-service` — see
`../developer-guide/alerting.md` for the full endpoint inventory.

## Alert lifecycle actions — IMPLEMENTED

Acknowledge, Resolve, Escalate, and Close — exactly the four mutations
confirmed to exist as real routes. Each waits for the backend's
confirmed response before updating the UI (no optimistic update),
disables its button while pending (preventing duplicate submission),
and reports success or failure clearly. Gated by the existing coarse
role capability model as a UX convenience — not a simulation of
backend authorization, since none exists on these routes today.

## Alert history and context — IMPLEMENTED

Lifecycle (real per-alert status-transition audit trail),
Acknowledgements (every acknowledge/resolve action recorded, separate
from the alert row itself), Correlated alerts (real children correlated
to this alert, each linking to its own detail page), and Notifications
(real delivery attempts per routed channel, including retry count and
error) — all from source-confirmed endpoints, none fabricated.

## Scalable data presentation — IMPLEMENTED

The Alerts page applies real server-side filtering (`status`,
`severity`) plus client-side search and sort over the endpoint's own
complete (non-paginated) result — honest specifically because nothing
is hidden behind a page boundary the client can't see. Filter/sort
state lives in the URL, making any specific view shareable and
survivable across navigation (§14).

## Responsive behaviour — IMPLEMENTED

The Alerts table renders as a real `<table>` at `md`+ and a stacked
card list below it (§32), matching Monitoring's established pattern.

## Accessibility — IMPLEMENTED (foundation, unchanged this prompt)

Built entirely on already-accessible primitives from Prompts 002/003/005/006
(`StatusBadge`, `Dialog`, `EmptyState`, `ErrorState`, native
`<table>`/`<select>`/`<input>`/`<textarea>`, `SectionState`) — no new
bespoke interactive pattern requiring dedicated accessibility work
beyond the existing `Dialog` component. Sortable column headers are
real `<button>`s with a visible sort-direction icon.

## Permission-aware data — IMPLEMENTED (mechanism, unchanged this prompt)

Every section distinguishes a 403 ("Access denied") from any other
failure, via the same `SectionState` component Dashboard and Monitoring
use. Mutation buttons are additionally gated by the coarse role
capability model (`@/permissions`) — the first feature in this codebase
to consume it for a real mutation surface.

## Partial failure handling — IMPLEMENTED

Every section (summary, maintenance windows, the alert table, alert
detail, lifecycle, acknowledgements, correlations, notifications) fails
independently — one unavailable piece of data degrades only its own
section, never the whole page (§20).

## Dashboard integration — IMPLEMENTED

`AttentionRequiredSection`'s alert-fetching logic, previously a
self-contained copy inside `features/dashboard` (Prompt 005), is now
consolidated into this feature — the single source both consume (§24).
Each alert card links to its own detail page; the section heading links
to the full Alerts list.

## What's PLANNED / UNAVAILABLE

- **Reopen.** No backend route moves a `resolved`/`closed`/`expired`
  alert back to an active state, even though the internal state
  machine permits the transition internally.
- **Unsuppress.** Suppression is evaluated at ingestion time via a
  separate resource (`alert-suppressions`); there's no per-instance
  toggle to undo it.
- **Maintenance window creation.** `POST /maintenance-windows` is real,
  but no creation form was built — this prompt's scope was
  representing existing windows clearly, not full CRUD management.
- **Alert-to-asset cross-linking.** An alert's `source_reference` is a
  free-form object with no guaranteed key; a real `InventoryClient`
  exists in the backend service but is never wired into any route
  (confirmed dead code, exercised only by its own unit test). No
  Alerting↔Monitoring link was built without a real, confirmed
  relationship to link through.
- **Editing an alert's severity/title/message/assignee.** `PUT
  /alerts/{id}` is real but wasn't in this prompt's own action list
  (§11-§14) — no edit form was built.

See `../backend-v1-integration-limitations.md` for the full,
cross-prompt list with source citations.
