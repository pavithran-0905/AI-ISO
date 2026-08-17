# Design Principles

AI-IOS is an enterprise infrastructure and operations platform. The
visual language communicates reliability, technical sophistication,
operational clarity, trust, precision, enterprise maturity (§3) — not
a consumer product's warmth or a marketing site's polish.

## Use

- Clean typography, strong hierarchy (`lib/typography.ts`'s scale).
- Controlled information density — enterprise operators read a lot of
  data per screen; whitespace is a tool, not a default.
- Restrained color — the 10 status tones (`status-system.md`) carry
  meaning precisely because color is otherwise used sparingly.
- Subtle depth — a border first, elevation only when it communicates
  real hierarchy (`elevation.md`).
- Consistent spacing (`spacing.md`), purposeful borders, minimal but
  meaningful motion (`motion.md`).

## Avoid

- Excessive gradients, glassmorphism, shadows, rounded cards.
- Decorative animation — every motion token in this system exists to
  communicate a state change (open/close, loading, hover), never
  decoration for its own sake.
- Excessive color — a screen with five different accent colors on it
  has none of them meaning anything.
- Consumer-app patterns: no bouncy easing, no illustration-heavy empty
  states, no marketing-style oversized type.
- Inconsistent spacing, giant empty dashboard cards, unnecessary
  visual noise — a `Card` with 200px of empty padding around one
  number is not "clean," it's wasted screen real estate an operator
  has to scroll past.

## What "premium without decorative" means concretely here

Every choice in this system is justified by function: elevation exists
to separate an overlay from the page behind it, not to make a `Card`
"pop." Motion exists to show that a `Dialog` opened, not to delight.
Color exists to carry status meaning, not brand personality. Where a
choice could go either way, the restrained option won — see
`elevation.md`'s explicit preference for borders over shadows as the
concrete example.
