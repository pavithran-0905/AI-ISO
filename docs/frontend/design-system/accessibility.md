# Accessibility

Target: WCAG 2.2 AA — a foundation requirement, verified per component
as it was built, not audited after the fact. This extends Prompt 001's
own `docs/frontend/standards/accessibility.md`; that document still
covers the app-wide baseline (landmarks, `aria-live` regions on
`LoadingState`/`PartialDataNotice`/`ErrorState`, reduced motion). This
one covers what Prompt 002 added.

## Colour contrast

Every semantic token pair (`success`/`success-foreground`,
`warning`/`warning-foreground`, ...) is picked for AA contrast against
its own foreground in both themes — `warning`/`pending`/`unknown` use
a dark foreground (`--gray-950`) even in dark mode specifically because
their amber/light-gray backgrounds stay too light for a light
foreground to clear AA. See the `.dark` block in `app/globals.css` for
where this diverges from a naive "invert everything" approach.

## Keyboard

- **`Dialog`/`Drawer`**: native `<dialog>` + `showModal()` — real focus
  trap, Escape closes, focus returns to the trigger on close (browser
  default behavior).
- **`Popover`/`Dropdown`**: `use-dismissable-layer.ts` closes on
  Escape and outside click. `Dropdown` additionally supports
  ArrowUp/ArrowDown/Home/End between menu items (roving focus).
- **`Tabs`**: ArrowLeft/ArrowRight/Home/End move both focus and
  selection, roving `tabindex` (only the active tab is in the natural
  tab order) — the standard WAI-ARIA Tabs pattern.
- **`Accordion`**: native `<details>`/`<summary>` — Enter/Space toggle,
  natively.
- **`Switch`**: a real `<input type="checkbox" role="switch">` — Space
  toggles, natively.
- **`SplitPaneLayout`'s resize handle** (Prompt 001): ArrowLeft/
  ArrowRight adjust the split — unchanged, verified still working.

## Every interactive component has an accessible name (§21)

`IconButton`'s `aria-label` prop is required at the type level, not
just documented — a caller physically cannot render one without an
accessible name. `Tooltip` wires `aria-describedby` from its trigger to
the tooltip bubble automatically.

## Forms

`FormField` wires `aria-describedby` (pointing at whichever of
description/error is present), `aria-invalid`, and `aria-required`
onto the control automatically — see `forms.md`.

## Status

Every `StatusIndicator`/`StatusBadge` pairs an icon with a text label
(§5: "status colours must not rely only on colour... every status
presentation must also support: icon, label, text") — never a bare
colored dot with no label.
