# Dashboard

The AI-IOS dashboard — your starting point for understanding whether
the platform is healthy, what needs attention, and where to go next.
Built in Prompt 005 and evolved into the full Executive Command
Center in Prompt 020. Only documents what's actually implemented.

## Choosing an organization

Most of the dashboard's data is scoped to one organization. If you
belong to only one, it's selected automatically. If you belong to
more than one, you'll see a **Choose an organization** prompt — pick
one to see its dashboard. Your choice is remembered the next time you
open AI-IOS. If your account doesn't belong to any organization, the
dashboard explains that and tells you to contact your administrator —
there's nothing to show until you do.

## Executive and Operations mode

Two modes, switchable at the top of the page (**Executive** /
**Operations**) — both read the exact same underlying data, just with
a different set of extra widgets below the always-visible core:

- **Executive** — adds Reporting and AI Insight.
- **Operations** — adds a shortcut into Operations Workspace.

Your choice is remembered for next time, and it's also saved in the
page's URL (`?mode=`), so a link you share opens in the same mode.

## Overview (KPI cards)

A row of key numbers for your organization: Users, Projects, Assets,
Workflows, Automations, Validations. These are live counts, not
estimates — there's no "up/down from last week" indicator, because
AI-IOS doesn't yet have enough historical data to show a trend
honestly.

## Asset health

The real health of every registered asset — Healthy, Warning,
Critical, Unknown, Offline, Unreachable — shown as a compact
distribution bar with counts. A small status badge next to the page
title ("Platform Healthy" / "Warning" / "Critical") summarizes this at
a glance; it only appears once there's real asset data to summarize.

## Operational health

A summary of every backend service registered for your organization,
grouped by status (Healthy, Warning, Degraded, Critical, Maintenance,
Unknown) with a count for each. This is a different, coarser signal
than Asset health above — it reflects gateway/service reachability,
not any one asset's own condition.

## Attention required

Your organization's currently active (not resolved, closed, or
expired) alerts, most severe first. If nothing needs attention, this
says so plainly: "No active alerts."

## Recent automation activity

Your organization's most recent automation runs, each with a status
(Running, Completed, Failed, Cancelled, and a few others) and how long
ago it happened.

## System status

A compact, per-service list of exactly what's registered and its
current status, latency, and any reported error — the detailed view
behind the Operational Health summary above.

## Quick access

One-click links into every module available to you — only shows
modules you actually have access to.

## Additional insights (optional widgets)

Below the core sections, a set of smaller widgets round out the
picture:

- **Recent activity** — a real, audit-based activity feed (the last
  24 hours), separate from automation-specific "Recent automation
  activity" above.
- **Infrastructure** — inventory size and relationships.
- **Notifications** — your recent notifications.
- **Reporting** (Executive mode) — recent report-generation activity.
- **AI Insight** (Executive mode) — see below.
- **Operations Workspace** (Operations mode) — a shortcut into
  investigating active alerts and automation activity together.

Use the **Customize** button (top right) to hide any of these you
don't need — your choice is remembered on this device.

## AI Insight

A clearly-labeled card, never itself a source of generated analysis —
it shows a real count of AI recommendations awaiting your review, and
an **Ask AI** button that opens a fresh Assistant conversation with a
draft message about the current situation. Nothing is sent
automatically.

## Refreshing

The refresh button (top right) re-fetches every section at once. The
"Updated ⟨time⟩" note next to it shows how long ago the data was last
refreshed. Sections also refresh in the background on their own
schedule, so the numbers stay reasonably current even without pressing
refresh.

## Empty and degraded states

Every section handles its own data independently — if one section
can't load (for example, if a particular backend service is
temporarily unreachable), the rest of the dashboard keeps working
normally, and the affected section shows a clear message with a Retry
button. If your account doesn't have permission to view a particular
section's data, that section says so plainly rather than showing a
generic error.

## Troubleshooting / known limitations

- **No trend/percentage-change indicators.** AI-IOS doesn't fabricate
  a "+12% this week" figure without real historical data to back it.
- **A widget I hid isn't there any more.** Open **Customize** and
  re-check it.
- **No custom filters or time-range selection** — not backed by real
  data support yet.
- **No dedicated Topology summary widget** — asset relationships need
  a specific asset to show anything meaningful; the Infrastructure
  widget shows the one real, organization-wide relationship count
  instead, with a link into the full Topology experience.
