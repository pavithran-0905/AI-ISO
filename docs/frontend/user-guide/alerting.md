# Alerting

Where to see what's currently wrong, acknowledge it, work it, and
resolve it. Only documents what's actually implemented — there's no
"reopen" or "unsuppress" action yet (see Known limitations).

## Alerting Overview

Open **Alerting** from the sidebar (or `/alerting` directly). It shows
the same organization you've already picked on the Dashboard — you
won't be asked again.

- **Summary** — a tile per severity actually present among your
  alerts (Critical, High, Medium, Low, Informational), plus real
  backend-computed totals: total alerts, open alerts, average time to
  acknowledge, and average time to resolve.
- **Active maintenance windows** — any maintenance window currently
  suppressing alerts for your organization. Read-only; there's no
  "create a window" form here yet.

## Alerts

Open **Alerts** from the tab bar under Alerting, or `/alerting/alerts`.
This is the full list of every alert for your organization.

- **Search** — matches title, message, and source. This runs over the
  complete list for your current Status/Severity filter — there's no
  hidden remainder it might miss.
- **Filters** — narrow by Status or Severity.
- **Sort** — click any column header to sort by it; click again to
  reverse the direction.
- The exact search/filter/sort you're looking at is reflected in the
  page's URL, so you can bookmark or share it.

Click any alert's title to open its detail page.

## Alert detail

Shows everything AI-IOS knows about one alert:

- **Identity** — its id, organization/project/rule ids, fingerprint,
  who it's assigned to, and any raw source-reference data attached
  when it was raised.
- **Severity & status** — its current severity, status, and source.
- **Timestamps** — when it was triggered, resolved, and closed.
- **Description** — its title and message.
- **Actions** — see below.
- **Lifecycle** — every real status change recorded for this alert,
  most recent first.
- **Acknowledgements** — every acknowledge/resolve action recorded,
  with who did it and any comment or resolution notes.
- **Correlated alerts** — other alerts correlated to this one, each
  linking to its own detail page.
- **Notifications** — every delivery attempt made for this alert
  (channel, status, retry count, and any error).

## Actions

Depending on your role and the alert's current status, you may see:

- **Acknowledge** — mark that someone is looking at it, with an
  optional comment.
- **Resolve** — mark it fixed, with optional resolution notes.
- **Escalate** — hand it up, with an optional reason.
- **Close** — close it out.

Each action opens a confirmation dialog and waits for AI-IOS to
confirm the change before updating what you see — nothing shows as
"done" until the backend actually confirms it. Once an alert is
resolved, closed, or expired, no further actions are offered — there's
no way to reopen it (see Known limitations).

If you don't see an action, either your role doesn't allow it or the
alert has reached a state where it no longer applies.

## Refresh

The Alerting Overview and Alerts pages each have a refresh button (top
right) that re-fetches their data, with an "Updated ⟨time⟩" note
showing when it last ran. The alert list also refreshes automatically
in the background every 30 seconds.

## Severity meanings

**Critical**, **High**, **Medium**, **Low**, **Informational** — in
that priority order, most severe first.

## Troubleshooting

- **A section says "Access denied."** Your account doesn't have
  permission to view that specific data — contact your administrator.
- **A section shows an error with a Retry button.** That data is
  temporarily unavailable; the rest of the page keeps working
  normally. Try Retry, or use the page's own refresh button.
- **I don't see Acknowledge/Resolve/Escalate/Close on an alert.** Either
  your role doesn't allow it, or the alert is already
  resolved/closed/expired.
- **An action failed.** You'll see a clear failure message; the alert's
  status is left exactly as it was — nothing is assumed to have
  succeeded.

## Known limitations

- **No "reopen" action.** Once an alert is resolved, closed, or
  expired, there's no way to bring it back to an active state from
  this interface.
- **No "unsuppress" action.** Suppression is evaluated when an alert
  is ingested, not something you can toggle per alert afterward.
- **No creation form for maintenance windows.** They're shown, not
  created, from this interface.
- **Source reference doesn't link to a specific asset.** An alert's
  raw source data is shown as-is; AI-IOS can't currently resolve it to
  a specific Monitoring asset.
