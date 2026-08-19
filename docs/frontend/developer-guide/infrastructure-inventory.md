# Infrastructure

The Enterprise Infrastructure Inventory & Asset Management Experience
built in Prompt 011, against `services/inventory-service` — the
authoritative CMDB backend. See `docs/frontend/rfi/infrastructure-inventory.md`
for the implemented-vs-planned split and
`docs/frontend/backend-v1-integration-limitations.md` for every gap
discovered building this — this prompt found the single worst
tenant-isolation gap of the whole session (see below).

## Consolidation: this feature supersedes Monitoring's own asset views

Monitoring (Prompt 006) built a read-only asset list/search/detail
experience against `inventory-service` for health-observability
purposes. This prompt's own instructions ("Monitoring: Asset →
Infrastructure Detail", "do not create competing architecture") and
the genuinely richer real capability set confirmed here — full CRUD,
groups, relationship create/delete, topology, import/export, a much
richer statistics/analytics response — made a straight duplication
indefensible. So `features/infrastructure` became the canonical asset
owner: `assets-api.ts`, `use-asset-search.ts`/`use-asset.ts`,
`AssetTable`/`AssetFilters`/`AssetDetailView`, and both asset pages
were moved out of `features/monitoring` entirely (not left as a thin
re-export shim) and rebuilt here against the full `AssetResponse`
schema (Monitoring's own version had silently dropped
`mac_address`/`serial_number`/`firmware_version`/`architecture`/
`current_version`). `/monitoring/assets` and `/monitoring/assets/[id]`
no longer exist; `/infrastructure/assets` and
`/infrastructure/assets/[id]` are canonical. Monitoring's Overview page
still shows a health summary and a "needs attention" list — both now
import from `features/infrastructure` (`useInventoryStatistics`,
`CriticalIssuesSection`) rather than owning a duplicate copy; the
dependency direction is Monitoring → Infrastructure, never the reverse.

## Real endpoint inventory

Confirmed by direct source inspection of `app/api/*.py` — 23
non-health routes across 8 routers (`asset.py`, `search.py`,
`relationship.py`, `topology.py`, `group.py`, `import_.py`,
`export.py`, `statistics.py`/`analytics.py`), all consumed:

| Router | Routes consumed |
|---|---|
| `asset.py` | `GET /inventory/assets` (unbounded list), `GET/{id}`, `POST`, `PATCH/{id}`, `DELETE/{id}` |
| `search.py` | `GET /inventory/search` (paginated/filtered/sorted) |
| `relationship.py` | `GET ?asset_id=`, `POST`, `DELETE/{id}` |
| `topology.py` | `GET ?asset_id=&query_kind=neighbors\|dependencies\|impact&depth=` |
| `group.py` | `GET`, `POST`, `GET/{id}/members` |
| `import_.py` | `POST` (multipart), `GET/{id}`, `POST/{id}/rollback` |
| `export.py` | `POST`, `GET/{id}` |
| `statistics.py`/`analytics.py` | `GET /inventory/statistics`, `GET /inventory/analytics` |

**Not consumed, and why**: `PUT /inventory/assets/{id}` (full-replace,
see "PATCH, never PUT" below); `POST /inventory/tools/execute`-style
direct actions don't exist here, but the analogous
`DELETE /inventory/groups/{id}` and add/remove-member routes are
**confirmed absent** — the service methods (`AssetGroupService.delete`/
`.add_member`/`.remove_member`) exist but no route calls them, so
groups are create/list/view-members only in this UI, matching the
backend's own actual surface.

## Real CRUD, not fabricated

Unlike almost every other inventory-style module found this session,
`inventory-service` genuinely supports `POST`/`PATCH`/`DELETE` on
assets and `POST`/`DELETE` on relationships. `AssetCreateForm`,
`AssetEditForm`, `AssetActions`, and `AssetRelationshipsSection` are
real mutations, not a read-only view dressed up — confirmed via direct
source inspection of `app/api/asset.py`/`relationship.py`, not
inferred from the service being called "inventory."

## PATCH, never PUT

`AssetUpdateRequest` (`PUT`) gives every field a server-side default
(`status`→`discovered`, `health`→`unknown`, `criticality`→`medium`,
...) — the same "PUT status trap" shape found in `automation-service`'s
job-update route (Prompt 009): omitting a field on `PUT` silently
resets it, it doesn't leave it unchanged. `AssetPatchRequest` (`PATCH`)
uses `model_dump(exclude_unset=True)` and the route itself reads the
current row first to fill in anything the patch doesn't specify
(confirmed: `app/api/asset.py#patch_asset` calls `assets.get_by_id`
before merging) — a genuine, safe partial update. `AssetEditForm`
pre-fills every field from the current asset and only ever calls
`assetsApi.patch`; `PUT` is never called anywhere in this feature.
Neither route can change `assetType` or `tags` (confirmed absent from
both request schemas) — the edit form doesn't offer them.

## Relationship directionality

`AssetRelationship` is a directed edge — `RelationshipType` values
(`runs_on`, `depends_on`, `hosted_by`, ...) are inherently directional,
source-to-target. But `GET /inventory/relationships?asset_id=` is
bidirectional in its *lookup* (confirmed: the repository queries
`source_asset_id = :id OR target_asset_id = :id`), so the raw response
doesn't say which side the asset in view is on.
`lib/relationship-direction.ts#resolveRelationshipNeighbor` resolves
this once, centrally, rather than each caller re-deriving it — a
subtlety Monitoring's own prior read-only view got wrong (it always
linked to `targetAssetId`, correct only when the viewed asset happened
to be the source).

## Topology, not a graph

