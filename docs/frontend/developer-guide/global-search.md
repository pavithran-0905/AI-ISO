# Global Search & Command Center

Built in Prompt 017 by extending the existing command palette
(`components/navigation/command-palette.tsx`, built in Prompt 003 as
navigation-only) with real cross-module resource search — never a
second command-palette library, never a new HTTP call, and never a
fabricated backend "global search" endpoint. See
`docs/frontend/rfi/global-search.md` for the implemented-vs-planned
split and `docs/frontend/backend-v1-integration-limitations.md` for
the full gap list with citations.

## There is no global search API — confirmed, again, across every resource type checked

Prompt 003 already documented that no unified search endpoint exists.
This prompt confirmed the same is true resource-by-resource: **no
list/search route on any of six candidate services accepts a free-text
query parameter except two** — `inventory-service`'s `GET
/inventory/search` (`query`) and `user-management-service`'s `POST
/users/search` (`query`). `alerting-service`'s `GET /alerts`,
`automation-service`'s `GET /automation/jobs`, `reporting-service`'s
`GET /reports`, and `ai-assistant-service`'s `GET /ai/conversations`
all support only `organization_id` plus a few exact-match filters — no
`query`/`q`/`search` parameter of any kind (confirmed by reading each
route's own signature; each API module's own docstring already states
this, established by the prompts that originally built them).

**Two strategies follow directly from that split**, both composing
existing, already-built feature API modules (`features/search/hooks/use-global-search.ts`)
— never a new `fetch`:

- **Assets and Users**: real, debounced (200ms), server-side search.
  Each keystroke (after debounce) produces a new TanStack Query key,
  so a stale in-flight response is simply never rendered once a newer
  query resolves — the standard, no-extra-code mechanism this
  session's query architecture already gives every debounced search
  (§32's "never display results from an older query").
- **Alerts, Automations, Reports, AI Conversations**: no server-side
  query parameter exists, so this feature fetches each
  organization-scoped list **once** (cached via TanStack Query's own
  `staleTime`, not re-fetched per keystroke — §31) and filters
  client-side by title/description substring. This is not a new
  pattern: `features/reporting/pages/reports-list-page.tsx` already
  does exactly this for its own free-text search, since `GET /reports`
  has never supported one either.

Audit events and notifications are **deliberately excluded** from live
resource search — Prompt 015 and Prompt 016 already confirmed neither
has any free-text-searchable field on any real route (only exact-match
filters like `entity_id`/`status`). Approximating a "search" over an
exact-match-only field would be dishonest; both remain reachable only
through the navigation-command layer (`/audit`, `/notifications`
already exist as real routes).

## Search adapter and result model (§41)

`features/search/types/index.ts`'s `SearchResult` — `id`, `resultType`,
`title`, `description`, `status`, `href` — is the only shape any UI
component depends on. `features/search/lib/adapters.ts` maps each real
domain type (`Asset`, `UserSummary`, `Alert`, `AutomationJob`,
`Report`, `Conversation`) into it; a UI change to how one resource type
is fetched never touches the palette or the results page.

## Ranking (§12) — transparent, client-side, never claimed as backend relevance

`features/search/lib/rank.ts`: exact title match → exact id match →
title starts with the query → title contains the query. Within a tier,
`Array.sort`'s stability preserves each source's own real ordering
(e.g. alerts/reports newest-first) as the recency tiebreaker, rather
than this module re-deriving one. No resource's real API returns a
relevance score of any kind — this ranking is never presented as
something the backend computed.

## Command palette extended, not replaced (§39)

`CommandPalette` now also filters `NAVIGATION_COMMANDS` by role —
`route.roles === null || (role !== null && route.roles.includes(role))`,
the exact same check `PrimaryNavigation` already applies to the
sidebar. This closes a real, pre-existing gap: before this prompt, the
palette showed every implemented route regardless of role (including
admin-only ones like Users), even though the sidebar already hid them
— a session-role-restricted user could reach a route through the
palette that the sidebar deliberately kept out of view. Fixed as part
of this prompt's own §23 ("permission-aware results") rather than left
for a future one, since the palette is the same component being
extended here.

A single flat, keyboard-navigable list spans matching pages *and*
every resource group's results, in one fixed order, so Arrow/Enter
work uniformly regardless of what kind of thing is highlighted.

## Recent searches (§21) — local, bounded, never sent anywhere

`state/recent-searches-store.ts` — a small (max 5), `localStorage`-
persisted list of past query *terms* only, never a result payload,
mirroring the existing `useTableDensityStore` persistence pattern. A
term is recorded once its search has actually settled (not on every
keystroke). Clearable. Never sent to any backend — no route accepts
one.

"Recent resources" (recently *viewed* assets/alerts/etc., which §9
also lists as a potential idle-state) was not built: this session has
no existing view-tracking infrastructure to build it against honestly,
and inventing one would be exactly the kind of fabrication this
prompt's own rules forbid. Recent search terms (real, already
buildable) fill the same "useful idle-state navigation" role instead.

## Permissions and multi-tenancy (§23/§24)

Users results are gated to `isAdministrative` sessions only — the same
frontend convenience Users' own nav entry already applies (Prompt 014
found `user-management-service` enforces no server-side authorization
at all; this gate does not fix that, it only avoids surfacing a
results group whose own dedicated page a non-admin session can't even
navigate to). Assets/Alerts/Automations/Reports/AI Conversations are
all scoped to the currently-selected organization
(`useSelectedOrganization`) — no client-side override is offered or
possible, matching every other feature's own multi-tenancy handling
this session established.

## Accessibility (§37)

`role="combobox"` on the input, `role="listbox"` on the results
container, `role="option"` per result with `aria-selected`, real
`role="group"`/`aria-label` per section (Recent searches, Pages, and
each resource type), `aria-activedescendant` tracks the highlighted
item, and a `sr-only`/`aria-live="polite"` status region announces
"Searching…" or a result count — without narrating every keystroke.

## AI integration and the Search/AI distinction (§27/§28)

"Ask AI" appears once a query is typed, in both the palette's footer
and the `/search` results page — reusing the existing, already-built
`AskAiButton` pattern (`/intelligence/assistant?draft=<text>`, a
pre-filled but never auto-sent draft, the same honest mechanism every
other "Ask AI" entry point in this codebase uses; no structured
context-attachment API exists to do more). It is never mixed into the
result groups themselves — Search returns real platform resources;
"Ask AI" is a clearly separate action that opens a different
experience entirely.

## A shared `<dialog>` bug avoided proactively

The palette's own dialog now needs a responsive, full-screen-on-mobile
layout (`hidden ... open:flex`, conditional on the real `[open]` state)
— written this way from the start, applying the exact fix Prompt 015
had to discover the hard way for `Drawer` (an unconditional `flex`
utility on a closed native `<dialog>` stays laid out and intercepts
clicks, since author-origin CSS always wins over the UA stylesheet's
own `display:none` default regardless of specificity).
