# Monitoring

The Monitoring & Observability feature built in Prompt 006, on top of
the Dashboard's `organization/` context (Prompt 005) and the
application shell (Prompt 003). See
`docs/frontend/rfi/monitoring.md` for the implemented-vs-planned split
and `docs/frontend/backend-v1-integration-limitations.md` for every
gap discovered building this.

**Consolidation (Prompt 011)**: asset list/search/detail/relationships
— originally built here — moved to `features/infrastructure`, which
now owns all `inventory-service` asset-fetching (including real CRUD
this feature never had). See
`docs/frontend/developer-guide/infrastructure-inventory.md`
"Consolidation" for the full reasoning. What remains genuinely
Monitoring's own: the Overview's health rollup (still reads
`inventory-service`, just through `features/infrastructure`'s own API
now) and service-topology/event visibility, which never had an
inventory-asset equivalent to begin with.

## Feature structure

```
features/monitoring/
├── api/            services-api.ts, events-api.ts
├── hooks/          one useQuery wrapper per api module
├── components/     MonitoringSubNav, HealthSummary, ServiceHealthList,
│                    EventTimeline
├── types/          response types mirroring the real V1 schemas
│                    (service-topology/event types only — asset types
│                    moved to features/infrastructure)
├── lib/            status-maps.ts — service/event enum → StatusState
│                    mappings (asset-health mapping moved too)
└── pages/          monitoring-overview-page.tsx, monitoring-services-page.tsx,
                     monitoring-events-page.tsx
```

`HealthSummary` and the Overview's "Critical issues" section
(`features/infrastructure/components/critical-issues-section.tsx`) both
import from `features/infrastructure` rather than owning their own copy
of asset-fetching — the dependency direction is intentionally
Monitoring → Infrastructure, not the reverse, since Infrastructure is
the canonical asset owner.

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

## Query architecture

Each hook takes the parameters it needs (`organizationId`, an asset
id) and sets `enabled: false` until they're available — matching the
Dashboard's established pattern. Asset-search/filter/sort/table/detail
architecture now lives in
`docs/frontend/developer-guide/infrastructure-inventory.md`.

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
events) is its own `useQuery` + `SectionState` — one failing
independently never blanks the rest of the page (§20), matching
Dashboard's established pattern exactly.

## Performance decisions

- `CriticalIssuesSection` (now in `features/infrastructure`) intentionally
  scans only one bounded page (100 items, sorted newest-updated) rather
  than the full asset list, since `/inventory/search` has no `health`
  filter param to do this server-side — documented in the component's
  own comment and in `backend-v1-integration-limitations.md`.
- No virtualization: the events/services lists this feature still owns
  are small enough that it isn't justified yet (§30: "virtualization
  where genuinely needed").

## Navigation / information architecture

`lib/route-registry.ts`: `monitoring` (path `/monitoring`) is the only
entry shown in the primary sidebar; `monitoring-services`,
`monitoring-events` are registered `"implemented"` (so the command
palette can find them) but `showInNav: false` — reachable via
`MonitoringSubNav` (real `<Link>`s, not the ARIA `Tabs` widget, since
these are distinct shareable routes) instead of a fourth sidebar
nesting level the shell doesn't support. The former `monitoring-assets`
entry was removed when Assets moved to `/infrastructure/assets`
(Prompt 011) — see `lib/route-registry.ts`'s own `infrastructure*`
entries.

## Dashboard integration

`features/dashboard/pages/dashboard-page.tsx`'s "Operational health"
and "System status" section headings carry a `viewAllHref` ("View in
Monitoring") pointing at `/monitoring` and `/monitoring/services`
respectively. The Overview KPI grid's "Assets" tile now links to
`/infrastructure/assets` (updated in Prompt 011 alongside the
consolidation) rather than the removed `/monitoring/assets`.
