# Application Shell

The enterprise shell built in Prompt 003, on top of Prompt 001's
foundation and Prompt 002's design system. This document covers
architecture and extension rules — see `docs/frontend/user-guide/navigation.md`
for user-facing behavior.

## Shell architecture

```
layouts/main-layout.tsx          MainLayout — composes the shell
  layouts/main/header.tsx        Header — brand, search/command-palette
                                  trigger, help, notifications, theme,
                                  account menu, mobile nav trigger
  components/navigation/primary-navigation.tsx
                                  PrimaryNavigation — desktop sidebar +
                                  narrow-viewport drawer, same data
  components/navigation/breadcrumbs.tsx
                                  Breadcrumbs — derived from route metadata
  {children}                     Page content (starts with PageHeader)
  layouts/main/footer.tsx        Footer
```

`MainLayout` owns shell chrome only — it never renders feature
content directly. A page under `app/(app)/` is expected to render its
own `PageHeader` (`components/navigation/page-header.tsx`) as the
first thing inside its content, followed by whatever the feature
needs.

`CommandPalette` (`components/navigation/command-palette.tsx`) is
mounted once, globally, in `providers/app-providers.tsx` — not inside
`MainLayout` — so `Ctrl`/`Cmd+K` works from any route, including ones
that don't use `MainLayout`.

## Route metadata / navigation registry

`lib/route-registry.ts` is the single source of truth for every
route's metadata: `id`, `path`, `title`, `description`, `breadcrumb`,
`navGroup`, `navLabel`, `icon`, `roles`, `feature`, `visibility`
(`"implemented" | "planned" | "hidden"`), `layout`, `analyticsId`,
`external`, `showInNav`.

Two builder helpers construct entries:

- `implemented({...})` — a page that's actually shipped. Requires a
  real `path`.
- `planned({...})` — on the roadmap, not built. `path` defaults to
  `/${navGroup}/${id}` when omitted; `layout` defaults to `"main"`.
  Never renders as a real link (see "Planned, not fake" below).

Query functions built on top of the registry:

- `getRouteMeta(path)` / `getRouteById(id)`
- `getNavRoutes()` — routes with `showInNav: true` and a non-null
  `navGroup`
- `getNavGroups()` — `getNavRoutes()` grouped by `NAV_GROUPS` order,
  skipping empty groups; this is what `PrimaryNavigation` and
  `CommandPalette` both render from
- `getBreadcrumbTrail(path)` — currently returns `[route]` for a
  registered path (flat; every route today is one level deep) or `[]`
  for an unregistered one

**Adding a route**: add one entry to `ROUTE_REGISTRY` via `implemented`
or `planned`. Nothing else needs to change — the sidebar, breadcrumbs,
and command palette all read from this one array.

### "Planned, not fake" pattern

A `"planned"` route is real metadata (so its place in the taxonomy is
decided and testable) but never gets a working link: `PrimaryNavigation`
renders it as a disabled row with a "Planned" badge, and
`CommandPalette` excludes it entirely (`NAVIGATION_COMMANDS` filters
to `visibility === "implemented"`). When a feature prompt actually
builds the page, flip its registry entry to `implemented({...})` with
a real `path` — the nav and command palette pick it up automatically.

## Navigation groups (information architecture)

`NAV_GROUPS` (`lib/route-registry.ts`) is the canonical 7-group
taxonomy — Overview, Operations, Automation, Intelligence, Governance,
Administration, Platform — derived from
`docs/frontend/backend-feature-matrix.md`'s own service groupings, not
invented. `NAV_GROUP_META` pairs each group with its label and Lucide
icon.

## Permission-aware navigation

`PrimaryNavigation` filters each group's routes through
`usePermissions()` (`permissions/hooks.ts`, Prompt 001): a route with
`roles: null` is visible to everyone; a route with a `roles` array is
only shown when the current session's `role` is included. This is a
**presentation-only** filter — it improves the UX by hiding what a
role can't use, but it is not a security boundary (see
`docs/frontend/architecture/authorization.md`). Every `ROUTE_REGISTRY`
entry today has `roles: null` since the backend doesn't yet populate a
`role` claim reliably at login (`docs/frontend/architecture/authentication.md`)
— the filtering logic is real and tested, just not yet exercised by
real restricted routes.

## Layouts integrated

- **`MainLayout`** — the primary shell (above).
- **`FullscreenLayout`** — unchanged contract from Prompt 001: no
  chrome, full height, optional `topBar` slot. Verified ready for a
  future immersive view (topology, log viewer, editor); still nothing
  renders through it yet.
