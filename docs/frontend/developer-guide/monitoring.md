# Monitoring

The Monitoring & Observability feature built in Prompt 006, on top of
the Dashboard's `organization/` context (Prompt 005) and the
application shell (Prompt 003). See
`docs/frontend/rfi/monitoring.md` for the implemented-vs-planned split
and `docs/frontend/backend-v1-integration-limitations.md` for every
gap discovered building this.

## Feature structure

```
features/monitoring/
├── api/            assets-api.ts, services-api.ts, events-api.ts
├── hooks/          one useQuery wrapper per api module
├── components/     MonitoringSubNav, HealthSummary, CriticalIssuesSection,
│                    AssetFilters, AssetTable, AssetDetailView,
│                    ServiceHealthList, EventTimeline
├── types/          response types mirroring the real V1 schemas
├── lib/            status-maps.ts — enum → StatusState mappings
└── pages/          monitoring-overview-page.tsx, monitoring-assets-page.tsx,
                     monitoring-asset-detail-page.tsx, monitoring-services-page.tsx,
                     monitoring-events-page.tsx
```

Follows §27's flow: `Page → Hook → API module → apiClient → real V1 endpoint`.

## Three services, three different "health"/org-scoping models

This feature is unusual among AI-IOS features in that it pulls from
**three separate backend services with three different conventions** —
confirmed by direct source inspection, not assumed to be consistent:

| Service | Org scoping | "Health" enum | Used for |
|---|---|---|---|
| `inventory-service` | `organization_id` query param, client-supplied | `HealthStatus` (6 values: `healthy, warning, critical, unknown, offline, unreachable`) — **local to this service** | Assets, asset detail, relationships |
| `observability-platform-service` | Resolved **server-side** from the caller's session (`Depends(get_organization_id)`) — passing `organization_id` explicitly does nothing | `NodeHealth` (4 values: `healthy, degraded, unhealthy, unknown`) on topology; no health concept on events | Service topology, events |
| `api-gateway-service` (via Dashboard, Prompt 005) | `organization_id` query param | `HealthState`/`shared_core.HealthStatus` (6 values, different from inventory's) | Dashboard's health overview/system status only — not used directly by this feature |

**Do not conflate the three health enums** — `features/monitoring/lib/status-maps.ts`
keeps each mapped to the canonical `StatusState` taxonomy
(`@/lib/status`) independently, with its own comment explaining why.
`services-api.ts`/`events-api.ts` deliberately never send an
`organization_id` query param, unlike every other API module in this
feature — their own module docstrings explain why.

## Asset search vs. asset list

`GET /inventory/assets` (list, unbounded, org-scoped, no
filter/sort/pagination) and `GET /inventory/search` (paginated,
filtered by `status`/`asset_type`/`q`, sorted) are two different real
endpoints. This feature uses **only** `/inventory/search` — never the
plain list endpoint — since every table/filter/pagination requirement
(§6/§14/§15/§16) needs the search endpoint's capabilities. `assets-api.ts#search`
wraps it directly.

## Query architecture

Each hook takes the parameters it needs (`organizationId`, search
params, an asset id) and sets `enabled: false` until they're
available — matching the Dashboard's established pattern. `useAssetSearch`
additionally uses `placeholderData: keepPreviousData` so paginating or
changing a filter doesn't flash the whole table to a skeleton (§32/§35).

Query keys include every parameter that affects the result
(`["monitoring", "assets", "search", params]`) so two different
filter/sort/page combinations never collide in the cache.

## Filter model

`AssetFilters` is a controlled component — `MonitoringAssetsPage` owns
the actual state, synced to the URL (`?q=&status=&type=&sort=&dir=&page=`)
via `next/navigation`'s `useSearchParams`/`useRouter` (§14: "URL/share-link
friendly," "preserve state on navigation"). Sorting maps directly onto
`GET /inventory/search`'s own `sort=field:asc|desc` syntax — confirmed
by reading `packages/shared-core/.../sorting.py`'s `parse_sort_expression`,
not guessed at.

Table density (`state/table-density-store.ts`) is a separate, shared
(not monitoring-specific) persisted preference — any future dense
table in the app should reuse it rather than inventing its own.

## Table architecture

`AssetTable` renders a real `<table>` at `md`+ and a stacked card list
below it (§32) from the *same* data and props — no separate mobile
data-fetching path. Columns are exactly the fields `AssetResponse`
actually has; there's deliberately no "Last Seen" column (confirmed no
such field exists on the schema — only `created_at`/`updated_at`).

