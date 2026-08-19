# Infrastructure

Where to browse, search, and manage every asset AI-IOS knows about —
the authoritative CMDB. Covers what actually exists in V1: real
create/edit/delete, groups, relationships, topology, and import/export,
alongside the read-only browsing that used to live under Monitoring.

## Infrastructure Overview

Open **Infrastructure** from the sidebar (or `/infrastructure`
directly). It shows the same organization you've already picked on the
Dashboard.

- **Summary** — total assets, total relationships, how many were added
  in the last 30 days, plus real breakdowns by type, health, lifecycle,
  operating system, vendor, and discovery source. A "Computed" timestamp
  shows how fresh these numbers are.
- **Needs attention** — assets currently critical or unreachable, most
  recent first.

## Assets

Open **Assets** from the tab bar, or `/infrastructure/assets`. The
full, searchable, filterable list of every asset registered for your
organization.

- **Search** — matches name, hostname, IP, MAC address, serial number,
  vendor, model, and operating system.
- **Filters** — narrow by Status or Type. Active filters show a count
  next to the Reset button.
- **Sort** — click any column header to sort by it; click again to
  reverse the direction.
- **Density** — switch between comfortable and compact row spacing.
  Your choice is remembered.
- The exact search/filter/sort/page you're looking at is reflected in
  the URL, so you can bookmark or share it.
- **Export** / **Import** — the two buttons near the top run as
  background jobs (useful for a large inventory); a progress panel
  shows status until it finishes, with a download link for export or a
  row-by-row result and rollback option for import.

Click **New asset** to register one, or any asset's name to open its
detail page.

## Asset detail

Shows everything AI-IOS knows about one asset:

- **Identity** — name, hostname, FQDN, IP/MAC address, serial number,
  vendor, model, firmware, OS, architecture, environment, with a
  one-click copy for its internal ID.
- **Actions** — Edit and Delete, if your role allows them.
- **Current state** — health, status, lifecycle, criticality, and when
  it was last updated.
- **Metadata** — tags and any additional key/value data recorded for
  the asset. A value whose key looks like a password, token, or API
  key is always shown masked, regardless of what it actually contains.
- **Relationships** — every recorded connection to another asset (for
  example, "runs on," "depends on"), each linking to that asset's own
  page. You can add a new relationship or remove an existing one if
  your role allows it.
- **Topology** — a structured view of neighbors, dependencies, or
  impact (what would be affected if this asset failed), computed by
  AI-IOS from the relationship graph.
- **Ask AI** — opens a new AI Assistant conversation with a message
  already referencing this asset by name — nothing is sent until you
  choose to send it.

Some technical identifiers (category, class, location, and owner) are
shown as raw IDs rather than names — AI-IOS doesn't yet have a way to
look up what those IDs correspond to.

## Creating and editing an asset

**New asset** needs a name and a type; everything else is optional.
Editing an existing asset only ever changes the fields you actually
touch — nothing you leave alone gets reset. There's no separate
enable/disable button; status is just one of the fields you can change
when editing.

## Deleting an asset

A confirmation dialog explains this removes the asset from every list
and view. It's a soft delete — there's no restore option from this
interface once it's gone.

## Groups

Open **Groups** from the tab bar, or `/infrastructure/groups`. Static,
dynamic, and rule-based groupings of assets. Create one with a name
and type; click a group to see its current membership in a side panel.
Membership is set at creation time — there's no way to add or remove
members from an existing group yet (see Known limitations).

## Monitoring integration

Monitoring's own Overview page still shows a health summary and a
"needs attention" list drawing on this same asset data — clicking
through takes you to the full asset detail page here.

## Related alerts / Related automation

Not available. AI-IOS doesn't currently record any link between an
asset and a specific alert or automation job, so no such section is
shown — this isn't a bug, there's genuinely nothing to display yet.

## Troubleshooting

- **A section says "Access denied."** Your account doesn't have
  permission to view that specific data — contact your administrator.
- **A section shows an error with a Retry button.** That data is
  temporarily unavailable; the rest of the page keeps working
  normally.
- **I don't see New asset, Edit, Delete, Export, or Import.** Your
  role doesn't currently allow that action.
- **An asset shows raw IDs instead of names for category/class/location/owner.**
  Expected today — see Asset detail, above.
- **A relationship shows "(incoming)" next to its type.** That means
  the *other* asset is the one the relationship type describes (for
  example, another asset "depends on" this one) rather than this asset
  doing the action.

## Known limitations

- **No group membership editing.** A group's members are fixed once
  created.
- **No topology graph.** Neighbors/dependencies/impact are shown as a
  structured list, not a visual diagram.
- **No related alerts or automation.** No real connection exists
  between an asset and either today.
- **Metadata isn't editable from this interface**, only viewable.
