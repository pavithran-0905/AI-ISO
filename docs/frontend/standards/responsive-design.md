# Responsive Design

Primary target: enterprise desktop/laptop. Tablet and a smaller-viewport
fallback are supported, not treated as an afterthought shrink of the
desktop layout.

## What's in place today

- **`SplitPaneLayout` stacks below `md`** rather than squeezing two
  side-by-side panes into a useless sliver — the resize handle itself is
  `hidden md:block`, so there's nothing draggable to confuse a narrow
  viewport with.
- **`SettingsLayout`'s nav** goes from a vertical sidebar (`md:flex-col`,
  fixed width) to a horizontal, scrollable row below `md`
  (`flex-row overflow-x-auto`) — the standard "sidebar becomes a tab
  strip" collapse pattern, not a hidden hamburger reproducing desktop
  navigation awkwardly.
- **`WizardLayout`'s step indicator** is a plain flex row today; it will
  need its own collapse treatment (compact step counter instead of full
  labels) once it's used somewhere with real content to test against.

## Breakpoints

Tailwind CSS v4's own default scale (`sm`/`md`/`lg`/`xl`/`2xl`) is used
as-is — see the note in `app/globals.css` on why spacing/radius/shadow/
breakpoint categories weren't given custom enterprise tokens: that
scale is already a semantic, fixed rem-based progression, and docs/010
names no override.

## What a future feature must still design for

- **Responsive tables**: a horizontally-scrolling table (with a sticky
  first column) or a card-per-row transformation below `md` — no
  reusable `DataGrid`/table primitive exists yet
  (`components/data-display/` only has `Card` today).
- **Filter drawers**: an inline filter bar on desktop collapsing into a
  `components/overlays/` drawer on narrow viewports — neither the filter
  bar nor the drawer primitive exists yet.
- **Modal behavior**: full-screen on narrow viewports vs. a centered
  dialog on desktop, once `components/overlays/` has a `Modal`.
