# Charts

Contract-only (§17) — **no chart library is chosen in this prompt**.
Prompt 001's technology baseline doesn't name one, and picking a
charting dependency (Recharts, visx, Chart.js, ...) without a real
chart to build is exactly the kind of premature dependency addition
Prompt 001/002 both warn against. Whichever future prompt builds the
first chart should pick a library then, against a real requirement,
and follow the rules below.

## Semantic colour usage

Chart series colors come from the same token set as everything else —
`primary`/`accent` for neutral data series, the 10 status tones for
anything representing a status/outcome (e.g. a stacked bar of
`success`/`warning`/`danger` counts). Never a chart-library default
palette; never a hardcoded hex list inside a feature module (§17
explicitly forbids hardcoding chart colors per-module).

## Per chart type

| Type | Rule |
|---|---|
| Line / area / time series | `primary` for the main series, `muted-foreground` gridlines, no more than 4 series on one chart before it becomes a legend-reading exercise instead of a visualization. |
| Bar / stacked bar | Category axis labeled with `tableText`-equivalent sizing; stacked segments use status tones when the segments represent outcomes. |
| Donut | Center label showing the aggregate (a `metric`-styled number) — a donut chart with no center label wastes its own center. |
| Gauge | Thresholds colored via `success`/`warning`/`danger` bands, matching whatever threshold config the underlying metric already defines — never a chart-local threshold definition disconnected from the real one. |
| Heatmap | A single-hue intensity scale (not a rainbow) — reserve multi-hue only for genuinely categorical (non-ordered) data. |

## Cross-cutting

- **Gridlines**: `border-muted`-equivalent opacity, never full
  `border-border` strength — gridlines support reading the chart, they
  aren't content.
- **Labels/tooltips**: `caption`/`bodySmall` typography, a chart
  tooltip should look like `Tooltip`'s own styling, not a
  library-default box.
- **Legends**: `StatusIndicator`-style dot + label per series where the
  series maps to a status tone.
- **Empty / loading / error**: the same `EmptyState`/`LoadingState`/
  `ErrorState` primitives every other data view uses — a chart doesn't
  get its own bespoke empty state.
- **Accessibility**: every chart needs a text/table alternative for the
  same data (§21-adjacent — a canvas/SVG chart with no accessible
  fallback excludes a screen-reader user from that data entirely).
