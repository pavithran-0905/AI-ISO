# Topology

The Enterprise Infrastructure Topology & Dependency Visualization
Experience built in Prompt 012, against `services/inventory-service`'s
one real topology endpoint. See
`docs/frontend/rfi/topology.md` for the implemented-vs-planned split
and `docs/frontend/backend-v1-integration-limitations.md` for the
gaps this prompt found.

## The real contract, in full

`GET /inventory/topology?asset_id=&query_kind=neighbors|dependencies|impact&depth=1..5`
is the **only** topology endpoint that exists — confirmed by direct
inspection of `app/api/topology.py`, `app/services/topology.py`, and
`app/topology/graph.py` (the Neo4j client underneath). There is no
full-graph endpoint, no source→target path endpoint, no node-detail
endpoint (asset detail is reused from Prompt 011), and no server-side
filter of any kind.

Critically, the three `query_kind` values are **not equivalent** in
what they return:

| `query_kind` | Depth | Returns per node | Real edges? |
|---|---|---|---|
| `neighbors` | Always 1 hop (backend never reads `depth` for this kind — confirmed: `get_neighbors` takes no depth argument) | `relationship_type`, `outgoing` (direction) | **Yes** |
| `dependencies` | 1–5, real | Only `distance` | **No** — `relationship_type`/`outgoing` are always `null` |
| `impact` | 1–5, real | Only `distance` | **No** — same as `dependencies` |

This is confirmed at the Cypher level: `get_neighbors`'s query returns
`type(r)`/`startNode(r).id = a.id AS outgoing`; `get_dependency_graph`/
`get_impact_analysis`'s queries return only `dependency.id`/`.name`/
`.asset_type`/`length(path) AS distance` — no relationship type, no
direction, and critically **no parent/path linkage at all**. A
multi-hop response is a flat, deduplicated, distance-tagged node list;
there is no way to know which node connects to which beyond the root.

## Why the graph canvas only ever renders `neighbors`

