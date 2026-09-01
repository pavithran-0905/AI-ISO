# Dashboard

Built in Prompt 005 (the original page, replacing the
`modules/dashboard/` placeholder) and evolved into the full Executive
Command Center in Prompt 020. Prompt 020 is an orchestration layer
only (§2): every widget it adds is a thin consumer of a feature query/
component this codebase already built for its own page — never a
second, dashboard-owned implementation of any of them. See
`docs/frontend/rfi/dashboard.md` for the implemented-vs-planned split
and `docs/frontend/backend-v1-integration-limitations.md` for the full
gap list with citations.

## Canonical route, unchanged

Still `/` (`app/(app)/page.tsx` → `DashboardPage`), per §4 — no second
route was ever created.

## Why an `organization/` module exists

Almost every real V1 endpoint this dashboard needs (alerts, assets,
automation, reports, org analytics — confirmed by direct source
inspection of `services/alerting-service`, `services/automation-service`,
`services/organization-service`, `services/api-gateway-service`)
requires `organization_id` as a required parameter. The current login
contract doesn't populate an `organization_id` JWT claim (the
documented gap in `auth/types.ts`), so the frontend has no way to
supply one from the token alone.

`GET /organizations` itself needs only auth, no `organization_id`. The
`organization/` module (a foundation module, sibling to `auth/` and
`permissions/`, not a `features/` business module — every org-scoped
feature needs it) uses that to let the user pick which organization's
data to see. `useSelectedOrganization()` auto-selects when there's
exactly one organization, otherwise leaves the selection `null` and
sets `needsSelection: true` so the caller renders `OrganizationPicker`.
A stored selection no longer in the user's organization list (e.g.
access was revoked) is treated as invalid, not trusted blindly.

## Directory structure

```
features/dashboard/
├── api/               alerts-api.ts, automation-api.ts,
│                       gateway-health-api.ts, gateway-liveness-api.ts
├── hooks/              use-gateway-health.ts, use-gateway-liveness.ts,
│                       use-organization-statistics.ts
├── lib/                asset-health.ts, widget-registry.ts
├── components/
│   ├── metric-card.tsx, section-state.tsx, organization-picker.tsx
│   ├── kpi-grid.tsx, health-overview-section.tsx,
│   │   attention-required-section.tsx, recent-activity-section.tsx,
│   │   system-status-section.tsx, gateway-liveness-card.tsx
│   │                    (foundational, Prompt 005 — unchanged)
│   ├── dashboard-widget.tsx, distribution-bar.tsx
│   │                    (the widget shell + visualization, Prompt 020)
│   ├── asset-health-section.tsx, quick-access-grid.tsx
│   │                    (foundational, Prompt 020)
│   ├── recent activity → reuses `features/operations/components/
│   │   recent-activity-timeline.tsx` directly, no new component
│   ├── infrastructure-overview-widget.tsx, reporting-status-widget.tsx,
│   │   notification-summary-widget.tsx, ai-insight-widget.tsx,
│   │   operations-signals-widget.tsx
│   │                    (optional, registry-driven, Prompt 020)
│   └── dashboard-mode-tabs.tsx, dashboard-customize-menu.tsx
│                        (mode switch + personalization UI, Prompt 020)
├── types/              response types mirroring the real V1 schemas
└── pages/
    └── dashboard-page.tsx   composes everything, rendered by app/(app)/page.tsx

state/dashboard-preferences-store.ts   localStorage-only mode/visibility prefs
```

Follows §35's required flow throughout:
`Page → Feature Queries → Existing API Modules → Backend V1`. No
component calls `fetch()` directly; no second API client, and no
`getDashboardData()` catch-all.

## Six foundational sections, not part of the optional registry

`KpiGrid`, `AssetHealthSection`, `AttentionRequiredSection`,
`RecentActivitySection`, `SystemStatusSection`, and `QuickAccessGrid`
always render in both modes, regardless of personalization. §24/§26
apply to *optional* widgets — making the platform's own primary risk
signals (active alerts, asset health, automation status) hideable
would be a regression, not a feature, so they were deliberately kept
outside `DASHBOARD_WIDGET_REGISTRY`.

