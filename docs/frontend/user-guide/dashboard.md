# Dashboard

The AI-IOS dashboard — your starting point for understanding whether
the platform is healthy and what needs attention. Only documents what's
actually implemented.

## Purpose

Opening AI-IOS takes you straight to the dashboard, which is built to
answer, at a glance: is anything unhealthy, what needs my attention,
what's changed recently, and where should I go next.

## Choosing an organization

Most of the dashboard's data is scoped to one organization. If you
belong to only one, it's selected automatically. If you belong to
more than one, you'll see a **Choose an organization** prompt — pick
one to see its dashboard. Your choice is remembered the next time you
open AI-IOS. If your account doesn't belong to any organization, the
dashboard explains that and tells you to contact your administrator —
there's nothing to show until you do.

## Overview (KPI cards)

A row of key numbers for your organization: Users, Projects, Assets,
Workflows, Automations, Validations. These are live counts, not
estimates — there's no "up/down from last week" indicator, because
AI-IOS doesn't yet have enough historical data to show a trend
honestly.

## Operational health

A summary of every backend service registered for your organization,
grouped by status (Healthy, Warning, Degraded, Critical, Maintenance,
Unknown) with a count for each. This reflects the platform's real,
current health — not just whether the dashboard page itself loaded.

## Attention required

Your organization's currently active (not resolved, closed, or
expired) alerts, most severe first. If nothing needs attention, this
says so plainly: "No active alerts."

## Recent automation activity

Your organization's most recent automation runs, each with a status
(Running, Completed, Failed, Cancelled, and a few others) and how long
ago it happened. This is automation activity specifically — AI-IOS
doesn't yet have a single feed covering every kind of platform
activity (see Known limitations).

## System status

A compact, per-service list of exactly what's registered and its
current status, latency, and any reported error — the detailed view
behind the Operational Health summary above.

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

## Known limitations

- **No trend/percentage-change indicators.** AI-IOS doesn't fabricate
  a "+12% this week" figure without real historical data to back it.
- **"Recent activity" covers automation only**, not every kind of
  platform activity — no single cross-platform activity feed exists
  yet.
- **No quick-action buttons or click-through navigation from dashboard
  tiles to other feature pages yet** — those pages (Monitoring,
  Alerting, Automation, etc.) don't exist in AI-IOS yet, so the
  dashboard doesn't link to them rather than link to something that
  isn't there.
- **No custom filters or time-range selection** — not backed by real
  data support yet.
