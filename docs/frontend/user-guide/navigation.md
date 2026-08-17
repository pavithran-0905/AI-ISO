# Navigation

The enterprise application shell built in Prompt 003. This document
covers only what's actually running in `apps/frontend` today — pages
marked "Planned" in the sidebar aren't described here as if they exist.

## Application shell

Every signed-in screen shares the same frame: a global header across
the top, primary navigation down the left, a breadcrumb bar, and the
page content itself. `Footer` runs along the bottom. The shell is the
same on every page — only the content area changes.

## Sidebar

The left-hand primary navigation lists every business area. It's
grouped under seven sections — Overview, Operations, Automation,
Intelligence, Governance, Administration, Platform — matching how the
backend's own services are organized, not an arbitrary layout.

A section with only one page (today, just **Dashboard** under
Overview) shows as a single link. A section with several pages shows
as an expandable header — click it to reveal or hide its pages; AI-IOS
remembers which sections you've collapsed.

Some pages are marked **Planned** with a small badge instead of being
clickable. That means the page is on the roadmap and its place in the
navigation is already decided, but the screen itself hasn't been built
yet — clicking it does nothing on purpose, rather than sending you to
a broken or empty page.

## Collapsed sidebar

The button at the top of the sidebar shrinks it to icons only, useful
on a smaller screen or if you just want more room for the page
content. Hover or focus an icon to see its label in a tooltip. Your
choice is remembered the next time you open AI-IOS.

## Navigation on a narrow screen (phone/small tablet)

Below a certain screen width the sidebar isn't shown inline — instead
a menu (☰) button appears at the top left of the header. Tap it to
open navigation as a panel that slides in from the left; tap a page,
or tap outside the panel, or press Escape, to close it again.

## Breadcrumbs

The bar just under the header shows where you are — for example
"Dashboard" on the dashboard. Earlier segments (once pages are nested
more than one level deep) are clickable; the current page is shown in
bold and isn't a link.

## Page headers

Each page's own title area — its name, an optional short description,
a status indicator where relevant, and any actions for that page (like
"Create" or "Export") — appears consistently at the top of the page
content, below the breadcrumb.

## Global search / command palette

Click the search box in the header ("Search pages and commands…"), or
press **Ctrl+K** (**Cmd+K** on macOS) from anywhere, to open the
command palette. Type to filter; every page you can currently navigate
to is searchable by name or description. This is also today's global
search — there's no separate full-text search across records yet (see
Known Limitations below).

## Notifications

The bell icon in the header opens the notification panel. It's
currently always empty — AI-IOS doesn't yet have a way to fetch real
notifications from the backend, so rather than show fake data, the
panel honestly shows "No notifications yet." This will start showing
real notifications once that's wired up in a future update.

## User menu

The account icon in the header opens your menu. If you're signed in,
it shows your email, role, and organization (or "Not assigned" /
"No organization" if the backend hasn't provided one yet), plus
Preferences, Documentation, and Sign out. If you're not signed in yet,
only Documentation is shown — AI-IOS doesn't have a sign-in page yet
either (see Known Limitations).

## Keyboard shortcuts

| Shortcut | Action |
| --- | --- |
| `Ctrl`/`Cmd` + `K` | Open the command palette |
| `Tab` / `Shift+Tab` | Move between links, buttons, and menu items |
| `Enter` / `Space` | Activate the focused link or button |
| `↑` / `↓` | Move the highlighted result in the command palette, or between items in a menu |
| `Home` / `End` | Jump to the first/last item in a menu |
| `Escape` | Close the command palette, a menu, a panel, or the mobile navigation drawer |

## Theme selection

The sun/moon button in the header switches between light and dark
theme (Prompt 001/002). Your choice is remembered across visits.

## Known limitations

- **No sign-in page yet.** The user menu and route guards are built,
  but there's nothing to sign in with today — every visitor is shown
  the unauthenticated view.
- **No separate full-text search.** The command palette only searches
  the pages you can navigate to, not records inside a feature (e.g. a
  specific incident or user). A real global-search backend endpoint
  doesn't exist yet.
- **Notifications are always empty.** See above — this is intentional
  until a real notifications API contract is confirmed.