## Widget architecture (§25)

`features/dashboard/components/dashboard-widget.tsx` — one `Card` +
title/description/action header + `SectionState`'s own loading/error
handling. Mirrors `components/resource/resource-section.tsx` (Prompt
018) deliberately: both delegate to the same `SectionState`, so there
remains exactly one loading/error implementation in the codebase
(§25), not two. A widget's *empty* state stays its own `children`
concern — matching `SectionState`'s own long-standing precedent (Prompt
005), since "no alerts" and "no reports" need different copy.

## Widget registry (§26)

`features/dashboard/lib/widget-registry.ts` — a typed
`DashboardWidgetDefinition[]` covering the six *optional* widgets:
Recent Activity, Infrastructure, Notifications, Reporting, AI Insight,
Operations Workspace. Each entry's `roles` is read directly from the
canonical route it links into (`getRouteById(id)?.roles`) rather than
a second, hand-picked restriction — if that route ever gains a role
restriction, the widget picks it up automatically instead of silently
drifting out of sync. `filterVisibleWidgets()` is the pure function
that applies mode + role + personalization filtering, extracted
specifically so it's unit-testable with synthetic roles independent of
whether any *currently* registered widget's linked route happens to be
role-restricted — today, Recent Activity's own linked route (`/audit`)
already is, so this is a live, real mechanism, not merely a latent one.

## Every real V1 source consumed, and how each is deduped (§35/§36)

| Widget | Query | Shared with |
|---|---|---|
| Executive Summary | `useOrganizationStatistics` (`GET /organizations/{id}/analytics`) | — |
| Asset Health | `useInventoryStatistics` (`GET /inventory/statistics`) | Infrastructure widget (same `queryKey`) |
| Infrastructure | `useInventoryStatistics` | Asset Health widget |
| Active Alerts | `useAlerts` | Operations Signals widget |
| Automation Status | `useExecutions` | Operations Signals widget |
| System/Operational Health | `useGatewayHealth` | Pre-existing dedup between the two gateway sections (Prompt 005), unchanged |
| Recent Activity | `useAuditEvents("compliance", ...)` (Prompt 015) | Reuses `RecentActivityTimeline` (Prompt 019) directly — no new component |
| Notifications | `useRecentNotifications` | The shell's own notification bell (Prompt 016) |
| Reporting | `useReportingStatistics` (`GET /reports/statistics`) | — |
| AI Insight | `useRecommendations` (`GET /ai/recommendations`) | The Recommendations page, if visited |
| Operations Workspace bridge | `useAlerts` + `useExecutions` | Active Alerts / Automation Status sections — issues **zero** additional requests when those are also on the page |

Every dedup above relies on React Query matching an identical
`queryKey` — the exact mechanism `system-status-section.tsx`'s own
docstring already documents for the pre-existing gateway-health pair.

## Query keys / caching, unchanged principle

Query keys include the organization id (e.g. `["alerts", organizationId]`)
so switching organizations never shows stale data from the previous
one — every Prompt-020 hook follows the same pre-existing convention.
`staleTime` stays set per data type's actual volatility (60s for
slower-changing statistics, 15–30s for more time-sensitive alert/
execution/notification data, 5 minutes for the organization list
itself). `useGatewayHealth`/`useGatewayLiveness`/`useRecentNotifications`
set `refetchInterval` for light background polling; nothing new added
here — per §33, no aggressive polling was introduced.

## Status hierarchy (§9)

Asset Health is the first health-related section on the page, ahead of
the pre-existing gateway-based "Operational health" — §9 explicitly
separates "Asset health" (top priority) from "Service state" (lowest
of the four), and this is the first prompt with a real, org-wide asset
health source (`InventoryStatistics.healthDistribution`) to satisfy
it. "Total Checks"/raw validation counts are never the headline metric
— `KpiGrid`'s "Validations" tile is one KPI tile among six, not a
section of its own.

## Asset Health vs. Operational Health — two real, distinct signals

