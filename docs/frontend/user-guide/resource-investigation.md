# Resource Investigation

Everything AI-IOS knows about an infrastructure asset, in one place.

## Opening a resource

From **Infrastructure → Assets**, click any asset. You can also reach
it directly from global search (**Ctrl+K**, or the Search page).

## Breadcrumbs

Every asset page now shows a real trail — **Infrastructure → Assets →
{asset name}** — so you always know where you are and can jump back a
level.

## Tabs

- **Overview** — identity (name, hostname, IP, vendor, OS, and more),
  current health/status/lifecycle/criticality, and any actions you're
  allowed to take (Edit, Delete).
- **Relationships** — other assets this one is connected to.
- **Topology** — neighbors, dependencies, and impact — the same real
  relationship data as the Topology page, viewed from this asset's own
  perspective. Use **View in Topology** (top right) to open the full
  interactive graph.
- **Configuration** — tags and metadata. Anything that looks like a
  secret (a password, token, or API key) is always shown masked.

Switching tabs is instant and never reloads the page — the URL updates
(`?tab=...`) so you can bookmark or share a specific tab.

## Refresh

The refresh button in the header reloads this asset's own data —
identity, relationships, and topology — without reloading the rest of
the app.

## Ask AI

**Ask AI** opens the AI Assistant with a draft message referencing
this asset by name and ID. It doesn't send anything automatically, and
it's a separate action from the data shown on this page — AI-generated
answers are never presented as backend facts.

## If the asset can't be found

You'll see a clear "not found" message with a way back to the Assets
list and to Search — never a generic error screen.

## What's not here, and why

- **Metrics (CPU, memory, etc.)** — AI-IOS doesn't have a metrics
  endpoint for assets today.
- **Alerts related to this asset** — AI-IOS doesn't record a reliable
  link between an alert and the asset that caused it.
- **Automation runs against this asset** — the same: no reliable link
  exists today, even though the underlying capability is partially
  built on the backend.
- **Reports about this asset** — reports aren't scoped to individual
  assets on this backend.
- **Recent activity/audit history for this asset** — recorded
  internally, but there's no way to read it back today.

## Troubleshooting

- **A section shows "Retry" instead of its content.** That one section
  failed to load — the rest of the page still works; click Retry to
  try again.
- **I don't see an Edit or Delete button.** You don't have permission
  for that action on this asset.
- **The page says the asset wasn't found, but I know the ID is
  right.** It may have been deleted, or the link may be out of date.
