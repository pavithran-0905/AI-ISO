# Component Guidelines

## States (§22)

Every interactive component defines, at minimum: default, hover,
focus(-visible), disabled. Where applicable: active, loading, error,
selected, readonly. Concretely:

| Component | States implemented |
|---|---|
| `Button` / `IconButton` | default, hover, focus-visible, disabled, loading (`aria-busy`) |
| `Input` / `Textarea` / `Select` | default, hover, focus-visible, disabled, readonly, invalid |
| `Checkbox` / `Radio` / `Switch` | default, focus-visible, disabled, checked (native) |
| `Tabs` | default, hover (inactive tab), selected, focus-visible |
| `Dropdown` item | default, hover/focus-visible, disabled, destructive |
| `Dialog` / `Drawer` | open/closed (native `<dialog>` state) |

No component skips `focus-visible` — every one uses the same
`focus-visible:ring-2 focus-visible:ring-ring` (or the `peer-focus-visible`
equivalent for `Switch`) treatment, per `accessibility.md`.

## Built components — one-line contracts

- **`Button`** (Prompt 001) / **`IconButton`** — labeled vs. icon-only action.
- **`Badge`** — generic, non-status tag/count. **`StatusBadge`** —
  tone+label+icon primitive. **`StatusIndicator`** — named-state
  wrapper over `StatusBadge` via `@/lib/status`.
- **`Card`** (Prompt 001) — titled content block. **`Surface`** —
  untitled panel at one of 3 elevation tiers.
- **`Separator`** — a purposeful hairline divider.
- **`Spinner`** — the bare glyph. **`LoadingState`** (Prompt 001,
  updated) — a labeled loading region composing `Spinner`.
- **`Label`/`Input`/`Textarea`/`Select`/`Checkbox`/`Radio`/`Switch`/`FormField`**
  — see `forms.md`.
- **`Alert`** — persistent inline banner. **`Toast`/`ToastViewport`** —
  transient, auto-dismissing notification, imperative API
  (`toast.success(...)`) via `state/toast-store.ts`.
- **`Tooltip`** — CSS-only hover/focus label. **`Popover`** — arbitrary
  floating content. **`Dropdown`** — an action menu (`role="menu"`).
- **`Tabs`** — WAI-ARIA tab pattern. **`Accordion`** — native
  `<details>`-based disclosure list.
- **`Dialog`** — modal, native `<dialog>`. **`Drawer`** — edge-anchored
  panel, same primitive.

## Documented-only contracts (§13) — not built, no consumer yet

| Component | Contract |
|---|---|
| `DataTable` / `DataGrid` | See `tables.md` in full. |
| `MetricCard` | A `Card` variant: `typography.metric` headline number, a `caption` label above it, an optional trend indicator (↑/↓ + percentage, colored via `success`/`danger` tone based on whether the direction is good or bad *for that metric* — not hardcoded to "up is good"). |
| `KPI` | The same shape as `MetricCard` at a smaller size, for a dense multi-KPI row rather than one-per-card. |
| `Timeline` | A vertical list of dated events, each with a `StatusIndicator`-style dot, a title, a timestamp (`caption`), reverse-chronological by default. |
| `ActivityFeed` | A `Timeline` specialization: each entry additionally carries an actor (user/system) and an action verb. |
| `LogViewer` | Monospace (`typography.code`), virtualized for volume (not built — no virtualization dependency chosen yet), a level-based `StatusIndicator` per line (info/warning/danger tones), sticky "jump to latest" affordance. |
| `CodeViewer` | Monospace, line numbers, syntax highlighting (library TBD — not chosen; adding one is a future prompt's decision, not implied by this contract). |
| `JSONViewer` | Collapsible tree using the same disclosure pattern as `Accordion` (native `<details>` per node) rather than a bespoke tree-collapse implementation. |
| `TreeView` | Generalizes `JSONViewer`'s disclosure pattern to arbitrary hierarchical data (e.g. asset topology). |
| `Pagination` | Page-number + prev/next, `nav` landmark, `aria-current="page"` on the active page. |
| `FilterBar` | A `Surface` (`flat`) toolbar row of filter controls (`Select`/`Input`/`Checkbox` as appropriate) + a "clear all" `Button` (`ghost` variant) — collapses to a `Drawer` on narrow viewports per §20. |
| `SearchBar` | An `Input` with a leading search icon and a debounced `onChange` — the debounce interval isn't specified here since it should be tuned per data source, not fixed globally. |
| `CommandPalette` | A `Dialog` variant: no header/footer, a `SearchBar` immediately inside, results as a `role="listbox"` — reads `@/lib/route-registry` once real navigation exists. |
| `Breadcrumb` | A `nav aria-label="Breadcrumb"` with an `ol`, reading from `@/lib/route-registry`'s own `breadcrumb` field — not yet wired since no nested routes exist yet. |

## Dashboard visual language (§16) — not building the Dashboard page

- **KPI cards**: `MetricCard`/`KPI`, above.
- **System health / service status**: `StatusIndicator` grids, not
  free-form colored boxes — every health signal on a dashboard must
  resolve through the same taxonomy a detail page would use for the
  same resource.
- **Alerts**: `Alert` (persistent, on-page) for something the operator
  must see now; `Toast` only for a transient confirmation of an action
  *they* just took, never for an incoming alert they didn't trigger.
- **Charts**: see `charts.md`.
- **Recent activity**: `ActivityFeed`, above.
- **Quick actions**: `Button`s, grouped, not a decorative icon grid.
- **Operational summaries**: prioritize actionable information over
  decorative aggregate cards (§16) — a dashboard card exists to answer
  "does something need my attention," not to fill space.

## Navigation visual rules (§19) — language only, not the final structure

- **Sidebar**: `surface` background, `border-border` right edge,
  collapsible to icon-only at `iconSize.control` width.
- **Nav item**: `px-3 py-2` (matches `Tabs`), `iconSize.control` icon +
  label, `gap-2` (matches `iconLabelGapClass`).
- **Active item**: `bg-muted` background + `text-foreground` (not a
  color-only signal — paired with a left border accent using
  `border-primary` at `--border-width-emphasis`, so it doesn't rely on
  the muted-background alone).
- **Nested navigation**: indent by one `pl-4` step per level, no more
  than 2 levels deep (a 3rd level belongs on its own page, not deeper
  nesting).
- **Breadcrumbs**: see `Breadcrumb`'s contract, above.
- **Top bar**: matches `layouts/main/header.tsx`'s existing `h-14
  border-b` shape.
- **User menu / notification area**: both are `Dropdown` consumers,
  anchored top-right.
