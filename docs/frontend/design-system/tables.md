# Tables

AI-IOS will contain significant infrastructure data (§15) — tables are
one of the most-used surfaces in the eventual product. **Neither
`DataTable` nor `DataGrid` is built in this prompt** (no consumer
exists yet, per §13's "only implement components genuinely needed by
the foundation"); this document is their design contract, binding on
whichever future prompt builds them.

## Contract

- **Header**: `surface-muted` background, `caption`-weight
  (`text-xs font-medium text-muted-foreground`), sticky on scroll for
  a tall table.
- **Rows**: `border-border` bottom hairline between rows, no vertical
  cell borders (a common enterprise-table mistake: vertical rules add
  visual noise without adding information).
- **Hover**: `hover:bg-muted` on the row, not the cell.
- **Selected rows**: `bg-primary/5` background + a `border-primary`
  left accent at `--border-width-emphasis` — the same "don't rely on
  background alone" rule as a navigation active state.
- **Sorting**: a `ChevronUp`/`ChevronDown` (`iconSize.inline`) next to
  the sorted column's header label, `aria-sort` on the `<th>`.
- **Filtering**: via `FilterBar` (see `component-guidelines.md`), never
  a filter control embedded in the table header itself.
- **Pagination**: via `Pagination` (see `component-guidelines.md`),
  below the table, never infinite-scroll by default (an operator
  scanning infrastructure data needs a stable, countable result set).
- **Column visibility**: a `Dropdown` of `Checkbox` items, one per
  column, triggered from a toolbar icon.
- **Density**: two modes — default (`px-3 py-2` per `spacing.md`) and
  compact (`px-2 py-1`) — a single toggle affects the whole table, not
  per-row.
- **Status cells**: always `StatusIndicator`, never a raw colored
  text/background in a cell.
- **Actions**: a trailing column, right-aligned, `IconButton`s or a
  single `Dropdown` ("⋯" trigger) once a row has more than 2 actions.
- **Empty state**: `EmptyState` (Prompt 001) inside the table body
  region, not a blank table.
- **Loading**: `Skeleton` rows matching the real row height/column
  count, not a single centered `LoadingState` replacing the whole
  table (which loses the header/column context while loading).
- **Error**: `ErrorState` (Prompt 001) with `onRetry`, replacing the
  body region.
- **Long text**: `truncateClass` by default per cell, with the full
  value in a `Tooltip` — never silent truncation with no way to read
  the full value.
- **Responsive fallback**: below `md`, a card-per-row transformation
  (each row's cells become labeled key/value pairs in a `Card`) rather
  than horizontal scroll — matching §20's "do not simply scale
  everything down."