`GET /inventory/topology` is real (neighbors/dependencies/impact
traversal, computed server-side against a Neo4j-backed graph), but
§15/§53 explicitly ask for a structured list rather than a graph
visualization unless the feature genuinely needs one, and forbid
adding a graph library for one view. `TopologySection` renders the
three query kinds as tabs over a plain list — no new dependency.

## Sensitive metadata masking

`Asset.metadata` is a genuinely free-form `dict[str, Any]` — confirmed
by source inspection, no dedicated credential field exists anywhere in
this service, but nothing stops a caller from putting one in this dict
either. `lib/sensitive-metadata.ts` masks any metadata value whose
*key* matches a password/secret/token/api-key/credential pattern,
purely in the presentation layer — a name-based heuristic, not a
backend guarantee.

## Import/export architecture

Both are real, async, job-based (`202` + queue message), polled via
`useExportJob`/`useImportJob` (3s interval while non-terminal, stopped
at a terminal `shared_core.enums.job_status.JobStatus` — 13 values,
unrelated to `features/automation`'s own local 4-value job-status
enum despite the shared name). Export's `download_url` is a presigned
link, opened directly rather than routed through `apiClient` — it's
already self-authenticating. Import needs a real
`multipart/form-data` body, which `@/api/client` doesn't support
(confirmed: it always serializes as JSON) — `lib/multipart-fetch.ts`
is a small, separate fetch path mirroring `features/reporting/lib/binary-fetch.ts`'s
own precedent for the same class of problem (a route whose body/response
shape `apiClient` can't handle). `organization_id`/`source_format`/
`preview_only` are real query params on the import route, not
multipart fields — only `file` is.

## The worst tenant-isolation gap found this session

Confirmed by direct source inspection: **every by-id route in this
service has no `organization_id` parameter of any kind** —
`GET/PATCH/DELETE /inventory/assets/{id}`, `GET/DELETE /inventory/relationships/{id}`,
`GET /inventory/groups/{id}/members`, `GET /inventory/topology`,
`GET/POST /inventory/import/{id}`, `GET /inventory/export/{id}` all
resolve purely by primary key. `shared_core.database.tenant.enforce_tenant_match`
exists specifically for this "defense in depth for entities fetched by
ID" case — its own docstring describes this exact scenario — but is
never called anywhere in `inventory-service`. Separately, every *list*
route (`GET /inventory/assets`, `/search`, `/statistics`, `/analytics`,
`/groups`) takes `organization_id` as a client-supplied parameter with
no cross-check against the caller's own identity — `BaseRepository`'s
`tenant_scope` mechanism exists and is used elsewhere in the platform,
but every repository in this service is constructed with
`tenant_scope=None` (confirmed: none of the 23+ `AssetRepository(...)`-style
call sites in `app/api/deps.py` pass one). Net effect: any
authenticated user, from any organization, can read or mutate any
other organization's assets, relationships, groups, or import/export
jobs by ID. This frontend still always sends the real, currently
selected `organization_id` on every list call and fabricates no
client-side tenant check the backend doesn't enforce.

## Permission handling

Same mechanism as every prior feature: the coarse role capability
model, mapped onto the closest of the 9 real `PermissionAction`
values since this service defines none of its own — create/register →
`create`; edit → `update`; delete → `delete`; export → `export`;
import → `import`. `inventory-service` performs no real permission
check on any route (every route depends only on decoding a valid JWT)
— this is a UX convenience only, layered on top of the tenant-isolation
gap above.

## Navigation / information architecture

`lib/route-registry.ts`: the pre-existing `"inventory"` `planned()`
stub (navGroup `"platform"`, matching `docs/frontend/backend-feature-matrix.md`'s
own `features/inventory` mapping) is promoted to a 3-entry
`implemented()` family — `infrastructure` (root, shown in the primary
sidebar), `infrastructure-assets`, `infrastructure-groups` (both
`showInNav: false`, reachable via `InfrastructureSubNav`). `id`/`path`
use "infrastructure" for the UX-facing name (matching the prompt's own
explicit `/infrastructure` route requirement) while `feature: "inventory"`
is kept for backend-mapping traceability — the same split Prompt 010
established for `"ai-assistant"`/`"intelligence"`. The separate,
still-`planned()` `"assets"` stub (`services/asset-management-service`,
doc 038 — ownership/warranty/contracts/compliance/cost) is a different
backend service entirely and was left untouched; nothing here maps to
it. Dynamic `/infrastructure/assets/[id]` and `/[id]/edit` aren't
registered (flat registry, no meaningful static breadcrumb for a
dynamic id) — each page renders its own "Back to…" action instead.

## Cross-module integration

- **Dashboard**: the Overview KPI grid's "Assets" tile now links to
  `/infrastructure/assets` (previously `/monitoring/assets`) — no
  duplicate inventory query added to Dashboard itself.
- **Monitoring**: `HealthSummary`/`CriticalIssuesSection` both import
  from this feature (see Consolidation, above) rather than the reverse.
- **Alerting / Automation**: confirmed absent — no field on `Asset` or
  any relationship references an alert or an automation job/target in
  either direction, and neither `alerting-service` nor
  `automation-service` calls `inventory-service`'s `InventoryClient`
  from any reachable route (both have one, both are dead code — see
  `backend-v1-integration-limitations.md`). No cross-link was built.
- **AI Assistant**: `AskAiButton` on `AssetDetailView`, same pattern as
  every other module — a plain-text draft naming the real asset,
  never a fabricated structured context payload.

## Error handling

Every section (statistics, critical issues, asset table, asset detail,
relationships, topology, groups, group members, export/import job
status) is its own `useQuery` + `SectionState` — one section failing
never blanks the rest of the page (§35/§42).
