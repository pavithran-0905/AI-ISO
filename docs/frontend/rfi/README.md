# RFI / RFP Documentation (structure only)

Per Prompt 001 §29, this establishes the structure and honestly
separates **IMPLEMENTED** from **PLANNED** — nothing here claims future
functionality as currently available.

## Frontend architecture — IMPLEMENTED

Next.js 16 (App Router) + React 19 + TypeScript (strict) + Tailwind CSS
v4, in a `pnpm` workspace. Layered architecture (app → features →
components → foundation) with an enforced one-directional dependency
graph — see `../architecture/dependency-boundaries.md`.

## Technology stack — IMPLEMENTED

TanStack Query (server state), Zustand (client state, two
purpose-scoped stores), React Hook Form + Zod (present as dependencies;
not yet used — no form exists yet), Vitest + Testing Library +
Playwright (testing). See `../architecture/frontend-architecture.md`.

## UX principles — IMPLEMENTED (foundation) / PLANNED (applied)

Design tokens, loading/empty/error states, and layout primitives
implementing Prompt 001 §18's principles exist and are tested. Their
application to a real, information-dense enterprise screen is
**PLANNED** — no business screen exists yet to demonstrate them at scale.

## Design system — IMPLEMENTED (foundation) / PLANNED (component library)

Full token set (color, status, elevation, motion, z-index, focus) in
`app/globals.css`. Component library is minimal today: `Button`, `Card`,
`StatusBadge`, `ThemeToggle`, and the 7 feedback-state primitives.
`components/forms/`, `components/navigation/`, `components/overlays/`
are established, empty directories — **PLANNED**.

## Accessibility — IMPLEMENTED (foundation)

WCAG 2.2 AA target; semantic landmarks, focus-visible treatment,
keyboard operability, and `aria-live` regions verified in every
primitive shipped so far. Dialog/table/chart-specific accessibility
patterns are **PLANNED** (no such components exist yet).

## Security — IMPLEMENTED (frontend UX layer) / backend-authoritative

Bearer-token auth against the real backend contract, with a documented
backend gap (`role`/`organization_id` claims not currently populated at
login — see `../architecture/authentication.md`) rather than an
invented workaround. Frontend authorization is explicitly presentation-only
(`../architecture/authorization.md`) — the backend remains the sole
security authority, always.

## Scalability & maintainability — IMPLEMENTED (foundation)

Feature-module pattern (`features/<feature>/`) established for every
future business module, one enforced dependency direction, centralized
API client and route-metadata registry. **PLANNED**: the pattern
proven at scale by an actual second and third feature.

## Testing — IMPLEMENTED

115 unit/component tests, 2 of 3 e2e specs passing without external
dependencies (the third requires the live gateway — see
`../standards/testing.md`). **PLANNED**: visual regression, dedicated
accessibility (axe-core) test pass, Storybook-driven component testing
(Storybook itself is deferred — see `../README.md`).

## Performance — IMPLEMENTED (defaults) / PLANNED (measured optimization)

Route-level code splitting (free, from Next.js App Router), tuned
TanStack Query caching. Virtualization, memoization, and bundle
analysis are explicitly **not yet done** — Prompt 001 §22 calls for
measuring before optimizing, and nothing has shipped yet that would be
meaningful to measure.

## Responsive design — IMPLEMENTED (foundation) / PLANNED (data-heavy patterns)

Layout-level responsive collapse (`SplitPaneLayout`, `SettingsLayout`)
implemented and tested. Responsive tables, filter drawers, and modal
behavior are **PLANNED** — no table/drawer/modal component exists yet.

## Future extensibility — IMPLEMENTED (foundation)

Every mechanism a future business feature needs (API client, auth,
permissions, routing metadata, layouts, design tokens, error states,
testing setup) exists and is documented. The next frontend prompt is
expected to build the first real feature against this foundation.
