# Reporting

Per Prompt 008 §51, this honestly separates **IMPLEMENTED** from
**PLANNED**/**UNAVAILABLE** for the Enterprise Reporting, Report
Designer, Scheduling & Distribution Experience. Nothing here claims
future functionality as currently available. See `../rfi/README.md`,
`../rfi/dashboard.md`, `../rfi/monitoring.md`, and `../rfi/alerting.md`
for the foundation this builds on.

## Reporting UX — IMPLEMENTED

An eleven-route experience (Overview, Reports list/create/detail/edit,
Templates list/create/detail, Scheduled Reports, Generated Reports,
Archive) covering the workflow §1 sets out: browse reports, view
detail, create and design reports where V1 supports it, generate,
download/export, schedule, distribute, inspect history, and access
archived reports. Every data point traces to a specific,
source-confirmed V1 endpoint on `services/reporting-service` — see
`../developer-guide/reporting.md` for the full endpoint inventory and
the important note that this service, unlike prior ones, enforces no
tenant isolation at all (flagged prominently, not glossed over).

## Report designer — IMPLEMENTED

A real, structured, schema-driven section editor (§7) — add, edit,
reorder, and remove sections, each validated against the same
per-kind requirements the backend enforces on write. Not a
drag-and-drop canvas: the backend contract has no such concept, and
§7 explicitly forbids faking one. No live chart/table preview either —
sections render server-side only; "preview" means generating and
opening a real export (§10).

## Generation, export, and download — IMPLEMENTED

Real synchronous generation against `POST /reports/generate` (§13),
real 7-format export (`pdf, xlsx, csv, json, markdown, html, xml`, §11),
real binary download handling with safe, server-sanitized filenames
(§12). A generation's degraded sections are shown as a visible
warning, never silently dropped (§13).

## Scheduling — IMPLEMENTED

Real schedule CRUD against the exact fields `ScheduleCreateRequest`/
`ScheduleUpdateRequest` accept (§15/§16): frequency (including a raw
cron expression), timezone (drawn from the browser's own real IANA
timezone database via `Intl.supportedValuesOf`, not invented), start/
end, enable/disable (the `enabled` field on the update request, not a
dedicated endpoint — there isn't one).

## Distribution and sharing — IMPLEMENTED

Real distribution channels only (`download, email, webhook,
shared_link, api, object_storage`, §17) — never a generic "email/
Slack/Teams" list. Standing recipients (persistent, per-report) and
ad-hoc distribute/share (per-export, one-off) are both real and
distinct. No credential/secret field is collected anywhere in the UI
(§17). Share-link tokens are shown exactly once, matching the backend's
own one-time-return design (§18).

## Archive — IMPLEMENTED

Real immutable archive browsing, search, and status filtering (§19),
download, restore (creates a new export, never resurrects the
original), and retention-gated purge — a rejected purge shows the
backend's own real reason (§20), never bypassed or hidden.

## AI narratives — IMPLEMENTED (honestly scoped)

An `AI_SUMMARY` designer section is a real, first-class section kind.
Because the backend renders it inline within the single synchronous
generate call with no separate polling endpoint, the frontend shows
one whole-pipeline loading state rather than fabricating a distinct
"generating narrative…" sub-state (§21/§22) — the backend has exactly
two real outcomes (success or a labeled failure that degrades only
that section), and that's exactly what's surfaced.

## Permission-aware reporting — IMPLEMENTED (mechanism, mapped onto the existing 9-action vocabulary)

Every mutation is gated by the coarse role capability model (§25) —
mapped onto the closest of the platform's real 9 actions since
Reporting-specific verbs like "generate"/"schedule"/"distribute" don't
exist in that vocabulary. This is a UX convenience only: `reporting-service`
enforces no permission check on any route today (see Backend V1
limitations).

## Concurrency/versioning — UNAVAILABLE (documented, not implemented)

§30 asks for real optimistic-locking conflict handling ("Your report
changed elsewhere..."). `reporting-service` has the underlying
`version` column and `expected_version` mechanism in its shared
repository base, but never exposes `version` in any response schema
and never passes `expected_version` on write — there is no reachable
409 to build this UI against. Not implemented, because implementing it
against a contract that can't produce the conflict it's meant to
handle would be exactly the kind of invented behavior this project
avoids.

## Partial failure handling — IMPLEMENTED

Every section (summary, recent generations, favorites, reports table,
report detail, schedules, recipients, history, templates, archive)
fails independently — one unavailable piece of data degrades only its
own section, never the whole page (§20).

## Responsive behaviour — IMPLEMENTED

The Reports table renders as a real `<table>` at `md`+ and a stacked
card list below it (§34), matching Monitoring's and Alerting's
established pattern. The designer's section list and dialogs reflow
to a single column on narrow viewports rather than overflowing
horizontally.

## Accessibility — IMPLEMENTED (foundation, unchanged this prompt)

Built entirely on already-accessible primitives from Prompts 002/003/
005/006/007 (`StatusBadge`, `Dialog`, `Switch`, `EmptyState`,
`ErrorState`, native `<table>`/`<select>`/`<input>`/`<textarea>`,
`SectionState`) — no new bespoke interactive pattern requiring
dedicated accessibility work beyond composing the existing `Dialog`.

## Dashboard integration — N/A this prompt

§36 only asks for a Dashboard→Reporting link "where Dashboard contains
report metrics." It doesn't — the Dashboard's KPI grid has no
report-count field — so nothing was added rather than fabricating a
metric to link from.

## What's PLANNED / UNAVAILABLE

- **Re-fetching a past generation's results.** No `GET /reports/{id}/executions`
  or `GET /reports/executions/{id}` endpoint exists — a generation's
  artifacts are only visible in the single response that produced
  them. Revisit if such an endpoint is added.
- **Revoking a share link before it expires.** No endpoint exists.
- **Per-report archive filtering.** `GET /reports/archive` has no
  `report_id`/`job_id` param — only the org-wide Archive page exists.
- **Editing a report's category, type, or template after creation.**
  `PUT /reports/{id}` doesn't accept these fields.

See `../backend-v1-integration-limitations.md` for the full,
cross-prompt list with source citations.
