# Infrastructure

Per Prompt 011 §59, this honestly separates **IMPLEMENTED** from
**PLANNED**/**UNAVAILABLE** for the Enterprise Infrastructure Inventory
& Asset Management Experience. Nothing here claims future functionality
as currently available. See `../rfi/README.md` and the prior per-feature
RFI docs (`dashboard.md`, `monitoring.md`, `alerting.md`, `reporting.md`,
`automation.md`, `ai-assistant.md`) for the foundation this builds on.

## Enterprise asset inventory — IMPLEMENTED

A real, searchable, filterable, sortable, paginated inventory
(`GET /inventory/search`) plus a real, structured detail view — 23 of
23 real `inventory-service` routes consumed across asset CRUD, search,
relationships, topology, groups, import/export, and statistics/analytics.
Supersedes Monitoring's own narrower, read-only asset views (Prompt
006) — see `../developer-guide/infrastructure-inventory.md`
"Consolidation" for why, and for the full endpoint inventory.

## Scalable asset discovery — IMPLEMENTED

Real server-side pagination/filtering/search — never loads a complete
inventory into the browser (§7). Sorting maps directly onto the
backend's own `sort=field:asc|desc` syntax, confirmed server-side
(`apply_sorting` on the SQL statement itself, not client
post-processing).

## Real asset lifecycle management — IMPLEMENTED

Create, edit (via `PATCH`, never the reset-prone `PUT` — see the
developer guide), and soft-delete are all real, confirmed backend
operations (§21), not fabricated because "this is an inventory
module." Status is an ordinary editable field rather than a dedicated
enable/disable action, since no such route exists.

## Relationships and topology — IMPLEMENTED (structured, not a graph)

Relationship create/list/delete are real routes; topology
(neighbors/dependencies/impact) is a real, server-computed traversal.
Rendered as structured lists rather than a graph visualization — §15
explicitly permits this when graph UX isn't appropriate, and §53
forbids adding a graph-rendering dependency for one view.

## Groups — IMPLEMENTED (create/list/view-members only)

`GET`/`POST /inventory/groups` and `GET /inventory/groups/{id}/members`
are real. **Confirmed absent**: no delete route, no add/remove-member
route — the backend service methods exist, nothing routes to them. A
group's membership is fixed at creation time in this UI, honestly
matching what's reachable.

## Import / export — IMPLEMENTED (real, async, job-based)

Both `POST /inventory/import` (multipart upload, with Preview and
Rollback — §26) and `POST /inventory/export` (§25) are real, queued
background jobs, polled to completion — never a fake client-side CSV
dump of the currently loaded page.

## Metadata presentation and sensitive-value masking — IMPLEMENTED

Key/value metadata display (§16) with a name-based mask (§17) applied
to any key that looks like a password/token/API key/credential,
regardless of its actual content — a presentation-layer safeguard, not
a backend guarantee (the backend has no dedicated secret field to
guarantee anything about).

## Permission-aware access — IMPLEMENTED (mechanism, mapped onto the existing 9-action vocabulary)

Every mutation (create/update/delete/export/import) is gated by the
coarse role capability model (§25), mapped onto the closest of the
platform's 9 real actions since `inventory-service` defines no
resource-specific verbs of its own. The service enforces no permission
check on any route today (see Backend V1 limitations) — this is a UX
convenience only.

## Responsive UX — IMPLEMENTED

The asset table renders as a real `<table>` at `md`+ and a stacked
card list below it (§43), matching the established pattern from
Monitoring/Alerting/Reporting/Automation/AI Assistant.

## Accessibility — IMPLEMENTED (foundation, unchanged this prompt)

Built entirely on already-accessible primitives (`StatusBadge`/
`StatusIndicator`, `Dialog`, `Drawer`, `EmptyState`, `SectionState`,
native `<table>`/`<select>`/`<input>`/`<textarea>`) — no new bespoke
interactive pattern requiring dedicated accessibility work.

## Extensibility — IMPLEMENTED (foundation)

`Page → Hook → API module → apiClient → real V1 endpoint` (§30),
strict TypeScript with no field-mismatch-bypassing `any` (§31), and a
query-key scheme that invalidates cleanly after every mutation (§33) —
the same architecture pattern every prior feature this session
established, applied consistently here.

## Cross-module integration — IMPLEMENTED where a real relationship exists, N/A otherwise

Dashboard's KPI tile and Monitoring's health rollup both link into
this feature; AI Assistant's "Ask AI" is wired from asset detail.
**No Alerting or Automation cross-link**: §12/§13/§36/§37 ask for these
"if V1 exposes the relationship" — confirmed absent in either
direction (no field on `Asset` references an alert or automation
target, and neither service's own dead `InventoryClient` is ever
called by a live route). Nothing was fabricated.

## Related alerts / Related automation — UNAVAILABLE (documented, not implemented)

See above — no real V1 relationship exists to build either section
against.

## Tenant isolation — the worst gap found this session (documented, not fixed)

Every by-id route in `inventory-service` — asset, relationship, group
member, topology, import/export job — applies **no organization
filter of any kind**, and every list route trusts a client-supplied
`organization_id` with no cross-check against the caller's identity.
This is a backend defect, out of scope to fix under the V1 freeze;
this frontend always sends the real, currently-selected organization
on every call and fabricates no client-side tenant check the backend
doesn't itself enforce. Full citation in
`../backend-v1-integration-limitations.md`.

## Category/class/location/owner names — UNAVAILABLE (documented, not implemented)

`category_id`/`class_id`/`location_id`/`owner_id` are shown as raw IDs
— no name-resolution endpoint exists for any of the four, despite full
service/repository code existing behind the scenes for each. Inherited
from Monitoring's own prior finding, reconfirmed here.

## Partial failure handling — IMPLEMENTED

Every section (statistics, critical issues, asset table, asset detail,
relationships, topology, groups, group members, export/import status)
fails independently — one unavailable piece of data degrades only its
own section, never the whole page (§42).

See `../backend-v1-integration-limitations.md` for the full,
cross-prompt list with source citations.