`AssetHealthSection` (`GET /inventory/statistics`,
`inventory-service`) and `HealthOverviewSection`/`SystemStatusSection`
(`GET /gateway/health`, `api-gateway-service`) measure genuinely
different things — asset-level health vs. gateway-probed service
reachability — and are never merged into one number. Their tone
mappings intentionally differ too:
`features/infrastructure/lib/status-maps.ts#ASSET_HEALTH_TO_STATUS`
for the former,
`features/dashboard/components/health-overview-section.tsx`'s own
local `HEALTH_STATE_TO_STATUS` for the latter (a distinct backend
enum, confirmed by both files' own comments).

## Distribution visualization (§11/§39/§40)

`features/dashboard/components/distribution-bar.tsx` — a horizontal
stacked bar over real counts, zero-value segments omitted. Built with
plain divs and the design system's own tone tokens (`bg-success`,
`bg-danger`, ...) rather than a charting library (§58: "do not add
chart libraries unless genuinely necessary" — a single proportional
bar doesn't need one; this fulfills the "Charts/visualizations" item
Prompt 005's own RFI left PLANNED, once a real, typed dataset — asset
health distribution — existed to build it against). Accessibility
(§40): the bar itself carries one `aria-label` summarizing every
segment, and an unconditional plain-text legend with the same counts
sits below it — the bar is never the only way the data is conveyed.

## Topology Summary — confirmed absent, not merely unbuilt (§19)

No org-wide topology summary/health endpoint exists:
`topologyApi.get()` (`GET /inventory/{assetId}/topology`) requires a
specific `assetId` (`features/infrastructure/hooks/use-topology.ts`) —
confirmed by direct source inspection, there is no
list-every-relationship-for-an-organization route. The one honest,
real, org-wide topology-adjacent number this backend does provide,
`InventoryStatistics.totalRelationships`, is shown inside the
Infrastructure widget instead of as its own thin "Topology" card
(§43: avoid a card for one number), with a direct link into the real
per-asset Topology experience (Prompt 018). The Infrastructure widget
also deliberately does NOT repeat a total-asset-count tile —
`KpiGrid`'s own "Assets" tile already shows that (from
`OrganizationStatistics.assetCount`); a second "Assets" card here,
sourced from a different backend computation
(`InventoryStatistics.totalAssets`), would risk two differently-worded
counts for what looks like the same thing.

## AI Insight — never inline AI-generated content (§21/§48/§49)

No dashboard-summarization endpoint exists on this backend. This card
never renders generated text inline — it shows a real, already-
generated count (`GET /ai/recommendations`, filtered to
`status === "proposed"`) plus `AskAiButton` (Prompt 010's own
established pattern: a pre-filled, never-auto-sent draft, opening a
genuinely separate Assistant conversation). This mirrors Operations
Workspace's own precedent (Prompt 019) of never presenting AI-
generated analysis as confirmed system state. No automatic AI request
is ever made from this card, and the recommendation-count sub-fetch is
isolated from the always-available "Ask AI" action — one failing
independently of the other (§28).

## Attention Required (§13) — three independent real signals, not one fabricated composite

§13 asks for a merged view of critical alerts, unhealthy assets, and
failed automation. Rather than building a single cross-source ranked
list — which would require an invented scoring algorithm across
heterogeneous severities (§13 explicitly forbids exactly that) — this
is satisfied by three adjacent, independently-real widgets instead:
Asset Health's own critical/unreachable counts, Active Alerts'
severity-sorted list, and Automation Status's real per-run status
(including `failed`). Each stays honestly scoped to its own source;
none claims a cross-source priority ranking that doesn't exist.

## Operations Signals (§14) — a bridge, never a second correlation engine

`OperationsSignalsWidget` reuses the exact `useAlerts`/`useExecutions`
queries the Active Alerts and Automation Status sections already fetch
on this same page (identical `queryKey`s — zero additional requests,
§36) purely to derive two counts. All real correlation logic (alert-
to-alert correlation, execution target-ids) stays exclusively inside
Operations Workspace (Prompt 019) — never duplicated here.

