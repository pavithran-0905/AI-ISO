# Responsive Design

Extends Prompt 001's own `docs/frontend/standards/responsive-design.md`
(which already covers `SplitPaneLayout`'s stacking and
`SettingsLayout`'s sidebar-to-tab-strip collapse). This document covers
the new component set's own responsive behavior.

Primary target: enterprise desktop/laptop (§20/§3) — nothing here
"simply scales everything down."

## Breakpoints and containers

Tailwind v4's default breakpoints (`sm`/`md`/`lg`/`xl`/`2xl`), used
as-is — unchanged from Prompt 001's own decision, still correct here.

## Per-component behavior

- **`Dialog`**: fixed `max-w-md`, centered — doesn't grow on desktop
  beyond a readable measure, doesn't need a narrow-viewport variant
  (native `<dialog>` already clamps to the viewport).
- **`Drawer`**: `max-w-md`, full height, anchored right — on a narrow
  viewport this already reads as near-fullscreen without extra rules,
  since `max-w-md` combined with `w-full` caps at the smaller of the
  two.
- **`Popover`/`Dropdown`**: no viewport-edge collision detection yet
  (documented gap, not silently missing) — both position via a simple
  `absolute` offset from their trigger, which can overflow the
  viewport near a screen edge. A future prompt should add boundary
  detection before either is used near a layout's own edge.
- **`Tabs`**: the tab list is a plain flex row with no wrap/scroll
  handling yet — a future feature with many tabs on a narrow viewport
  needs its own `overflow-x-auto` wrapper (matching the pattern
  `SettingsLayout` already uses for its nav).
- **`FormField`/`Input`/`Select`/`Textarea`**: full-width by default
  (`w-full`) so a form's own grid/stack layout controls field width,
  not the control itself.

## What's still a documented gap

Responsive tables, filter drawers, and modal-becomes-fullscreen-on-mobile
behavior remain **not built** (no `DataTable`/`FilterBar` exists yet) —
see `tables.md`'s own contract for where these rules belong once built.