Given the table above, drawing a real multi-hop edge for
`dependencies`/`impact` would mean inventing one — exactly what §5/§7
of the prompt forbid ("do not invent graph properties," "never
fabricate relationship semantics"). So the interactive graph canvas
(`TopologyGraphCanvas`) only ever renders one root plus its real,
directed, 1-hop `neighbors` — the one shape the backend actually
proves. `dependencies`/`impact` are real, honest, and fully supported,
just never as a canvas: `TopologyListView` renders them as a
distance-grouped list instead, with a working `depth` selector (real
`1..5`, wired straight to the query param) since that control only
makes sense for those two kinds — hidden entirely on the `neighbors`
tab, with a note explaining why, rather than shown and silently
ignored.

## "Focus," not "expand": how a bigger picture is built honestly

Since only 1-hop `neighbors` data is trustworthy, "exploring" the
graph is implemented as **pivoting the root**, not accumulating nodes
client-side. Clicking **Focus topology on this asset** in the detail
panel issues a brand new, real `GET /inventory/topology?asset_id=<new
root>&query_kind=neighbors` request and replaces the canvas entirely —
this is real lazy expansion (§21), one real request per hop walked,
never a client-side traversal algorithm layered on top of what the
backend already computed.

## Graph data model and adapter (§30/§31)

`features/infrastructure/lib/topology-graph-adapter.ts#buildFocusGraph`
is the one place a raw `TopologyResult` (backend response shape,
already typed in Prompt 011) becomes a `TopologyGraph`
(`TopologyGraphNode`/`TopologyEdge`, Prompt 012's own types) — the
renderer (`TopologyGraphCanvas`) never sees the backend's field names
or nullability directly. Two details worth noting:

- **Health is joined in, not returned.** No topology node carries a
  health field (confirmed absent from `TopologyNode`'s own schema) —
  `buildFocusGraph` takes a `healthById` map built from `useAllAssets`
  (the same real, precedented bulk-list call `AssetRelationshipsSection`
  already uses for name resolution in Prompt 011) and joins each
  node's real health onto it. A node whose id isn't found there (the
  join hasn't loaded yet, or genuinely missing) renders `health: null`,
  shown as "Unknown" rather than blocking the whole graph.
- **Edge ids are synthetic.** The topology endpoint gives no edge id
  of its own — `TopologyEdge.id` is `${source}::${relationshipType}::${target}`,
  built once in the adapter. For real edge *metadata* (a custom label,
  free-form metadata fields), `TopologyDetailPanel` separately queries
  the real `GET /inventory/relationships?asset_id=<root>` (Prompt
  011's own endpoint) and matches by `(sourceAssetId, targetAssetId,
  relationshipType)` — when no match is found, the panel says so
  plainly ("No additional metadata recorded for this relationship")
  rather than inventing any.

## Graph renderer: hand-rolled, not a library (§53)

`package.json` was checked before writing a single line of canvas
code — no graph-visualization library exists in this app. None was
added. The graph this feature ever renders is always exactly one root
plus its direct neighbors (per the table above), a shape simple enough
that reactflow/cytoscape/d3-force would be pure bundle weight for
geometry this constrained. `TopologyGraphCanvas` lays out neighbors on
a single circle around a centered root (`layoutRadial`) and renders:

- **Real HTML `<button>`s for every node and every edge** — never a
  bare SVG shape with a click handler. Each has its own accessible
  name (a node's is its visible text; an edge's is an explicit
  `aria-label` naming the relationship, source, and target) and is
  independently focusable/activatable.
- **An SVG layer purely for the connecting lines**, marked
  `aria-hidden` — decorative only, never the only way to perceive a
  connection (every edge also has its own real button).
- **Zoom/pan as local component state** (`useState`, not global) — a
  CSS `transform: translate(...) scale(...)` on one wrapper div, with
  wheel-to-zoom and drag-to-pan, plus four real, keyboard-focusable
  buttons (Zoom in/out, Fit to screen, Reset) as the primary
  keyboard-accessible controls (§22/§23).

**A real bug this surfaced, worth recording**: the initial
implementation called `setPointerCapture` on the canvas container from
its own `onPointerDown` handler unconditionally, to support drag-to-pan
on empty canvas. In a real browser, that capture also fires when a
`pointerdown` bubbles up from a *child* node/edge button, which
redirects the subsequent `pointerup` to the container instead of the
button — and browsers derive the synthetic `click` event from the
pointerdown/pointerup pair landing on the same target, so the button's
own `click` handler silently never fired. `jsdom`'s `fireEvent.click`
in the unit test suite dispatches a click event directly and never
exercises real pointer-capture semantics, so all unit tests passed
while every E2E test that clicked a node timed out. Fixed by checking
`event.target.closest("button")` and skipping capture/pan entirely
when the gesture starts on an interactive child — panning only ever
starts from genuinely empty canvas space now. Left as a comment at the
fix site as a warning against reintroducing it.

## "Show relationship types": a display filter, not a backend one (§15)

`GET /inventory/topology` accepts no filter parameter of any kind
(confirmed absent). `TopologyFilters` is a client-side toggle over the
already-loaded, single-root/1-hop response only — scoped to exactly
the asset types actually present among the current neighbors (never
the full 44-value `ASSET_TYPES` vocabulary) — and never triggers a
re-query. This is a different thing from the client-side-filtering-
over-an-unbounded-dataset anti-pattern Prompt 011 already ruled out for
the asset list: the graph response here is inherently already scoped
(one root, 1 hop, real backend traversal), so hiding already-loaded
nodes by type is a legitimate display refinement, not a fabricated
backend capability.

## Search (§14)

`TopologySearch` uses the real, server-side `GET /inventory/search`
(Prompt 011's own endpoint) with a 300ms debounce, never a client-side
filter over whatever happens to already be on screen. Selecting a
result sets the `focus` URL param, which triggers a brand new real
topology query for that asset — never a client-side jump to a node
that might not even be in the currently-loaded graph.

## Query architecture (§29/§32)

`Topology Page → TopologyWorkspace → TopologyGraphCanvas/TopologyListView
→ use-topology-graph.ts / use-topology.ts → topology-api.ts →
apiClient → GET /inventory/topology`. `useTopologyGraph` composes
three real TanStack Query hooks (`useAsset`, `useTopology`,
`useAllAssets`) rather than adding a fourth API call — no new endpoint
was invented to avoid this composition.

## State management: `key`, not an effect (§22)

Selection and the "show relationship types" filter reset to a clean
slate whenever the focused asset changes. The first implementation did
this with a `useEffect` that called `setSelection(null)` on
`focusAssetId` change — this app's lint config (`react-hooks/set-state-
in-effect`) rejects synchronous `setState` calls inside an effect body,
correctly: it's the "adjusting state when a prop changes" anti-pattern
React's own docs warn against, since it causes a wasted extra render
every time. Fixed by extracting the state into a small
`TopologyFocusedGraph` subcomponent, rendered with `key={focusAssetId}`
from its parent — React remounts it fresh on every focus change, no
effect required. The mobile-viewport check
(`useIsMobileViewport`) has the same shape of fix: `useSyncExternalStore`
subscribing directly to `window.matchMedia`'s change event, rather than
an effect calling `setState` once on mount.

## Cross-module integration

- **Infrastructure**: `AssetDetailView` gained a real **View in
  Topology** link (`/infrastructure/topology?focus={id}`) — the only
  new cross-link this prompt adds to that page. `TopologyDetailPanel`
  links back via **Open full asset detail**.
- **AI Assistant**: `AskAiButton`, same plain-text-draft pattern as
  every other feature this session — no fabricated structured graph
  context is ever sent.
- **Monitoring / Alerting / Automation**: confirmed absent, same
  finding as Prompt 011 reconfirmed here from the topology angle — no
  asset-to-alert or asset-to-automation-target relationship is
  reachable via any route (see `backend-v1-integration-limitations.md`
  for the automation-target finding specifically, which is new this
  prompt). No cross-link was built for any of the three.

## Accessibility (§43/§44)

`TopologyListView` is the required non-graph alternative — real
`<table>`-free but fully structured lists, real links, a real `Focus`
button per row, real tab semantics for the three query kinds. The
graph canvas itself is also independently accessible (see "Graph
renderer," above): every node and edge is a labeled, focusable
`<button>`, not merely "the list view exists so the graph doesn't have
to be." A screen-reader-only paragraph above the canvas explains the
graph's scope and points at the List view toggle.

## Error handling / partial failure (§41/§42)

The graph, the list view, and the detail panel's relationship-metadata
enrichment are each their own `useQuery` — a slow or failed
`useAllAssets` health join degrades only the health badges (shown as
"Unknown"), never blocks the graph from rendering; a failed detail-
panel metadata lookup degrades only that one field, never the whole
panel.
