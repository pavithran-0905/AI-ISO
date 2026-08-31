# Operations Workspace

Investigate active alerts and recent automation activity together, in
one place. **This is not an incident-tracking system** — AI-IOS
doesn't have one; this page brings together real, already-existing
data from Alerting and Automation.

## Opening the workspace

Go to **Operations Workspace** under Operations in the sidebar, or
directly at `/operations`. It can also be found through global search
(**Ctrl+K**).

## Signals

Two real, separate lists:

- **Active alerts** — every alert not yet resolved, most severe first.
- **Automation activity** — recent automation runs, failures shown
  first.

When everything is quiet, you'll see a calm "No active issues detected
in this scope" message — not an alarming empty state.

## Investigating a signal

Click any alert or automation run to open it in the **Investigation**
panel on the right (or below, on smaller screens):

- **Alert**: its full details, real actions (Acknowledge, Resolve,
  Escalate, Close — if you have permission), any alerts AI-IOS has
  explicitly correlated to it, and its history. **Open Alert** takes
  you to its own full page.
- **Automation run**: status, timing, any error message, and the
  target identifiers it ran against (shown as plain text — AI-IOS
  can't confirm these correspond to a specific, currently-existing
  asset). **Open Execution** takes you to its own full page.

Your selection is saved in the page's URL, so you can bookmark or
share a link straight to a specific investigation.

## Recent activity

A short feed of recent compliance activity (last 24 hours). Click
**View full activity** to see everything in Audit & Activity.

## Investigate with AI

**Investigate with AI** (top of the page) opens the AI Assistant with
a draft summarizing the current situation — how many active alerts,
and their highest severity. Each selected alert or run also has its
own **Ask AI** for that specific item. Nothing is sent automatically,
and AI Assistant answers are never presented as confirmed facts from
AI-IOS itself.

## Refresh

The refresh button reloads alerts, automation activity, and recent
activity — not the entire application.

## What's not here, and why

- **Unhealthy assets as a signal.** AI-IOS can't efficiently search
  for "just the unhealthy ones," so this isn't offered as a signal
  source here.
- **A "this alert affects this specific asset" link.** AI-IOS doesn't
  reliably record which resource an alert is about.
- **Topology or Monitoring previews for a selected signal.** These
  need the same resource link mentioned above, which doesn't exist.
- **Reports related to a signal.** Reports aren't scoped to specific
  alerts or automation runs on this backend.
- **"These alerts share a root cause."** AI-IOS never claims a root
  cause — only alerts it has explicitly recorded as related to each
  other are shown as "Related alerts."

## Troubleshooting

- **I don't see Acknowledge/Resolve buttons on an alert.** You don't
  have permission for that action.
- **A target identifier under an automation run isn't clickable.**
  That's intentional — AI-IOS can't confirm it points to a real,
  currently-existing asset.
- **A section shows "Retry" instead of content.** That one source
  failed to load — the rest of the workspace still works.
