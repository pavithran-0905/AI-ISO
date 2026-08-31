# Notifications

Review notifications addressed to you across AI-IOS. Distinct from
**Audit & Activity** (a historical record of actions taken) and
**Alerting** (operational conditions) — this page is your own inbox.

## The notification bell

In the top bar, the bell shows a small dot when you have unread
notifications — never a number. AI-IOS's backend doesn't provide a
way to count your unread notifications accurately, so rather than show
a guessed number, it shows only whether you have any. Click it to
preview your most recent notifications, or **View all** to open the
full Notification Center.

## Notification Center

Go to **View all** from the bell, or `/notifications` directly.

- **All / Unread / Important** — three quick views over the same list.
  "Important" means Critical or High priority. Switching between them
  doesn't reload anything.
- **Category** and **Status** filters — real filters, not client-side
  guesses.
- There's no free-text search — filter by category/status instead.
- Paging is Previous/Next only; this backend doesn't report a total
  count.

Click a notification to open its full detail: message, category,
priority, status, source, timestamps, and (if any) delivery attempts
per channel (email, Slack, etc.).

### Mark read and Acknowledge

Two separate, real actions:

- **Mark read** — clears the unread state.
- **Acknowledge** — a stronger signal than read; acknowledging also
  marks it read automatically.

There's no "mark all read" — AI-IOS doesn't currently support that as
a single action, so it isn't offered as one here.

### Notification preferences

Preferences (which categories/channels you want notified about, quiet
hours, digest frequency) and channel setup are managed from **Settings
→ Notifications**, not from here — click **Preferences** at the top of
the Notification Center to go there.

## A note on security

**Reading, viewing, marking read, and acknowledging notifications
currently require no sign-in check at all on AI-IOS's backend** —
technically, anyone who can reach the API directly could view or
change any notification. This is the most significant gap found in
this app so far, and a prominent banner on the Notification Center
says so plainly. This page's own behavior (only ever showing your own
notifications) is AI-IOS's own careful choice, not something the
backend enforces.

## What's not here, and why

- **A number on the bell.** Not available — AI-IOS doesn't provide an
  unread count, only individual notifications you can count yourself.
- **Live/instant updates.** Not available — the bell checks for new
  notifications about once a minute; there's no push/instant delivery
  to the browser today.
- **Clicking through to the alert, automation run, report, or asset
  that caused a notification.** Not available — notifications don't
  carry a reliable link to what caused them today.
- **"Mark all read."** Not available — see above.
- **Sending, broadcasting, or cancelling a notification.** Not
  available here — this page is for viewing notifications sent to you,
  not authoring new ones.

## Troubleshooting

- **The bell shows a dot but the popover looks empty.** The dot only
  reflects your most recent handful of notifications — open the full
  Notification Center and check your filters if you expect to see
  more.
- **I marked something read but it still looks unread elsewhere.**
  Refresh — AI-IOS doesn't push live updates, so another open tab or
  the bell's own cached preview can briefly be out of date.
- **I don't see a category or status I expected in the filters.** Only
  AI-IOS's own real, confirmed categories and statuses are offered —
  nothing here is invented.
