# Automation

Per Prompt 009 §52, this honestly separates **IMPLEMENTED** from
**PLANNED**/**UNAVAILABLE** for the Enterprise Automation, Workflow &
Job Orchestration Experience. Nothing here claims future functionality
as currently available. See `../rfi/README.md`, `../rfi/dashboard.md`,
`../rfi/monitoring.md`, `../rfi/alerting.md`, and `../rfi/reporting.md`
for the foundation this builds on.

## Automation UX — IMPLEMENTED

An eleven-route experience across two feature modules: Automation
(Overview, Automations list/create/detail/edit, Executions list/
detail) against `services/automation-service`, and Workflows
(Workflows list/detail, Instances list/detail) against
`services/workflow-runtime-service`. Every data point traces to a
specific, source-confirmed V1 endpoint — see
`../developer-guide/automation.md` for the full inventory and why the
two services are deliberately kept as separate modules rather than
unified (materially different, only-partially-overlapping status
vocabularies and data models).

## Run workflow and safety UX — IMPLEMENTED

A real two-step Configure → Confirm flow for both Run Automation and
Run Workflow (§10/§11/§38): the confirmation step names the
automation/workflow, its variables, and — for Automation — states
plainly that it runs on the AI-IOS automation host, since there is no
target picker to imply otherwise. The confirm button is always
labeled unambiguously ("Run Automation"/"Run Workflow"), is disabled
for the mutation's duration (§12, preventing duplicate submission),
and nothing is retried automatically.

## Execution/instance visibility — IMPLEMENTED

Real, polling-based following of an in-flight run (§18): both
`automation-service` and `workflow-runtime-service` expose no
WebSocket or SSE endpoint (confirmed by source inspection of both), so
every "live" view here polls every 5 seconds while the run is active
and stops the moment it reaches a terminal status — never inventing
real-time behaviour the backend doesn't have. Execution/instance
detail shows computed duration (no such field exists on either
response), real status, real timestamps, and real output.

## Logs — IMPLEMENTED (honestly scoped)

A real log viewer (§17) with search, severity filtering, and copy, all
applied client-side over the endpoint's own complete, unpaginated
result. No follow/pause-streaming toggle: §17 asks for one "if
streaming exists" — it doesn't, on either service, so a pause control
over a plain poll would be theatre rather than a real capability.

## Cancel/Pause/Resume — IMPLEMENTED, with real caveats surfaced

Both services model these as cooperative, job/workflow-scoped
transitions, not preemptive per-execution controls — the UI states
this rather than implying an immediate halt (§20). Cancel requires
confirmation and never shows "Cancelled" until the backend's response
confirms it. Resume is handled carefully: the backend's own response
to a resume call still reports the pre-resume status (only a worker
flips it to running), so the UI says "Resuming" rather than claiming
success it can't yet back.

## Workflow-specific capability — IMPLEMENTED

Per-node step breakdown and human-approval decision gates (§9) — real
capabilities `workflow-runtime-service` has that `automation-service`
does not (its own step rows exist backend-side but have no route).
Approving/rejecting requires the coarse capability model's `approve`
action and a typed-in approver name, since the backend models
approvers as free-text strings with no reliable way to match them to
the signed-in session.

## Permission-aware actions — IMPLEMENTED (mechanism, mapped onto the existing 9-action vocabulary)

Every mutation is gated by the coarse role capability model (§25),
mapped onto the closest of the platform's 9 real actions since neither
service defines Automation/Workflow-specific verbs. Both services
enforce no permission check on any route today (see Backend V1
limitations) — this is a UX convenience only.

## Parameters and targets — UNAVAILABLE (documented, not implemented)

§13/§16 ask for typed, schema-driven parameter forms and a target
selector. Neither is implemented, because neither is reachable: a
complete `AutomationParameter` model/service/schema exists with zero
routes, `parameter_type` isn't even an enum server-side, and
`AutomationTarget` similarly has full backend plumbing and zero
routes. Variables are a plain free-form key/value editor instead
(§13's own "do not hardcode parameters" cuts the other way too —
faking a schema that can't be fetched would be exactly that).

## Scheduling — UNAVAILABLE (documented, not implemented)

§22/§23 ask for automation scheduling UI. `automation-service` has a
complete `AutomationSchedule` model and service layer — and zero
routes, and its cron engine is never started at process startup
(confirmed: no `SchedulerManager` is constructed in `app/core/factory.py`
despite a docstring elsewhere claiming otherwise). Building this UI
would be entirely decorative.

## Retry — UNAVAILABLE (documented, not implemented)

§19 asks for it "if V1 supports retry." No retry endpoint exists on
either service. Both retry transient failures internally during
dispatch, but that history has no route either. Re-running is done
through Run Automation/Run Workflow, described honestly as a fresh run
rather than a resumed one.

## Auditability — PARTIAL

`GET /automation/executions/{id}` and the execution list are real,
durable records of what ran and when. There is no full audit trail
beyond that (`AutomationRetryHistory`, approval decisions' full
history beyond the current `WorkflowApproval` row, and
`AutomationResult`/`AutomationOutput` all exist backend-side with no
route).

## Partial failure handling — IMPLEMENTED

Every section (summary, running-now, needs-attention, tables, detail
views, logs, steps, approvals) fails independently — one unavailable
piece of data degrades only its own section, never the whole page
(§35).

## Responsive behaviour — IMPLEMENTED

Both feature modules' tables render as a real `<table>` at `md`+ and a
stacked card list below it (§36), matching the established pattern
from Monitoring/Alerting/Reporting.

## Accessibility — IMPLEMENTED (foundation, unchanged this prompt)

Built entirely on already-accessible primitives from Prompts 002/003/
005–008 (`StatusBadge`, `StatusIndicator`, `Dialog`, `EmptyState`,
`ErrorState`, native `<table>`/`<select>`/`<input>`/`<textarea>`,
`SectionState`) — no new bespoke interactive pattern requiring
dedicated accessibility work.

## Dashboard integration — IMPLEMENTED

`RecentActivitySection`'s execution-fetching logic, previously a
self-contained copy inside `features/dashboard` (Prompt 005), is now
consolidated into `features/automation` (§28/§29). The KPI grid's
"Automations" tile and the "Recent automation activity" heading both
link into the new real routes.

## Monitoring / Alerting integration — N/A this prompt

§26/§27 ask for these links "where actual V1 relationships exist." None
do: no field on either service's job/execution/workflow/instance
schemas references an inventory asset or an alert, and neither service
calls `inventory-service` or `alerting-service` from any reachable
code path. Nothing was fabricated.

See `../backend-v1-integration-limitations.md` for the full,
cross-prompt list with source citations.
