# Operations Workspace

Per Prompt 019 §50, this honestly separates **IMPLEMENTED** from
**PLANNED**/**UNAVAILABLE** for the Enterprise Operations Workspace &
Incident Investigation Experience. See `../rfi/README.md` and
`../developer-guide/operations-workspace.md` for the full technical
reasoning.

**This is not an incident-management system.** No incident entity,
database, API, lifecycle, or assignment mechanism exists anywhere in
AI-IOS's backend, and none is fabricated here — this document, like
the feature itself, calls it an Operations Workspace throughout.

## Enterprise operational awareness — IMPLEMENTED (two real signal sources)

Active Alerts and recent Automation activity, both reusing the exact
same real queries and interpretations Dashboard already established.
A third candidate signal, unhealthy assets, is **confirmed
unavailable** — no health filter exists on the asset search route, and
the only unfiltered alternative is explicitly documented as unsuitable
for a primary list view.

## Multi-resource investigation — PARTIALLY IMPLEMENTED (real correlation only where it exists)

Selecting an alert or an automation run opens a real investigation
panel reusing this platform's own existing Alerting/Automation
components — never a duplicated alert or execution model. Alert-to-
alert correlation is real (`GET /alerts/{id}/correlations`). Execution
target ids are real but not confirmed to correspond to a verified
resource — shown as plain identifiers, not links.

## Cross-module visibility — PARTIALLY IMPLEMENTED

Topology, Monitoring, and Reporting context sections were **not
built**: no structured relationship exists from an Alert or an
Automation Execution to a specific Infrastructure asset (confirmed
absent — see the developer guide's own citation table), so there is
nothing real to show in a "this resource's topology/monitoring/reports"
section from a selected signal. Recent compliance Activity is shown,
real and narrow (one of Audit's three sources), with a link to the
full Audit & Activity experience.

## Topology context — UNAVAILABLE (confirmed, not unbuilt)

No signal this workspace shows (an alert or an automation execution)
carries a confirmed, structured link to a specific asset — so there is
no resource to open a topology preview *for*.

## Alert correlation — IMPLEMENTED (real, narrow)

"Related alerts" uses the real, already-built correlation endpoint —
only alerts explicitly correlated *to* the selected one as children,
never a fabricated "same root cause" claim.

## Activity visibility — PARTIALLY IMPLEMENTED

`compliance-service`'s own real audit trail (Prompt 015), last 24
hours — the richest of Audit's three real, unrelated sources, not a
cross-platform activity feed (no such capability exists on this
backend).

## Automation visibility — IMPLEMENTED

Real recent executions, selectable, showing real status/timestamps/
error messages and real (if unverified) target identifiers.

## AI-assisted investigation — IMPLEMENTED (redirect only, never inline analysis)

"Investigate with AI" and each context panel's own "Ask AI" open a
pre-filled, never-auto-sent Assistant draft built only from real,
already-loaded data. No AI-generated content is ever rendered inline
in this workspace — there is nothing here that needed an "Observed
vs. AI Analysis" visual distinction, because no AI analysis appears
in the workspace itself.

## Permission-aware operation — IMPLEMENTED

Alert actions (Acknowledge/Resolve/Escalate/Close) reuse the existing
`AlertActions` component's own permission gating unchanged — the same
frontend convenience, and the same underlying finding (Alerting
enforces no server-side permission check on any route today) already
documented for that feature.

## Resilient frontend architecture — IMPLEMENTED

Every section (alerts, executions, activity, and each context-panel
sub-section) has its own independent loading/error state — one
source's failure never blanks the rest of the workspace.

## Accessibility — IMPLEMENTED (foundation)

Built entirely on already-accessible primitives (`ResourceSection`,
`StatusBadge`/`StatusIndicator`, the existing Alerting components) —
no new bespoke interactive pattern introduced.

See `../backend-v1-integration-limitations.md` for the full,
cross-prompt list with source citations.
