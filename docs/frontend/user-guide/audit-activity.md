# Audit & Activity

Review audit trails across AI-IOS's compliance, integrations, and
notification systems. **There is no single audit log covering all of
AI-IOS** — this page shows three separate, real trails side by side,
never merged into one list.

## Opening Audit & Activity

Only shown in the sidebar to administrators — go to **Audit &
Activity** under Governance, or directly to `/audit`.

## Overview

A summary of recent compliance audit activity (last 30 days) — total
events, the most frequent actions, and a compliance-posture snapshot
(open findings by severity, how many are overdue). This is
`compliance-service`'s own summary; the other two sources have no
summary view here — see Activity to look at them directly.

## Activity

Pick a source at the top — **Compliance**, **Integrations**, or
**Notifications**. Each has its own event list, its own filters, and
its own paging; switching sources starts a fresh search.

- **Compliance** — filter by entity type, entity ID, actor ID, and a
  date-range preset (last 24 hours / 7 days / 30 days / 90 days).
  There's no action filter here — this route doesn't support one.
- **Integrations** — no filters beyond your organization; every event
  for the organization is shown.
- **Notifications** — filter by action (a real, fixed list — nothing
  made up), entity ID, and actor ID.

There's no free-text search on any of the three — only the filters
listed above narrow the list. None of the three backends reports how
many pages of results exist, so paging is Previous/Next only.

### Table and Timeline

Switch between a dense table and a chronological timeline view with
the toggle above the results — both show exactly the same events,
switching doesn't reload anything.

### Event details

Click **View** on any event to open its details: who did it, what
action, what it affected, when, and whether it succeeded. Any
password, token, API key, or similar secret-looking value inside an
event's details is always shown masked (`••••••••`), never in the
clear.

## Export

For **Compliance** events only, you can generate and download a
report (JSON, CSV, or Markdown) covering the last 90 days. The
downloaded file has fewer columns than the on-screen table — it leaves
out the event ID, the affected resource's ID, the actor's type, and
the detailed change record. **Integrations** and **Notifications**
have no export option — that capability doesn't exist for those two
sources.

## A note on who can do what here

Two of these three sources — **Integrations** and **Notifications** —
have **no access control at all** on their audit routes: anyone who
can reach the API directly could read them, signed in or not. The
third, **Compliance**, requires only that you're signed in — no
specific role is checked. A warning banner on the Activity page names
exactly which of these applies to the source you're currently viewing.
This page's own sidebar visibility (administrators only) is AI-IOS's
own safeguard, not something the backend enforces.

## What's not here, and why

- **A single combined audit feed.** Doesn't exist — the three sources
  are entirely separate systems with no shared identity.
- **Linking an event to the user who did it.** Not available — there's
  no confirmed way to match an event's actor to a specific account in
  Users today.
- **Linking an event to an Automation run or an Infrastructure asset.**
  Not available — none of these three sources records that kind of
  action.
- **"Analyze with AI" on an event.** Not available — no such capability
  exists for audit data today.
- **A guaranteed retention period, or a promise that Integrations/
  Notifications events can never be altered.** Not stated, because
  neither is confirmed. (Compliance's own audit trail specifically has
  been confirmed as unable to be edited or deleted — that one claim is
  safe, and doesn't extend to the other two sources.)

## Troubleshooting

- **I don't see Audit & Activity in the sidebar at all.** It's only
  shown to administrators.
- **I can't find an action filter for Compliance, or any filter at all
  for Integrations.** Expected — those two sources don't support those
  filters; see "Activity" above for what each source actually offers.
- **My Export button isn't there.** Export only exists for the
  Compliance source.
- **A field in an event's details shows `••••••••`.** That's
  intentional — it's a secret-looking value, and AI-IOS never displays
  those in the clear.
