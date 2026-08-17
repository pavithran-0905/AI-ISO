# AI-IOS Enterprise Design System

Frontend Prompt 002. Extends the token/component foundation Prompt 001
established (`docs/frontend/architecture/`) — this tree documents the
*visual language* layered on top of it: colors, typography, spacing,
motion, status, and the reusable component set every future feature
must build from.

## Layers (§4)

1. **Primitive tokens** — raw palette values (`--gray-*`, `--blue-*`,
   ...) in `app/globals.css`. Never referenced by a component directly.
2. **Semantic tokens** — what a primitive *means* (`--background`,
   `--danger`, `--surface-elevated`, ...), mapped to Tailwind utilities
   via `@theme inline`. Components reference these.
3. **Component tokens** — the handful of values too component-specific
   to be semantic on their own (`--focus-ring-width`, border widths).
4. **Reusable components** — `components/ui`, `components/forms`,
   `components/feedback`, `components/data-display`,
   `components/navigation`, `components/overlays`. See
   `component-guidelines.md`.

## What's real vs. documented-only

Per §13, not every component named in Prompt 002 was built —
"only implement components genuinely needed by the foundation." Built:
`Button`, `IconButton`, `Badge`, `StatusBadge`, `StatusIndicator`,
`Card`, `Surface`, `Separator`, `Spinner`, `Label`, `Input`,
`Textarea`, `Select`, `Checkbox`, `Radio`, `Switch`, `FormField`,
`Alert`, `Toast`, `Tooltip`, `Popover`, `Dropdown`, `Tabs`,
`Accordion`, `Dialog`, `Drawer`, plus the loading/empty/error state
primitives Prompt 001 already built. **Documented-contract-only** (no
code, since nothing in the foundation genuinely needs them yet):
`DataTable`, `DataGrid`, `MetricCard`, `KPI`, `Timeline`,
`ActivityFeed`, `LogViewer`, `CodeViewer`, `JSONViewer`, `TreeView`,
`Pagination`, `FilterBar`, `SearchBar`, `CommandPalette`,
`Breadcrumb` — see `component-guidelines.md` and `tables.md` for their
contracts. `Stepper`/`Wizard`/`SplitPane` are **already implemented**
as `layouts/wizard-layout.tsx`/`layouts/split-pane-layout.tsx`
(Prompt 001) — not rebuilt here.

## Storybook — re-assessed, still deferred (§23)

Prompt 001 deferred Storybook after a `pnpm-lock.yaml` corruption
incident. That specific incident is now understood and fixed (see
`docs/frontend/architecture/frontend-architecture.md`'s Prompt 001
history — it was a stray rebrand find/replace corrupting 3 unrelated
integrity hashes, unrelated to Storybook itself), and `pnpm install`
now runs clean and stable. **Storybook is deferred again anyway, for a
different and more honest reason than "unstable environment":** adding
it means a genuinely new dependency footprint (`storybook` +
`@storybook/nextjs` + supporting packages — on the order of 15-20
packages) and stories for the ~24 components this prompt built, which
is itself a substantial, separable body of work. Per §23's own
permission to defer without forcing installation, and §30's "do not
modify `pnpm-lock.yaml` unless a dependency change genuinely
requires it" — nothing in this prompt's own correctness *requires*
Storybook; it's a documentation/DX nice-to-have better scoped as its
own focused unit of work. The showcase route below is the interim
substitute.

## The showcase

`app/(app)/design-system/page.tsx` (protected by the same route group
as every other authenticated page — see `routing.md`) renders every
built primitive in both themes. It is the visual contract every future
frontend prompt should check its work against — not a product page.

## Documents in this tree

- `design-principles.md` — the visual direction (§3) and what to avoid.
- `colour-system.md` — the full token table, light and dark.
- `typography.md` — the type scale.
- `spacing.md` — the spacing scale and where each level applies.
- `elevation.md` — border vs. shadow, and the 3-tier elevation scale.
- `motion.md` — durations, easings, and the four named animations.
- `iconography.md` — Lucide sizing/usage rules.
- `accessibility.md` — WCAG 2.2 AA verification per category.
- `responsive-design.md` — breakpoints and per-component collapse rules.
- `status-system.md` — the 13-state → 10-tone canonical taxonomy.
- `component-guidelines.md` — states, contracts for every built and
  documented-only component.
- `forms.md` — the form design rules (§14).
- `tables.md` — the table design rules (§15) and `DataTable`/`DataGrid` contracts.
- `charts.md` — the chart visual language (§17), contract-only (no chart library chosen yet).
