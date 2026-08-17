# Colour System

Full token reference — see `app/globals.css` for the source of truth;
this document explains the *structure*, not a duplicate of every value
(which drifts the moment one changes).

## Layer 1 — Primitives

One neutral scale (`--gray-0` through `--gray-950`) and one accent hue
each for blue (primary/info), cyan (accent/running), green (success),
amber (warning/pending/degraded), red (danger). Never referenced by a
component — only Layer 2 tokens below reference these.

## Layer 2 — Semantic

| Token | Purpose |
|---|---|
| `background` / `foreground` | The page's own base. |
| `surface` / `surface-muted` / `surface-elevated` | Three panel backgrounds: default, recessed (e.g. a code block), raised above the page. |
| `card` / `card-foreground` | `Card`'s own background — currently equal to `surface`. |
| `border` / `border-muted` | Standard hairline vs. a barely-visible separator. |
| `input` | Form control backgrounds — distinct from `surface` so a themed input can diverge from panel backgrounds later without touching every panel. |
| `ring` | The focus-visible ring color — see `accessibility.md`. |
| `primary` / `primary-foreground`, `secondary` / `secondary-foreground`, `accent` / `accent-foreground` | The three brand-adjacent tones. `accent` is new in this prompt (cyan) — used sparingly, e.g. a "new"/highlighted state. |
| `muted` / `muted-foreground` | De-emphasized backgrounds/text — the single most-used pair in the app. |
| 10 status tones | See `status-system.md`. |

Every semantic token is re-picked (not inverted) for `.dark` — see the
comment in `app/globals.css` above the `.dark` block for the specific
rules (surfaces step up in lightness with depth, borders lighten
rather than darken, every status tone re-picked for dark-background
contrast).

## Layer 3 — Component tokens

`--focus-ring-width`, `--border-width-hairline`, `--border-width-emphasis`
— the few values specific enough to a component's own rendering that
they don't belong on the semantic layer, but are still tokens (never a
raw `2px` typed into a component).

## Rule

No component may reference a Layer 1 primitive or a raw color value.
`grep -rn "oklch(" components/ app/ --include=*.tsx` should only ever
match `app/globals.css`.
