# Global Search

Find and jump to pages, assets, alerts, automations, reports, users,
and your own AI conversations from anywhere in AI-IOS.

## Opening search

- Click **Search…** in the top bar, or
- Press **Ctrl+K** (Windows/Linux) or **Cmd+K** (Mac) from anywhere.

## Searching

Type at least two characters. Results appear grouped by type:

- **Pages** — any page you can navigate to (matches AI-IOS's own admin
  restrictions — you won't see pages you don't have access to).
- **Assets**, **Users** (administrators only) — real, live search.
- **Alerts**, **Automations**, **Reports**, **AI Conversations** —
  matched against your organization's own recent items; there's no
  free-text search on these in AI-IOS today, so this matches by name
  and description across what's already loaded.

Not searched here: Audit events and Notifications — neither supports
searching by typed text on this backend. Open **Audit & Activity** or
**Notifications** directly (both are real pages you can navigate to
from search) to browse those.

## Navigating results

- **↑ / ↓** — move between results.
- **Enter** — open the highlighted result.
- **Esc** — close search.
- Click any result to open it directly.

Each result shows what it is, its name, a short bit of context, and
its status where relevant.

## Result groups and scope

On the full **Search** page (`/search`, reached via **View all
results**), narrow to one resource type using the row of buttons above
the results, or leave it on **All**.

## Recent searches

When search is empty, your last few searches appear so you can re-run
one quickly. This list is stored only on your own device — it's never
sent anywhere, and you can clear it anytime with the **Clear** button.

## Ask AI

Once you've typed something, an **Ask AI** link appears alongside your
results. This opens the AI Assistant with your search text pre-filled
as a draft message — it does **not** send anything automatically, and
it's a completely separate action from search: search finds real
AI-IOS data, Ask AI generates an answer.

## Troubleshooting

- **I don't see Users in my results.** Only administrators can search
  users.
- **My search for an alert/automation/report shows fewer results than
  I expect.** These are matched against your organization's own
  current list, not a live server-side search — a very large list may
  not be fully covered client-side.
- **I can't search Audit or Notifications by keyword.** Correct — see
  "Searching" above. Open those sections directly instead.
- **Nothing happens when I press Ctrl+K.** Make sure focus isn't
  inside another text field that intercepts the shortcut, and that
  your browser or OS isn't using the same shortcut for something else.
