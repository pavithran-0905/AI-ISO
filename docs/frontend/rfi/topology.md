# Topology

Per Prompt 012 §59, this honestly separates **IMPLEMENTED** from
**PLANNED**/**UNAVAILABLE** for the Enterprise Infrastructure Topology
& Dependency Visualization Experience. Nothing here claims future
functionality as currently available. See `../rfi/README.md` and
`../rfi/infrastructure-inventory.md` for the foundation this builds on.

## Infrastructure topology visualization — IMPLEMENTED (real, one root at a time)

A real, interactive graph canvas (`GET /inventory/topology?query_kind=neighbors`)
showing one focused asset and its direct, directed relationships, with
zoom/pan/fit/reset — not a decorative graph, not a fabricated one. See
`../developer-guide/topology.md` "The real contract, in full" for
exactly what the backend does and doesn't provide, and "Why the graph
canvas only ever renders neighbors" for why multi-hop edges are never
drawn.

## Dependency visibility — IMPLEMENTED (as a real, distance-grouped list)

`query_kind=dependencies`/`impact` with a real `depth=1..5` control are
both real, backed by an actual Neo4j traversal — rendered as a
structured list (`TopologyListView`), never a graph, because the
backend's own response for these two kinds carries no parent/path
linkage at all (confirmed by source inspection). Drawing an edge for
either would mean inventing one.

## Operational impact analysis — IMPLEMENTED (list-based, no fabricated severity)

`query_kind=impact` answers "what would be affected if this asset
failed," using only the backend's own real transitive-dependent
traversal. No severity, blast-radius score, or service-level
categorization is shown beyond the asset's own real type and health —
none of that is computed by V1, so none is invented here.

## Source → target path analysis — UNAVAILABLE (documented, not implemented)

No path-query endpoint exists between two arbitrary assets — confirmed
absent from `inventory-service`'s topology router. Not built.

## Health overlay — IMPLEMENTED (joined, not native to the endpoint)

Every node shown carries its real, current health, joined in from the
same real asset list Prompt 011 already established
(`useAllAssets`) — the topology endpoint itself has no health field on
any node. No health propagation/aggregation logic runs client-side;
each node shows only its own real status.

## Alert overlay / Alerting integration — UNAVAILABLE (documented, not implemented)

No reachable relationship exists between an asset and an alert in
either direction (reconfirmed this prompt; see
`../backend-v1-integration-limitations.md`). No indicator, count, or
link was fabricated.

## Automation integration — UNAVAILABLE (a real field exists, but no route reaches it)

`automation-service`'s own `AutomationTargetResponse` schema has a real
`inventory_asset_id` field — but no API route anywhere in that service
ever creates, lists, or queries a target by it (confirmed: the schema,
service, and model exist; nothing in `app/api/` references any of
them). A real relationship the data model supports, with zero way for
this frontend to reach it. Documented, not built.

## Monitoring integration — UNAVAILABLE this prompt (superseded reasoning)

Monitoring's own asset ownership moved to Infrastructure in Prompt
011; Monitoring today has no separate per-asset detail view left to
link into from Topology, and no shared "service health" identifier
connects `observability-platform-service`'s service-topology concept
to `inventory-service`'s asset topology. No cross-link was built in
either direction this prompt.

## Search — IMPLEMENTED (real, server-side)

`GET /inventory/search` (Prompt 011's own endpoint), debounced,
focuses the graph on the selected result — never a client-side filter
over whatever's currently rendered.

## Filtering — IMPLEMENTED (client-side, scoped to the already-loaded graph)

`GET /inventory/topology` accepts no filter parameter of any kind.
"Show relationship types" toggles visibility within the already-
loaded, single-root/1-hop response only — see the developer guide's
own section distinguishing this from the unbounded-dataset client-
filtering anti-pattern ruled out elsewhere in this app.

## Depth control — IMPLEMENTED (real, 1–5, where the backend honors it)

Real for `dependencies`/`impact`. `neighbors` ignores `depth`
server-side (confirmed: the route never passes it through for that
kind) — the depth control is hidden on that tab rather than shown and
silently no-op'd.

## Focus mode — IMPLEMENTED (real re-query per hop, not client-side traversal)

"Focus topology on this asset" issues a brand-new real
`GET /inventory/topology` request centered on the clicked asset — see
the developer guide's "Focus, not expand" section. This is also this
feature's answer to large-graph handling (§21): only ever one root's
real 1-hop neighbor set is in memory at a time, never an accumulated
or fully-downloaded graph.

## Selection and detail panel — IMPLEMENTED

Node and edge selection both open a real detail drawer: identity,
health, real relationships, "Open full asset detail," and "Ask AI."
Edge metadata is enriched from a real `GET /inventory/relationships`
match when one exists, and says so plainly when it doesn't (§13: "do
not create fake relationship descriptions").

## Graph/List accessibility — IMPLEMENTED (both real, not one faking the other)

The graph canvas is built entirely from real, independently
focusable/labeled HTML buttons (not raw SVG shapes) — genuinely
keyboard- and screen-reader-navigable on its own — and `TopologyListView`
is a complete, separately usable structured alternative. Neither is a
decorative stand-in for the other.

## Responsive UX — IMPLEMENTED

Below the tablet breakpoint, the workspace always renders List view;
the interactive graph canvas is a desktop/tablet experience, per §45's
own instruction not to squeeze it into mobile.

## Export — UNAVAILABLE (documented, not implemented)

No topology-specific export route exists on this service. Not built.

## Real-time updates — UNAVAILABLE (documented; manual/on-navigation refresh only)

No push/streaming mechanism exists for topology data anywhere in this
platform (confirmed absent, consistent with every other feature this
session). The backend itself caches each traversal result for 5
minutes server-side (`app/services/topology.py`'s own cache) — this
frontend re-queries on every focus change and via each section's own
retry action, never polls artificially.

## AI integration — IMPLEMENTED

"Ask AI" from a selected node's detail panel, same plain-text-draft
mechanism as every other feature — no fabricated graph-context payload
is ever sent, since no such API exists.

## Dependency safety — IMPLEMENTED (no new dependency added)

`package.json` was checked before writing any canvas code; no existing
graph-visualization library was found, and none was added. The graph
canvas is hand-rolled — see the developer guide's "Graph renderer"
section for why that was the right call for a graph this shape-
constrained, not a shortcut.

See `../backend-v1-integration-limitations.md` for the full,
cross-prompt list with source citations.
