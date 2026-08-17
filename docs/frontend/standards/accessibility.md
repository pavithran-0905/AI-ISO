# Accessibility

Target: WCAG 2.2 AA. Established as a foundation requirement, not a
final-QA pass — every primitive built in this prompt already applies
the rules below; nothing was postponed.

## What's already in place

- **Semantic HTML + landmarks.** `layouts/main/header.tsx` is a real
  `<header>` (`role="banner"`), `layouts/main/footer.tsx` a real
  `<footer>` (`role="contentinfo"`) — verified directly in
  `tests/unit/layouts/main/*.test.tsx` via `getByRole`, not just visual
  inspection.
- **Focus visibility.** One consistent `:focus-visible` treatment
  (`app/globals.css`), applied via `focus-visible:ring-2
  focus-visible:ring-ring` on every interactive primitive (`Button`,
  the `SplitPaneLayout` resize handle). Deliberately `:focus-visible`,
  not `:focus` — no visible ring on mouse click, still visible on
  keyboard navigation.
- **Keyboard operability.** `SplitPaneLayout`'s resize handle
  (`role="separator"`, `tabIndex={0}`) responds to `ArrowLeft`/
  `ArrowRight`, not just pointer drag — tested in
  `tests/unit/layouts/split-pane-layout.test.tsx`.
- **`aria-live`/status regions.** `LoadingState` and
  `PartialDataNotice` use `role="status"`; `ErrorState`,
  `AccessDeniedState`, and `OfflineState` use `role="alert"` — a screen
  reader announces the state change without the app needing a separate
  live-region manager.
- **Decorative content hidden correctly.** Every Lucide icon used
  purely decoratively carries `aria-hidden="true"`; `Skeleton` itself is
  `aria-hidden` (the surrounding `role="status"` region is what should
  be announced, not the placeholder shape) — see the comment in
  `components/feedback/skeleton.tsx`.
- **Reduced motion.** `motion-reduce:animate-none` on every
  `animate-spin`/`animate-pulse` usage (`LoadingState`, `Skeleton`).
- **Forms**: no form exists yet (Prompt 001 §34) — the standard to apply
  once one does: every input has a real `<label>` association, errors
  are announced via `aria-describedby` + `role="alert"`, not color
  alone.

## What a future feature must still do

- **Dialogs** (`components/overlays/`, not built yet): focus trap, focus
  return to the trigger on close, `Escape` to dismiss, `aria-modal`.
- **Tables** (`components/data-display/`, only `Card` exists today):
  real `<table>`/`<th scope>` semantics for tabular data, not styled
  `<div>` grids.
- **Charts** (not built yet): a text/table alternative for the same
  data, not a canvas/SVG with no accessible fallback.
