# Monitoring

Where to check whether AI-IOS's infrastructure is healthy, inspect a
specific asset, and see what's changed recently. Only documents what's
actually implemented — there's no metrics/charting page yet (see Known
limitations).

## Monitoring Overview

Open **Monitoring** from the sidebar (or `/monitoring` directly). It
shows the same organization you've already picked on the Dashboard —
you won't be asked again.

- **Health summary** — how many of your assets are healthy, in
  warning, critical, and so on, plus the total count.
- **Critical issues** — assets currently critical or unreachable, most
  recent first. If nothing's critical, it says so.
- **Service health** — a short preview of platform service health (see
  Services below).
- **Recent events** — a short preview of what's happened recently (see
  Events below).

## Assets

Open **Assets** from the tab bar under Monitoring, or `/monitoring/assets`.
This is the full, searchable list of every asset registered for your
organization.

- **Search** — matches name, hostname, IP, serial number, and similar
  fields.
- **Filters** — narrow by Status or Type. Active filters show a count
  next to the Reset button.
- **Sort** — click any column header to sort by it; click again to
  reverse the direction.
- **Density** — the two icons on the right switch between comfortable
  and compact row spacing. Your choice is remembered.
- The exact search/filter/sort/page you're looking at is reflected in
  the page's URL, so you can bookmark or share it.

Click any asset's name to open its detail page.

## Asset detail

Shows everything AI-IOS knows about one asset: its identity
(hostname, IP, vendor, OS, ...), its current health and status, any
tags and metadata, and any related assets recorded for it (with a
link to jump to each one).

Some technical identifiers (category, class, location, and owner) are
shown as raw IDs rather than names — AI-IOS doesn't yet have a way to
look up what those IDs correspond to.

## Services

Open **Services** from the tab bar, or `/monitoring/services`. Shows
every platform service AI-IOS has observed, with its current health
and how many other services call it (and how many it calls).

## Events

Open **Events** from the tab bar, or `/monitoring/events`. A
chronological list of platform, infrastructure, deployment,
configuration, and other events, most recent first.

## Search

Use the Assets page's own search box (above) — it's real, server-side
search across your organization's assets. There's no separate global
monitoring search beyond that.

## Time range

Not available yet — see Known limitations.

## Refresh

Each Monitoring page has a refresh button (top right) that re-fetches
its data, with an "Updated ⟨time⟩" note showing when it last ran.

## Status meanings

Asset health: **Healthy**, **Warning**, **Critical**, **Unknown**,
plus **Offline** and **Unreachable** for assets AI-IOS can't currently
reach. Service health (on the Services page): **Healthy**,
**Degraded**, **Unhealthy**, **Unknown** — this is a slightly
different scale than asset health, since it's measuring services'
dependency relationships rather than individual machines.

## Troubleshooting

- **A section says "Access denied."** Your account doesn't have
  permission to view that specific data — contact your administrator.
- **A section shows an error with a Retry button.** That data is
  temporarily unavailable; the rest of the page keeps working
  normally. Try Retry, or use the page's own refresh button.
- **An asset shows raw IDs instead of names for category/class/location/owner.**
  This is expected today — see Asset detail, above.

## Known limitations

- **No metrics/charts page.** AI-IOS's monitoring backend has metrics,
  but only if you already know a specific metric series' identifier —
  there's no way to browse "what metrics exist" yet, so a general
  metrics browser isn't available.
- **Events aren't linked to a specific asset.** The events feed
  doesn't currently record which asset (if any) an event relates to.
- **"Critical issues" scans a bounded set of assets**, not your
  organization's entire inventory, if you have a very large number of
  assets — use the full Assets page's search to find something
  specific.
