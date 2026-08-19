# Monitoring

Where to check whether AI-IOS's infrastructure is healthy and see
what's changed recently. Only documents what's actually implemented —
there's no metrics/charting page yet (see Known limitations).

Full asset browsing, search, detail, and management now lives in
**Infrastructure** (`/infrastructure`) — see
`docs/frontend/user-guide/infrastructure-inventory.md`. This page still
covers the two things that remain genuinely Monitoring's own: an
at-a-glance health rollup and platform-level service/event visibility.

## Monitoring Overview

Open **Monitoring** from the sidebar (or `/monitoring` directly). It
shows the same organization you've already picked on the Dashboard —
you won't be asked again.

- **Health summary** — how many of your assets are healthy, in
  warning, critical, and so on, plus the total count.
- **Critical issues** — assets currently critical or unreachable, most
  recent first, each linking to its full detail page in Infrastructure.
  If nothing's critical, it says so.
- **Service health** — a short preview of platform service health (see
  Services below).
- **Recent events** — a short preview of what's happened recently (see
  Events below).

## Services

Open **Services** from the tab bar, or `/monitoring/services`. Shows
every platform service AI-IOS has observed, with its current health
and how many other services call it (and how many it calls).

## Events

Open **Events** from the tab bar, or `/monitoring/events`. A
chronological list of platform, infrastructure, deployment,
configuration, and other events, most recent first.

## Search

Asset search moved to Infrastructure's own Assets page — see
`docs/frontend/user-guide/infrastructure-inventory.md`. There's no
separate global monitoring search.

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

## Known limitations

- **No metrics/charts page.** AI-IOS's monitoring backend has metrics,
  but only if you already know a specific metric series' identifier —
  there's no way to browse "what metrics exist" yet, so a general
  metrics browser isn't available.
- **Events aren't linked to a specific asset.** The events feed
  doesn't currently record which asset (if any) an event relates to.
- **"Critical issues" scans a bounded set of assets**, not your
  organization's entire inventory, if you have a very large number of
  assets — use Infrastructure's own Assets page to search all of them.