## Detail architecture

`MonitoringAssetDetailPage` → `useAsset(id)` → `GET /inventory/assets/{id}`
(confirmed to return the identical `AssetResponse` shape as the list/search
endpoints — no richer "detail" schema exists). `AssetDetailView` composes
Identity → Current Health → Metadata → Related Assets, per §8's own
hierarchy. Related assets come from `GET /inventory/relationships?asset_id=...`
(a flat, one-hop edge list) — target asset names aren't resolved (would
require an extra fetch per relationship); the target id itself is a
real, working link to that asset's own detail page instead.

No Events or Metrics section on Asset Detail — see Backend V1
limitations below.

## Chart architecture

**None exists.** No chart library is a dependency of this repository,
and this prompt didn't introduce one (§44: "prefer existing
dependencies... do not add a chart library"). See "Metrics" under
Backend V1 limitations for why a metrics/chart experience wasn't built
at all this prompt, rather than built against guessed-at data.

## Permission handling

Same mechanism as Dashboard (Prompt 005): every section's `SectionState`
(reused from `@/features/dashboard/components/section-state`, not
reimplemented) shows `AccessDeniedState` for a 403, distinct from a
generic retryable error.

## Error handling

Every section (health summary, critical issues, service health,
events, the asset table, asset detail, related assets) is its own
`useQuery` + `SectionState` — one failing independently never blanks
the rest of the page (§20), matching Dashboard's established pattern
exactly.

## Performance decisions

- Real server-side pagination/filtering/search (`GET /inventory/search`) —
  never fetches more than one page of assets for the table.
- `CriticalIssuesSection` intentionally scans only one bounded page
  (100 items, sorted newest-updated) rather than the full asset list,
  since `/inventory/search` has no `health` filter param to do this
  server-side — documented in the component's own comment and in
  `backend-v1-integration-limitations.md`.
- No virtualization: page sizes (25 for the table, 100 for the
  critical-issues scan) are small enough that it isn't justified yet
  (§30: "virtualization where genuinely needed").
- `useAssetSearch`'s `keepPreviousData` avoids a full-page loading
  flash on every filter/sort/page change.

## Navigation / information architecture

`lib/route-registry.ts`: `monitoring` (path `/monitoring`) is the only
entry shown in the primary sidebar; `monitoring-assets`,
`monitoring-services`, `monitoring-events` are registered
`"implemented"` (so the command palette can find them) but
`showInNav: false` — reachable via `MonitoringSubNav` (real `<Link>`s,
not the ARIA `Tabs` widget, since these are distinct shareable routes)
instead of a fourth sidebar nesting level the shell doesn't support.
The dynamic `/monitoring/assets/[id]` route isn't registered at all
(the registry is flat/static; a dynamic id has no meaningful static
breadcrumb) — its page renders its own "Back to Assets" action
instead.

## Dashboard integration

`features/dashboard/pages/dashboard-page.tsx`'s "Operational health"
and "System status" section headings now carry a `viewAllHref`
("View in Monitoring") pointing at `/monitoring` and
`/monitoring/services` respectively; the Overview KPI grid's "Assets"
tile links to `/monitoring/assets`. All three were left unlinked in
Prompt 005 specifically because Monitoring didn't exist yet — see that
prompt's own "known limitations."
