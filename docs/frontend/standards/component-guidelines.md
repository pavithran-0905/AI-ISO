# Component Guidelines

## Generic components stay generic

Everything in `components/` (`Button`, `Card`, `EmptyState`,
`SettingsLayout`, ...) must work with zero knowledge of any specific
backend service, feature, or business concept. `SettingsLayout` takes
plain `href`/`label` items and a `renderNavLink` render-prop rather than
importing Next's `<Link>` or any specific feature's route list — it
works identically in a test (a plain `<a>`) and in the real app (a
`next/link`).

If a "generic" component starts needing an `if (feature === ...)`
branch, it isn't generic anymore — move the business-specific part into
the feature that needs it, and keep (or extract) the reusable part.

## Composition over configuration explosion

`Button`'s `buttonVariants(variant, className)` export (added during
this prompt, to back `not-found.tsx`'s "Back to dashboard" link) is the
concrete example: rather than teaching `Button` an `asChild`/Slot
composition API (a real dependency this project doesn't otherwise need,
per Prompt 001 §4's "before installing a package, check whether the
capability already exists"), the visual style itself was extracted so a
plain `<Link>` can carry it directly.

## Every reusable component ships with:

- Its implementation and (where the props aren't self-evident) a short
  module-level comment explaining *why* it exists or a non-obvious
  constraint — not a restatement of its props.
- A test in `tests/unit/<mirrored-path>/`.
- Accessibility considered at creation, not retrofitted — see
  `accessibility.md`.
- A Storybook story, **once Storybook is set up** (deferred — see
  `docs/frontend/README.md`'s status note). Until then, the test file is
  the executable documentation of a component's behavior.

## Layouts vs. components

A **layout** (`layouts/`) owns page-level structure (header/content/
footer, a resizable split, a wizard's step indicator) and is used once
or a handful of times, at route-group granularity. A **component**
(`components/`) is a smaller, composable primitive used many times
within a page. When in doubt: if it wraps `{children}` and defines the
overall page shape, it's a layout.
