# Reporting

The Enterprise Reporting, Report Designer, Scheduling & Distribution
Experience built in Prompt 008, on top of the Dashboard's
`organization/` context (Prompt 005) and the patterns established by
Monitoring (Prompt 006) and Alerting (Prompt 007). See
`docs/frontend/rfi/reporting.md` for the implemented-vs-planned split
and `docs/frontend/backend-v1-integration-limitations.md` for every
gap discovered building this — there are more of them, and more
serious ones, than in prior prompts (see "Tenant isolation," below).

## Feature structure

```
features/reporting/
├── api/            reports-api.ts, templates-api.ts, schedules-api.ts,
│                    distribution-api.ts, archive-api.ts
├── hooks/           grouped by resource: use-reports.ts, use-templates.ts,
│                    use-schedules.ts, use-distribution.ts, use-archive.ts
├── components/      ~20 components — filters/tables/dialogs per resource,
│                    the designer (ReportDefinitionEditor + SectionFormDialog),
│                    ReportingSubNav
├── types/           response types mirroring the real V1 schemas, plus the
│                    designer document types (ReportDefinition/ReportSection/...)
├── lib/             binary-fetch.ts, format-duration.ts, status-tones.ts
└── pages/           reporting-overview-page.tsx, reports-list-page.tsx,
                     report-new-page.tsx, report-detail-page.tsx, report-edit-page.tsx,
                     templates-list-page.tsx, template-new-page.tsx, template-detail-page.tsx,
                     schedules-list-page.tsx, history-list-page.tsx, archive-list-page.tsx
```

Follows §26's flow: `Page → Hook → API module → apiClient → real V1 endpoint`,
grouping hooks by resource (rather than one file per hook, as Alerting
did) since this feature has roughly 3× the endpoint count — the same
principle, adapted to scale.

## Binary downloads — a deliberate, documented exception to "only `@/api/client` calls `fetch`"

Two routes (`GET /reports/exports/{id}/download`,
`GET /reports/archive/{id}/download`) return a raw binary body instead
of the `{success, message, data, meta}` envelope every other endpoint
uses. `apiClient` only knows how to parse the envelope, so
`features/reporting/lib/binary-fetch.ts#fetchBinary` is a small,
separate fetch path — same auth/error-normalization behavior (reuses
`ApiRequestError`/`ApiNetworkError`), different response parsing
(`response.blob()` plus `Content-Disposition` filename parsing instead
of JSON). `saveBlob()` triggers the actual browser save-as via an
object URL, revoked immediately after use.

## Real endpoint inventory

Confirmed by direct source inspection of `services/reporting-service`
(41 endpoints across `reports.py`, `templates.py`, `delivery.py`),
never inferred from route names. The full table lives in the research
this prompt is built on — key points:

- `GET /reports` supports only `organization_id`, `category`,
  `enabled_only` — no pagination/search/sort.
- `POST /reports/generate` is **synchronous** — it runs the whole
  render+export pipeline inline and returns the complete result, not a
  job handle to poll.
- Exports are downloaded separately (`GET /reports/exports/{id}/download`)
  — list/detail responses never include artifact bytes.
- Templates go through a real state machine: `draft → approved → archived`.
  A report can only generate against an `approved` template
  (`resolve_for_execution()` enforces this server-side).
- 7 real export formats (`pdf, xlsx, csv, json, markdown, html, xml`)
  and 6 real distribution channels (`download, email, webhook,
  shared_link, api, object_storage`) — confirmed against the actual
  enums, not assumed.

## Tenant isolation — the most serious gap found this prompt

Unlike every prior prompt's "no permission checks" finding,
`reporting-service` additionally applies **no org-scoping enforcement**
at the repository layer: every DI factory in `app/api/deps.py`
constructs its repository without the `tenant_scope` argument
`BaseRepository` needs to actually filter by organization. See the
backend-v1-integration-limitations.md entry for the full detail. The
frontend's own behavior is unaffected — every call still sends the
real, currently-selected `organization_id` — but this is flagged
prominently because it's a materially different (and worse) class of
gap than "UX-only permission gating," and any reviewer of this feature
should know about it.

