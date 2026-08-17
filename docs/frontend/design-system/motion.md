# Motion

## Durations and easing (`app/globals.css`)

`--motion-duration-fast` (120ms), `-base` (200ms), `-slow` (320ms).
`--motion-ease-standard` for most transitions, `-decelerate` for
something entering (starts fast, settles), `-accelerate` for something
leaving (starts slow, exits fast) — the standard "objects enter fast,
leave faster" enterprise-UI convention, not decoration.

## The four named animations

| Animation | Used by | What it communicates |
|---|---|---|
| `animate-dialog-in` | `Dialog` | The modal has taken focus — a subtle scale+fade, not a bounce. |
| `animate-drawer-in` | `Drawer` | The panel slid in from the edge it's anchored to. |
| `animate-overlay-in` | `Popover`, `Dropdown`, `Toast` | A lighter-weight layer appeared near its trigger. |
| `animate-collapse-expand` | Reserved — no consumer yet (`Accordion` uses native `<details>`, which doesn't need it) | A region's height changed in response to a user action. |

Every one of these is wrapped in `motion-safe:` so
`prefers-reduced-motion: reduce` disables it — per §10 and §21, this is
enforced per-usage (`motion-safe:animate-*`, `motion-reduce:animate-none`
on spinners), not by a single global media query, so a component that
forgets the prefix is visible in code review.

## What doesn't animate

Hover/focus color transitions use plain `transition-colors` (no custom
duration token — the browser default is already imperceptibly fast and
appropriate). Loading states (`Spinner`) spin continuously but respect
`motion-reduce` by freezing rather than continuing to spin — see
`components/ui/spinner.tsx`.

## What's deliberately not built yet

No page-transition/route-change animation — Next.js App Router
navigations render instantly today, matching §3's "controlled" over
"decorative" direction; nothing in this prompt's foundation needs one.
