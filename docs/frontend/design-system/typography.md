# Typography

Source of truth: `lib/typography.ts`. Font family: Inter (`--font-sans`,
variable, loaded via `next/font/google` in `app/layout.tsx`) for
everything except code/IDs, which use JetBrains Mono (`--font-mono`).
Both were already established in Prompt 001 — unchanged here.

## Scale

| Token | Classes | Use |
|---|---|---|
| `display` | `text-3xl font-semibold tracking-tight text-balance` | Rare — a hero moment, not a page default. |
| `pageTitle` | `text-xl font-semibold tracking-tight` | One per route, the page's own `<h1>`. |
| `sectionTitle` | `text-base font-semibold tracking-tight` | A section heading within a page. |
| `cardTitle` | `text-sm font-semibold` | Matches `Card`'s own `CardTitle`. |
| `body` | `text-sm leading-relaxed` | Default copy. |
| `bodySmall` | `text-xs leading-relaxed` | Supporting copy — never the sole carrier of critical information. |
| `label` | `text-xs font-medium` | Form labels and small all-context labels. |
| `caption` | `text-xs text-muted-foreground` | Timestamps, helper text, metadata. |
| `code` | `font-mono text-xs` | Inline/block code, IDs, hashes. |
| `metric` | `text-2xl font-semibold tracking-tight tabular-nums` | A KPI's headline number — `tabular-nums` so a column of metrics aligns. |
| `tableText` | `text-sm` | Table cell text — same size as `body`, named separately so density tuning doesn't touch prose. |

## Weight, line height, letter spacing

Weights used: `font-medium` (labels, nav, table headers) and
`font-semibold` (titles, metrics) only — no `font-bold` anywhere,
matching §7's "avoid overly thin typography" from the other direction:
Inter's own regular weight is already readable at small sizes, and a
third weight adds no information.

## Truncation and wrapping

`truncateClass` (`truncate`) for anything that must not wrap and push a
layout (table cells, badges, nav labels). `wrapBalancedClass`
(`text-pretty`) for body copy/descriptions only — never a table cell.
