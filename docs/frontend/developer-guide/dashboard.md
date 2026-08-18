# Dashboard

The first real business feature (Prompt 005), replacing the
`modules/dashboard/` placeholder. See
`docs/frontend/rfi/dashboard.md` for the implemented-vs-planned split
and `docs/frontend/backend-v1-integration-limitations.md` for every
backend gap this prompt discovered.

## Why an `organization/` module exists

Almost every real V1 endpoint this dashboard needs (alerts, assets,
automation, reports, org analytics — confirmed by direct source
inspection of `services/alerting-service`, `services/automation-service`,
`services/organization-service`, `services/api-gateway-service`)
requires `organization_id` as a required parameter. The current login
contract doesn't populate an `organization_id` JWT claim (the
documented gap in `auth/types.ts`), so the frontend had no way to
supply one — until now.

`GET /organizations` itself needs only auth, no `organization_id`. The
`organization/` module (a foundation module, sibling to `auth/` and
`permissions/`, not a `features/` business module — every future
org-scoped feature will need it too) uses that to let the user pick
which organization's data to see:

```
organization/
├── api.ts                    organizationApi.list(), .fetchStatistics(id)
├── types.ts                  Organization, OrganizationStatistics
├── store.ts                  useOrganizationStore — persisted selectedOrganizationId
├── use-organizations.ts      useOrganizations(), useSelectedOrganization()
└── index.ts
```

`useSelectedOrganization()` auto-selects when there's exactly one
organization, otherwise leaves the selection `null` and sets
`needsSelection: true` so the caller renders `OrganizationPicker`. A
stored selection that's no longer in the user's organization list
(e.g. access was revoked) is treated as invalid, not trusted blindly.

## Dashboard architecture

```
features/dashboard/
├── api/              alerts-api.ts, automation-api.ts,
│                      gateway-health-api.ts, gateway-liveness-api.ts
├── hooks/             one useQuery wrapper per api module
├── components/         MetricCard, SectionState, OrganizationPicker,
│                        KpiGrid, HealthOverviewSection,
│                        AttentionRequiredSection, RecentActivitySection,
│                        SystemStatusSection, GatewayLivenessCard
├── types/              response types mirroring the real V1 schemas
└── pages/
    └── dashboard-page.tsx   composes everything, rendered by app/(app)/page.tsx
```

Follows §27's required flow throughout:
`Page → Hook (useQuery) → API module (snake_case→camelCase mapping) → apiClient → real V1 endpoint`.
No component calls `fetch()` directly; no second API client.

## Query structure / API modules

Each `api/*.ts` module is a thin, typed wrapper: request the real
endpoint, map its snake_case response body to a camelCase domain type
(mirroring `auth/api.ts`'s established pattern). Each has exactly one
`hooks/use-*.ts` `useQuery` wrapper. Org-scoped hooks (`useAlerts`,
`useAutomationExecutions`, `useGatewayHealth`, `useOrganizationStatistics`)
take `organizationId: string | null` and set `enabled: organizationId !== null`
— they simply don't fire until an organization is resolved.
`useGatewayLiveness` is the one exception: `GET /health` needs no
organization context at all (migrated verbatim from
`modules/dashboard`).

Query keys include the organization id (e.g. `["alerts", organizationId]`)
so switching organizations doesn't show stale data from the previous
one. `HealthOverviewSection` and `SystemStatusSection` both call
`useGatewayHealth` with the same key — TanStack Query dedupes this to
one request.

## Component structure

`SectionState` (`components/section-state.tsx`) is the one shared
loading/error/permission wrapper every data-driven section uses —
loading → `Skeleton`, a 403 → `AccessDeniedState`, any other error →
`ErrorState` with retry. Empty-vs-populated is left to each section's
own render, since "no alerts" and "no registered services" need
different copy (Prompt 005 §18).

`MetricCard` deliberately has no trend/change prop — see §7 in the RFI
doc for why. `StatusIndicator` (Prompt 002/003) is reused for every
named operational state; `Alert.severity` and `AlertStatus` are
rendered via a locally-scoped tone map instead, since severity is a
different taxonomy axis than operational health.

## State management

No dashboard-specific Zustand store beyond `organization/store.ts`'s
`selectedOrganizationId` (a genuine client preference, not server
data — §29 explicitly says not to create global state for server
data). Everything else is TanStack Query.

## Caching

`staleTime` set per data type's actual volatility: 60s for
organization statistics (slow-changing counts), 30s for alerts/health/
executions (more time-sensitive), 5 minutes for the organization list
itself (rarely changes). `useGatewayHealth`/`useGatewayLiveness` also
set `refetchInterval` for background polling; nothing else does —
per §15, polling is deliberately not applied where it isn't
justified.

The header's refresh button calls `queryClient.invalidateQueries()`
(everything) rather than section-by-section, since it's a manual,
infrequent user action where simplicity matters more than the
marginal efficiency of a targeted invalidation.

## Permission handling

Every section's `SectionState` distinguishes a 403 (`AccessDeniedState`,
"Access denied") from any other failure (`ErrorState` with Retry) —
the meaningful, honest form of "permission-aware dashboard" available
today, since the coarse role model (`permissions/capabilities.ts`)
gives every role at least `read`, so client-side hiding-by-role isn't
a real distinction for a read-only page. If the backend ever returns
403 for a section (e.g. a role restriction enforced server-side), the
user sees why, not a generic failure.

## Error handling

Every section fails independently (§16/§19) — one section's query
failing never blanks the rest of the page, since each is its own
`useQuery` + `SectionState`, not a single combined fetch.
`ApiRequestError` status ≥500 gets a generic "temporarily unavailable"
message (never a raw backend message); anything else shows the
backend's own (already-safe, per the API's own error envelope)
message.

## Extension guidelines

- **New KPI**: if it's on `OrganizationStatisticsResponse`, add a
  `MetricCard` to `KpiGrid`. If it needs a new endpoint, add an
  `api/*.ts` module + `hooks/use-*.ts` following the existing pattern
  exactly — confirm the real endpoint and field names by source
  inspection first, never infer from a service's name (Prompt 005 §2).
- **New section**: a new `components/*-section.tsx` using `SectionState`,
  added to `dashboard-page.tsx` at the appropriate information-hierarchy
  level (§5) — don't give it equal visual weight to Overview/Operational
  Health without a real reason to.
- **A metric/section the backend doesn't support yet**: don't build it.
  Document it in `backend-v1-integration-limitations.md` instead.
- **Quick actions / click-through navigation**: only ever link to a
  route registered as `"implemented"` in `lib/route-registry.ts` — as
  of this prompt, that's still only Dashboard and the design-system
  showcase, so no dashboard tile links anywhere yet. Add the link once
  the target feature page actually ships.
