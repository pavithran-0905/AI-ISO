# components/overlays/

`Dialog`, `Drawer` (both built on the native `<dialog>` element —
real focus trapping and Escape-to-close for free), `Tooltip`,
`Popover`, `Dropdown` (docs/frontend Prompt 002 §12). `Popover` and
`Dropdown` share `use-dismissable-layer.ts` for click-outside/Escape
handling, since they aren't built on `<dialog>`.
