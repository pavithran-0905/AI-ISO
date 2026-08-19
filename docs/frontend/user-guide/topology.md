# Topology

Explore how one asset connects to everything around it — what it runs
on, what depends on it, and what would be affected if it went down.

## Opening Topology

Open **Topology** from the Infrastructure tab bar, or
`/infrastructure/topology` directly. You'll land on a prompt to search
for an asset — Topology always starts focused on one asset at a time,
never a full dump of everything AI-IOS knows about.

## Searching for an asset

Type into **Search assets** (name, hostname, IP, serial, and more).
Selecting a result focuses the graph on that asset.

You can also jump straight into Topology from any asset's own detail
page: click **View in Topology** near the top.

## The graph

Once focused, you'll see the selected asset in the center with its
direct relationships arranged around it — each one a separate,
clickable card showing its name, type, and current health. An arrow
between two assets shows which one the relationship points from and
to; the small label on the arrow names the relationship (for example,
"depends_on").

- **Zoom in / Zoom out** — the magnifying-glass buttons above the
  graph.
- **Fit to screen** — resets zoom to fit everything currently shown.
- **Reset view** — returns to the default zoom and position.
- **Drag** anywhere on empty canvas to pan around.
- **Show relationship types** — in the side panel, hide or show
  specific kinds of connections.

## Selecting an asset or a relationship

Click any asset card to open its details in a side panel:

- Health, type, and current state.
- **Focus topology on this asset** — re-centers the whole graph on it,
  so you can walk outward one hop at a time.
- **Open full asset detail** — takes you to that asset's complete
  record in Infrastructure.
- **Ask AI** — opens a new AI Assistant conversation already
  referencing this asset (nothing is sent until you choose to).
- Every relationship touching the selected asset, each linking to the
  other asset involved.

Click the small labeled arrow between two assets to see the
relationship's type, direction, and any additional details recorded
for it.

## List view

Prefer a plain list, or using a screen reader? Switch to **List view**
next to the graph toggle. It offers three tabs:

- **Neighbors** — every asset directly connected to the focused one.
- **Dependencies** — what the focused asset depends on, transitively,
  up to 5 hops out (adjust with the **Depth** control).
- **Impact** — what would be affected if the focused asset became
  unavailable, also up to 5 hops out.

Each row shows the asset's name, type, and distance, with a **Focus**
button to re-center the graph on it.

## Health overlay

Every asset shown carries its real, current health status (Healthy,
Warning, Critical, Unknown, and so on) using the same indicators you
see everywhere else in AI-IOS.

## Monitoring and Alerting

There's currently no link between Topology and Monitoring's Service
Health / Events views, or between Topology and a specific Alert —
AI-IOS doesn't record either kind of connection today, so no such
link is shown.

## Mobile and tablet

On a narrow screen, Topology always shows the list view — the full
interactive graph is a desktop/tablet experience.

## Troubleshooting

- **I don't see a graph, just an empty prompt.** Search for an asset
  first — Topology needs to know where to start.
- **A relationship shows "(incoming)".** The *other* asset is the one
  doing the action described (for example, another asset "depends on"
  this one), not the reverse.
- **An asset seems to be missing from the graph.** Check the
  **Show relationship types** filter in the side panel — it may be
  hidden.
- **The graph only ever shows one hop.** That's expected for the graph
  itself: use **Focus** on any asset (in the graph or the list) to walk
  outward one asset at a time, or switch to List view's Dependencies/
  Impact tabs for a multi-hop view.
