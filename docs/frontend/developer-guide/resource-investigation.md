# Resource Detail & Investigation Workspace

Built in Prompt 018 as a set of genuinely reusable shell primitives
(`components/resource/*`), applied to retrofit the existing Asset
Detail page (Prompt 011) as their reference implementation — not a
parallel rebuild, and not forced onto every other detail page in this
codebase. See `docs/frontend/rfi/resource-investigation.md` for the
implemented-vs-planned split and
`docs/frontend/backend-v1-integration-limitations.md` for the full gap
list with citations.

## There is one real "resource" type here, not four

§2's own examples (Machine, VM, Service, Application) are not separate
backend resources. `inventory-service`'s `Asset` model has a single
`asset_type` enum (`ASSET_TYPES`, `features/infrastructure/types/index.ts`)
whose values include `physical_server`, `virtual_machine`, `service`,
and so on — one model, one real REST resource, one real adapter
(`useAsset`/`assetsApi`, already built in Prompt 011). No
`MachineAdapter`/`VirtualMachineAdapter`/`ServiceAdapter`/
`ApplicationAdapter` were created (§37's own suggestion) — building
four adapters for what is structurally one backend concept would
misrepresent the real data model, not simplify it.

No other resource type in this backend has comparable investigation
depth (health + relationships + a real topology query + real actions).
User (Prompt 014), Alert (Prompt 007), Report (Prompt 008), Automation
Job (Prompt 009), and Workflow Instance (Prompt 010) all already have
their own real, working, independently-tested detail pages — none was
retrofitted onto these new primitives in this prompt. Forcing that
retrofit for pages that already show everything their own backend
provides, with no new capability gained, would only add regression
risk for a stylistic goal — inconsistent with this session's
established restraint (Prompt 015's GRC-CRUD exclusion, Prompt 016's
choice not to reopen Prompt 015's shipped scope). The primitives below
are written generically enough for a future resource type to adopt.

## Reusable primitives (`components/resource/`)

- **`ResourceHeader`** — built on the existing `PageHeader`, adding
  only the one thing a generic page header doesn't have: an
  identifier/environment/last-updated meta row. Every field is
  optional; a resource type with fewer real fields simply omits what
  it doesn't have.
- **`ResourceBreadcrumbs`** — fixes a real, pre-existing gap: the
  shell's own `Breadcrumbs` resolves a trail by *exact* pathname match
  against `lib/route-registry.ts`, and no dynamic `[id]` route has ever
  been registered there (confirmed — matches every other detail page's
  own established convention). Every resource detail page in this
  codebase has therefore shown **no breadcrumb trail at all** until
  now. `ResourceBreadcrumbs` takes an explicit trail instead — its
  static ancestor entries (`getRouteById("infrastructure")`,
  `getRouteById("infrastructure-assets")`) still come from the real
  registry; only the final, current-resource entry is supplied
  directly, since no registry entry could express a dynamic name
  anyway.
- **`ResourceSection`** — `Card` + `CardHeader`/`CardTitle` +
  `SectionState`, extracted once the same three-line shape repeated
  across every section this feature and its predecessors already
  wrote. Each instance owns its own loading/error state, so one
  section's failure (§28) never blanks the page — confirmed by a real
  test asserting a failed section renders its own retry control while
  sibling content stays intact.
- **`ResourceNotFound`** — §29's dedicated 404 state, distinct from
  `SectionState`'s generic error branch (which still handles §30's
  permission-denied case via its existing 403 → `AccessDeniedState`
  path — not modified, already correct). `AssetDetailPage` checks
  `error instanceof ApiRequestError && error.status === 404`
  explicitly and renders this instead of the generic retry-oriented
  error UI, which would otherwise invite retrying a resource that
  genuinely doesn't exist.

`ResourceTabs` was **not** built as a new component — the existing
`components/navigation/tabs.tsx` (real `tablist`/`tab`/`tabpanel`
semantics, keyboard navigation, already used by Settings and
Administration) is reused directly, per §39's own "if an existing
command component exists, reuse it."

## Asset Detail's real section inventory — everything else confirmed absent

Four real tabs, URL-addressable (`?tab=overview|relationships|topology|configuration`,
§20): **Overview** (Identity, Current State, Actions — all already
real, from Prompt 011), **Relationships** (`AssetRelationshipsSection`,
Prompt 011), **Topology** (`TopologySection`, `GET /inventory/topology`,
Prompt 012), **Configuration** (tags/metadata, Prompt 011, sensitive
keys masked). Every other section §8-§16 lists is confirmed absent for
this specific resource, not merely unbuilt:

- **Health/Metrics**: no metric-series endpoint exists anywhere in
  this backend (confirmed absent, pre-existing finding from Prompt
  011). The asset's own `health` enum field is shown (Current State),
  which is the entirety of what's real here.
- **Alerts**: `alerting-service`'s `Alert.source_reference` is
  unstructured JSON with no schema-enforced `asset_id` (confirmed by
  reading `alert_instance.py`'s own model docstring: "without this
  service needing a foreign key into every other service's own
  schema"). Building a "Resource → Alerts" section from this would be
  the same class of speculative linkage this session has refused to
  build for Audit (Prompt 015) and Notifications (Prompt 016).
- **Activity/Audit**: `inventory-service` has its own real audit
  table with zero route reaching it (Prompt 015's own finding); none
  of the three real audit sources Prompt 015 built against records
  infrastructure-asset actions at all.
- **Automation**: `automation-service`'s `AutomationTargetResponse`
  has a real `inventory_asset_id` field and a real model — but
  `app/api/__init__.py` never registers a router for targets at all
  (confirmed absent, cited in the limitations doc). The service/model
  layer fully supports asset-to-automation-target linking; there is no
  way to reach it over HTTP.
- **Reports**: `Report` (`reporting-service`) has no `asset_id` or
  equivalent field of any kind (confirmed by its own type definition).
- **Monitoring**: `observability-platform-service`'s own topology/events
  routes are a separate system from `inventory-service`'s
  `/inventory/topology` (already consumed here) — no asset-id
  cross-reference exists between them.

**Real and already implemented**: "View in Topology" (Prompt 012) and
"Ask AI about this resource" (Prompt 010's `AskAiButton`, reused
unchanged — a pre-filled, never-auto-sent draft referencing the
asset's real name/id, the only honest mechanism available since no
structured context-attachment API exists).

## Refresh (§21) — scoped to this resource's own real query keys

`AssetDetailPage`'s refresh button invalidates exactly
`["infrastructure", "assets", assetId]`,
`["infrastructure", "relationships", assetId]`, and
`["infrastructure", "topology", assetId]` — never the whole-application
`invalidateQueries()` this session's own `useRefreshAction` (Dashboard,
Monitoring, Reporting, Audit, Notifications) uses for a page with one
dominant query. A resource investigation page composes several
independent per-section queries, so a page-wide invalidate would be
significantly more wasteful here than for those single-query pages.

## Search, Notification, and Audit integration (§42-§44)

- **Global Search → Resource Detail**: real (Prompt 017 already links
  asset search results to `/infrastructure/assets/{id}`; unchanged by
  this prompt, re-verified by a new E2E test).
- **Notification → Resource Detail**: confirmed absent (Prompt 016 —
  `Notification` has no structured entity reference of any kind).
- **Audit Event → Resource**: confirmed absent (Prompt 015 — none of
  the three real audit sources records infrastructure-asset actions;
  `inventory-service`'s own audit trail is unrouted).

## Accessibility and performance

`ResourceSection`'s independent `SectionState` instances mean each
section's own loading/error is announced separately (existing
`SectionState`/`Skeleton` accessibility already covers this — not
re-implemented). Section queries (`useAsset`, `useAssetRelationships`,
`useTopology`) already ran independently before this prompt (Prompt
011/012's own architecture) — the tab restructure doesn't change that,
it only changes which are *rendered* at once, avoiding waterfall
requests for a section the operator hasn't opened yet (Relationships/
Topology's own queries were already gated `enabled: assetId !== null`
each, so switching to a tab that was never opened means that section's
query never fires at all).
