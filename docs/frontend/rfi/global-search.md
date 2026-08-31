# Global Search & Command Center

Per Prompt 017 §48, this honestly separates **IMPLEMENTED** from
**PLANNED**/**UNAVAILABLE** for the Enterprise Global Search & Command
Center Experience, built by composing existing feature API modules
against six resource types. See `../rfi/README.md` and
`../developer-guide/global-search.md` for the full technical
reasoning.

## Enterprise resource discovery — PARTIALLY IMPLEMENTED (six real types, two others confirmed unbuildable)

Real search across Assets, Users, Alerts, Automations, Reports, and AI
Conversations — the only six resource types with an existing,
already-built list/search API on this backend. Audit Events and
Notifications are excluded: confirmed, on both, that no real route
accepts any free-text query — only exact-match filters exist. Included
anyway only as page-level navigation commands (to `/audit`,
`/notifications`, both real routes), never as approximated resource
search.

## Centralized navigation — IMPLEMENTED (extends the existing command palette)

Built by extending Prompt 003's own command palette
(`components/navigation/command-palette.tsx`), not a second
command-palette library. Ctrl/Cmd+K, a dedicated `/search` results
page with URL-addressable query and scope (`?q=&scope=`), full
keyboard navigation across a combined pages+resources list.

## Multi-module search — IMPLEMENTED (two real strategies, honestly different)

Assets and Users get real, debounced, server-side search — the only
two resource types whose backend route actually accepts a query
parameter. Alerts, Automations, Reports, and AI Conversations get
client-side filtering over an already-fetched, organization-scoped
list, fetched once (not per keystroke) — the same approach this
session's own Reporting feature already uses for its free-text search,
since that service's list route has never supported one either.

## Permission-aware results — IMPLEMENTED (and a pre-existing gap closed)

Users results only appear for administrative sessions. Separately,
this prompt found and fixed a real gap in the *existing* command
palette: navigation commands were never filtered by role before,
meaning an admin-only route (like Users) could be reached through the
palette even when hidden from the sidebar for that session's role.
Now filtered identically to `PrimaryNavigation`'s own check.

## Keyboard accessibility — IMPLEMENTED

Full `combobox`/`listbox`/`option` semantics, `aria-activedescendant`,
arrow-key navigation across the combined result list, Enter to open,
Escape to close (native `<dialog>` behavior), a polite live region for
loading/result-count state, and real `role="group"`/`aria-label`
sectioning — never relying on visual highlighting alone.

## Scalable architecture — IMPLEMENTED

Debounced (200ms) real search, TanStack Query's own stale-response
discarding (never renders an older query's results after a newer one
resolves), and `staleTime`-cached list fetches for the four
client-filtered resource types (never re-fetched per keystroke).

## Responsive UX — IMPLEMENTED

Centered command palette on desktop/tablet; a real full-screen overlay
on mobile (the palette's own `<dialog>` switches to `inset-0`/full
height below the `sm` breakpoint), with a visible close control, per
§38's own "do not constrain mobile search into a tiny dialog."

## Extensibility — PARTIALLY IMPLEMENTED

The adapter pattern (`SearchResult`, one small function per resource
type) makes adding a seventh resource type a contained change — but
only once that resource's own backend route gains a real free-text
filter, or once its existing list is small/stable enough to fetch and
filter client-side the same way Alerts/Reports/Automations/
Conversations already are here.

See `../backend-v1-integration-limitations.md` for the full,
cross-prompt list with source citations.