## The designer — a real, structured editor, not a fake canvas

`ReportDefinitionEditor` manages a template version's `definition`
(title/subtitle/branding + an ordered section list); each section's
own fields are edited in `SectionFormDialog`, which enforces the same
per-kind requirements the backend validates on write
(`ReportSection._validate_kind_requirements` in
`app/reports/designer/schema.py`) — a table needs a query and columns,
a chart needs a query and chart spec, a metric needs a query,
heading/text need text — so a save attempt fails here with a clear
message instead of an opaque 400 from the API. There is **no live
preview and no chart-rendering in the browser**: sections render
server-side only, and the only way to see real rendered output is to
generate and download/open an export (§10's own instruction: "do not
attempt to recreate server-side document rendering in the browser").
No chart library was added as a dependency (§45) — none was needed,
since nothing renders a chart client-side.

A new template version always starts as a new `draft`
(`POST /reports/templates/{id}/versions`) and replaces the whole
document atomically — there is no partial "update one section"
endpoint, so `TemplateNewVersionForm` always submits the complete,
edited `ReportDefinition` plus the complete parameter list.

## Generation and the "latest result" pattern

Because there is no `GET /reports/{id}/executions` (confirmed absent —
see the limitations doc), a generation's `execution`/`exports` are
only ever visible in the single `GenerateResponse` returned by the
`POST /reports/generate` call itself. `ReportDetailView` keeps this in
local component state (`useState<GenerateResult | null>`), not
`useQuery` — there is nothing to re-fetch. `GenerationResult` renders
it, including a real, visible warning for `degradedSections` (§13's
own reasoning: never silently deliver an incomplete report).

## Export-level actions

Each export artifact in a `GenerationResult` gets its own action row:
Download (always), and — gated behind `can("export")` — Archive
(`ArchiveExportDialog`), Share (`ShareExportDialog`, which mints and
displays a one-time token), and Distribute (`DistributeExportDialog`,
an ad-hoc one-off delivery distinct from a standing recipient
subscription).

## Permission handling

Same mechanism as Monitoring/Alerting: every section's `SectionState`
shows `AccessDeniedState` for a 403. Mutation buttons are gated by the
coarse role capability model, mapped onto the closest of the 9 real
actions since none of "generate"/"schedule"/"distribute" exist in that
vocabulary: Generate/schedule management → `execute`; Edit report →
`update`; Delete report/purge archive → `delete`; Archive-export/
share/distribute/recipient management → `export`; Template approval →
`approve` (the one action in the vocabulary that maps exactly).

## Error handling

Every section (summary, recent generations, favorites, the reports
table, report detail, schedules, recipients, history, templates,
archive) is its own `useQuery` + `SectionState` — one failing
independently never blanks the rest of the page (§20). A rejected
purge shows the backend's own real message (its retention-policy
reason), not a generic failure — see `PurgeArchiveDialog`.

## Navigation / information architecture

`lib/route-registry.ts`: `reporting` (`/reporting`) is the only entry
shown in the primary sidebar; `reporting-reports`, `reporting-templates`,
`reporting-schedules`, `reporting-history`, `reporting-archive` are
registered `"implemented"` (so the command palette can find them) but
`showInNav: false` — reachable via `ReportingSubNav`, mirroring
Monitoring's and Alerting's own pattern. The dynamic
`/reporting/reports/[id]`, `/reporting/reports/[id]/edit`, and
`/reporting/templates/[id]` routes aren't registered at all (no
meaningful static breadcrumb for a dynamic id) — each renders its own
"Back to…" action instead.

## Dashboard integration

§36 asks to link Dashboard → Reporting "where Dashboard contains
report metrics." It doesn't: the Dashboard's KPI grid
(`OrganizationStatisticsResponse`, Prompt 005) has no report-count
field. No cross-link was added — inventing one without a real metric
to back it would violate the same "don't fabricate" discipline this
whole codebase follows. Reporting is reachable from the primary
sidebar like every other top-level feature.
