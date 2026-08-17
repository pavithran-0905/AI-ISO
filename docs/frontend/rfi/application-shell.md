# Application Shell

Per Prompt 003 §41, this honestly separates **IMPLEMENTED** from
**PLANNED** for the enterprise application shell and navigation layer —
nothing here claims future functionality as currently available. See
`../rfi/README.md` for the Prompt 001 foundation this builds on.

## Enterprise navigation — IMPLEMENTED

A full application shell (global header, collapsible primary sidebar,
breadcrumbs, page-header framework, command palette) with a canonical
7-group information architecture (Overview, Operations, Automation,
Intelligence, Governance, Administration, Platform) derived directly
from the real backend service catalog
(`docs/frontend/backend-feature-matrix.md`), not invented. Every route
carries centralized metadata (`lib/route-registry.ts`) consumed
identically by the sidebar, breadcrumbs, and command palette — no
duplicated navigation data to drift out of sync.

Unbuilt pages are registered as `"planned"` and shown disabled with a
badge, never as a working link to a page that doesn't exist — an
explicit anti-"fake page" guarantee, not just a convention.

## Accessibility — IMPLEMENTED (foundation)

Every new interactive shell element consumes Prompt 002's accessible
primitives rather than custom fragile focus code: the command palette,
the narrow-viewport navigation drawer, and (already, from Prompt 002)
`Dialog`/`Drawer` are all built on the native `<dialog>` element, which
gives a real focus trap, top-layer stacking, and Escape-to-close for
free from the browser rather than reimplemented in JavaScript.
`Popover`/`Dropdown`-based overlays (notifications, the account menu)
share one hook (`useDismissableLayer`) for Escape and outside-click
dismissal. The account menu and command palette both implement full
arrow-key/Home/End keyboard navigation; the resizable split-pane
divider is a proper ARIA separator (`aria-valuenow`/`min`/`max`) with
keyboard resize support. Every route change goes through Next.js App
Router's own built-in focus handling rather than custom route-change
focus code.

**PLANNED**: a dedicated axe-core automated accessibility test pass
(still not run — see `../design-system/accessibility.md`'s own
tracked gap from Prompt 002); manual screen-reader verification.

## Responsive design — IMPLEMENTED

Three distinct regimes, not one shell "shrunk" to fit: a persistent,
user-collapsible sidebar at `md` and up; the same icon-collapse mode
covering the tablet range; and, below `md`, the sidebar is replaced
entirely by an accessible slide-over drawer (native `<dialog>`,
opened by a header hamburger trigger, closes on link selection) — per
§11's explicit "do not simply shrink the desktop sidebar." Layout
primitives (`SplitPaneLayout`, `SettingsLayout`) standardized this
prompt to collapse to a stacked layout below `md` as well.

**PLANNED**: responsive tables and filter drawers — no `DataTable`
component exists yet to need them (tracked in
`../design-system/tables.md`).

## Role-aware / permission-aware UX — IMPLEMENTED (mechanism) / PLANNED (applied)

`PrimaryNavigation` filters every navigation group's routes through
the existing permission architecture (`permissions/hooks.ts`,
Prompt 001) — a route can declare `roles: RoleName[]` and it's hidden
from a session whose role isn't in that list. This is deliberately
**presentation-only**: it is not, and is not claimed to be, a security
boundary (`../architecture/authorization.md`). The mechanism is real
and tested; it isn't yet exercised by a real restricted route, because
the backend doesn't currently populate a `role` claim reliably at
login (documented gap, `../architecture/authentication.md`) — every
route today ships with `roles: null` (visible to all) rather than
guessing at a role model the backend hasn't confirmed.

## Modular architecture — IMPLEMENTED

The shell is data-driven from one registry (`ROUTE_REGISTRY`), not
hand-wired per page: adding a route to the array is the entire
integration surface for the sidebar, breadcrumbs, and command palette
simultaneously. Shell composition (`Header`, `PrimaryNavigation`,
`Breadcrumbs`, `Footer`) is assembled once in `MainLayout`, which owns
chrome only and never feature content — matching Prompt 001's
app → features → components → foundation dependency direction.

## Maintainability — IMPLEMENTED

251+ shell/navigation-specific unit tests (behavior-based: active
route highlighting, permission filtering, planned-vs-implemented
rendering, keyboard interaction, responsive drawer open/close/dismiss)
alongside the existing Prompt 001/002 suite. Every documented decision
(the tablet/desktop breakpoint split, the notification and
global-search backend gaps, the permission-filter mechanism-vs-applied
distinction) is written down in `../developer-guide/application-shell.md`
rather than left implicit in code.

## Extensibility — IMPLEMENTED

A future feature prompt's entire navigation integration is one
`ROUTE_REGISTRY` entry (flip `planned(...)` to `implemented(...)` with
a real `path`) — no sidebar, breadcrumb, or command-palette code needs
to change. New nav groups extend `NAV_GROUPS`/`NAV_GROUP_META`. The
"planned, not fake" pattern means the full 51-service information
architecture is already navigable-in-outline today, even though most
pages behind it don't exist yet.

## What's still explicitly PLANNED

- **Global search** — the command palette searches pages, not records;
  a real cross-feature search needs a backend endpoint that doesn't
  exist yet.
- **Notifications** — UI foundation (badge, panel, empty/loading/error
  states) is built and tested, but always shows the empty state; no
  confirmed `services/notification-center-service` read/list contract
  was available this prompt.
- **A real login page** — the account menu, `AuthGuard`'s `?from=`
  return-to destination, and the 401 page's "you'll return to..."
  copy are all ready for one, but none exists yet.
- **Nested breadcrumb trails** — `getBreadcrumbTrail` is currently
  flat (every route is one level deep in the registry); a route
  hierarchy deeper than one level isn't modeled yet because nothing
  needs it yet.