- **`SplitPaneLayout`** — standardized this prompt: the resize divider
  now exposes `aria-valuenow`/`aria-valuemin`/`aria-valuemax` (a
  proper ARIA separator, not just `role="separator"`) and supports
  `Home`/`End` to jump to the pane's min/max, in addition to the
  existing `ArrowLeft`/`ArrowRight`. Falls back to a stacked layout
  below `md` (`SplitPaneLayout`'s own `md:flex-row`).
- **`WizardLayout`** — standardized this prompt: `WizardStep` now
  accepts an optional `status: "invalid"`, rendered as an error
  indicator on that step instead of its number/checkmark, so a
  multi-step flow can surface per-step validation state. Previous/next,
  save/cancel, and confirmation screens are still just ordinary steps
  through the existing `footer` slot and `children` — this component
  owns the indicator and frame only.
- **`SettingsLayout`** — extended this prompt with a required `title`,
  an optional `actions` slot (save/cancel), and `hasUnsavedChanges`
  (shows an "Unsaved changes" indicator and adds a `beforeunload`
  guard). Blocking in-app navigation away from a dirty form is left to
  the feature that knows what "leave" means for it — out of scope for
  a generic layout.

## Command palette

`components/navigation/command-palette.tsx` — a native `<dialog>`
(same primitive as `Dialog`/`Drawer`, so it gets a real focus trap and
Escape-to-close for free), opened via `Ctrl`/`Cmd+K` (global listener)
or `useCommandPaletteStore().show()`. Lists every `"implemented"`
route (independent of `showInNav` — `/design-system` is reachable this
way but not in the sidebar), filtered by title/description substring
match. `ArrowUp`/`ArrowDown` move the highlighted result, `Enter`
navigates and closes.

**Status: foundation only.** It searches pages, not records — see
Global Search below.

## Global search

There is no separate global-search UI. The command palette's own
page-search *is* today's global search entry point — a real
cross-feature record search (e.g., "find incident #4021") needs a
backend endpoint that doesn't exist yet. Documented here rather than
built against a guessed contract, per the backend-freeze rule.

## Notification UI

`components/navigation/notification-area.tsx` — a `Popover`-based
panel with an unread-count badge and loading/error states, all
implemented and ready, but never triggered: `unreadCount` is hardcoded
to `0` and the panel always renders its empty state. See the module's
own docstring — no confirmed REST read/list contract for
`services/notification-center-service` was available during this
prompt, and wiring a fetch to an unverified endpoint would risk
inventing one. Wire `features/notifications` to a real API function
once the contract is confirmed; the UI shell doesn't need to change.

## Error boundaries

`app/error.tsx` and `app/global-error.tsx` (Prompt 001) are unchanged
by this prompt. `app/not-found.tsx` (404), `app/unauthorized/page.tsx`
(401), and `app/forbidden/page.tsx` (403) were all enhanced this
prompt — see "Enhanced states" below.

### Enhanced states

- **404** (`app/not-found.tsx`): now shows the attempted path and a
  "Go back" (`router.back()`) action alongside "Back to dashboard".
- **401** (`app/unauthorized/page.tsx`): reads a `?from=` query param
  (set by `AuthGuard`) and shows "You'll return to `<path>` once
  signed in" — the return-to destination for a future login page.
  There's no "log in" action yet since no login page exists.
- **403** (`app/forbidden/page.tsx`): adds "Go back" alongside "Back to
  dashboard". `AccessDeniedState`'s own copy still avoids exposing
  which specific role/permission was required.

## Responsive behavior

- **`md:` and up** — `PrimaryNavigation` renders as a persistent,
  collapsible-to-icons sidebar (`hidden md:flex` on the desktop
  `<nav>`).
- **Below `md`** — the persistent sidebar is hidden; a native
  `<dialog>`-based drawer (left-anchored, same focus-trap/Escape
  primitive as `Drawer`) is opened via the header's hamburger button
  (`useMobileNavStore`) and closes itself when a link is chosen.
  Tailwind's stock breakpoints don't distinguish "tablet" from
  "desktop" any finer than `md`/`lg` without inventing a custom one;
  the existing icon-collapse mode is what covers the tablet range, and
  the drawer covers the narrow-viewport case specifically.
- `SplitPaneLayout` and `SettingsLayout` each collapse to a stacked
  layout below `md` (see Layouts above).

## Extension rules

- **New route**: add one `ROUTE_REGISTRY` entry (`lib/route-registry.ts`).
  Don't hand-write nav links, breadcrumb strings, or command-palette
  entries anywhere else.
- **New nav group**: add to `NAV_GROUPS` and `NAV_GROUP_META` — don't
  invent a group name inline on a route.
- **A page not yet built**: register it as `planned(...)`, never as a
  real link to a route that 404s.
- **New shell chrome** (e.g. a second header action): add it to
  `Header` directly — keep it to genuinely global, high-frequency
  actions per §6's own scoping (identity, search, notifications, help,
  theme, account). Feature-specific actions belong in that page's own
  `PageHeader`, not the shell.
- **Design tokens only**: every shell element consumes Prompt 002's
  token set (`app/globals.css`) — no arbitrary colors, spacing,
  radius, shadows, or a competing icon library. New icons come from
  `lucide-react`, the same library already in use throughout.