## Permission handling

Every section's `SectionState` distinguishes a 403 (`AccessDeniedState`)
from any other failure (`ErrorState` with Retry) — unchanged since
Prompt 005. Prompt 020 adds a second, complementary layer for the
*optional* widgets specifically: `filterVisibleWidgets()` hides a
widget from the page entirely when the caller's role doesn't satisfy
its linked route's `roles` restriction (§27), rather than letting it
render and then 403.

## Personalization (§24)

`state/dashboard-preferences-store.ts` — `localStorage`-only, matching
the exact precedent `useTableDensityStore`/`useRecentSearchesStore`
already established (no backend preference route exists — confirmed
absent). Covers preferred mode (the default before any `?mode=` URL
param) and per-widget visibility. "Density" (§24's third example) is
deliberately not modeled: it only ever meant *table row* density, and
a card-grid dashboard has no equivalent concept to reuse it for.

## Mode is a real, shareable URL param (§51)

`?mode=executive|operations` on `/`. An explicit URL param always wins
over the stored preference; the stored preference is only the default
for a fresh visit with no param. Never encodes anything beyond the
mode string itself.

## Refresh (§32/§33)

Reuses the existing `useRefreshAction` (`queryClient.invalidateQueries()`
with no filter) unchanged — the same shared hook Monitoring already
uses, predating this prompt. Operations Workspace (Prompt 019) chose a
narrower, explicitly-scoped invalidation instead, for its own reason
(several genuinely independent sources on one page); Dashboard follows
the established cross-page convention here rather than diverging,
since changing a hook shared with Monitoring would be an unrelated,
out-of-scope refactor.

## Error handling

Every section fails independently (§28) — one section's query failing
never blanks the rest of the page, since each is its own `useQuery` +
`SectionState`/`DashboardWidget`, not a single combined fetch.
`ApiRequestError` status ≥500 gets a generic "temporarily unavailable"
message (never a raw backend message); anything else shows the
backend's own (already-safe) message.

## Accessibility (§46)

Every optional widget's title is a real heading (`CardTitle`, `<h3>`),
picked up by heading-list screen-reader navigation. The mode switch is
a `radiogroup`/`radio` pair, not a repurposed `Tabs` component — `Tabs`
pairs one tablist with exactly one `tabpanel` it renders itself, but a
dashboard mode doesn't own a single panel; it changes which of several
independent cards are visible across the whole page. Reusing `Tabs`
anyway would mean an empty, misleading `tabpanel` pointing nowhere
near the real content, so a native `radiogroup` (the correct pattern
for two mutually-exclusive options) was used instead.

## Performance (§38)

Every section issues its own independent `useQuery` — no waterfall.
The optional widget grid renders unconditionally once an organization
is selected (no separate lazy-mount gate), since every widget's own
query is already cheap and several are cache-shared with core
sections already on the page.

## Extension guidelines

- **New KPI**: if it's on `OrganizationStatisticsResponse`, add a
  `MetricCard` to `KpiGrid`. If it needs a new endpoint, add an
  `api/*.ts` module + `hooks/use-*.ts` following the existing pattern
  — confirm the real endpoint and field names by source inspection
  first, never infer from a service's name.
- **New foundational section**: a new `components/*-section.tsx` using
  `SectionState`, added to `dashboard-page.tsx` at the appropriate
  information-hierarchy level (§9/§41) — reserve this for a genuinely
  platform-primary signal, not a nice-to-have (use the widget registry
  for those instead).
- **New optional widget**: implement `ComponentType<{ organizationId: string }>`
  using `DashboardWidget` as its shell, add one entry to
  `DASHBOARD_WIDGET_REGISTRY` with its own `modes`/`roles`/
  `defaultVisible`. No page-level layout change required.
- **A metric/section the backend doesn't support yet**: don't build
  it. Document it in `backend-v1-integration-limitations.md` instead.
- **Quick actions / click-through navigation**: only ever link to a
  route registered as `"implemented"` in `lib/route-registry.ts` — use
  `getRouteById()` rather than a hand-written path.
