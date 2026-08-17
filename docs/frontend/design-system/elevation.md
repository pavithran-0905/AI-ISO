# Borders, Radius, Elevation

## Radius

Tailwind's default scale, used restrained: `rounded-md` (buttons,
inputs, badges' pill shape aside), `rounded-lg` (cards, surfaces,
dialogs, popovers). Nothing uses `rounded-xl`/`rounded-2xl` — per §9,
"do not make every element look like a floating card." `rounded-full`
is reserved for genuinely circular/pill shapes (`Badge`, `StatusBadge`,
`Switch`'s track/thumb, avatar placeholders).

## Border widths

`--border-width-hairline` (1px) is the default for every `border`
usage. `--border-width-emphasis` (2px) exists for the rare case a
border itself needs to carry emphasis (currently unused — reserved for
a future selected/active state that shouldn't rely on color alone).

## Elevation — prefer a border first

Three tiers (`--elevation-1/2/3`, mapped to `shadow-elevation-1/2/3`):

| Tier | Use | Example |
|---|---|---|
| 1 | A subtly raised surface still part of the page flow. | `Surface` in `raised` mode (a sticky toolbar). |
| 2 | A floating panel anchored to a trigger. | `Popover`, `Dropdown`. |
| 3 | A layer above everything, including other overlays. | `Dialog`, `Drawer`, `Surface` in `overlay` mode. |

**Most panels use a border (`Surface`'s default `flat` mode, `Card`),
not elevation** — §9 says "use elevation only when it communicates
hierarchy." A `Card` sitting on the page next to other cards has no
hierarchy to communicate; a `Popover` floating above the page does.
Reach for elevation only when a layer is genuinely *above* something
else, not to make a panel look nicer.
