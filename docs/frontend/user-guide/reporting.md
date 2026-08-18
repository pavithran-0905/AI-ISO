# Reporting

Where to design, generate, schedule, distribute, and archive reports.
Only documents what's actually implemented — there's no way to reopen a
report's edit history beyond what's shown here (see Known limitations).

## Reporting Overview

Open **Reporting** from the sidebar (or `/reporting` directly). It
shows the same organization you've already picked on the Dashboard.

- **Summary** — real counts: total reports, total generations (and how
  many failed), how many are scheduled, and the average generation
  time.
- **Recent generations** — the organization's real activity feed, most
  recent first, each linking to its own report.
- **Favorites** — reports you've starred, from any of your sessions.

## Reports

Open **Reports** from the tab bar, or `/reporting/reports`. Every
report saved for your organization.

- **Search** — matches name and description, over the complete list
  for your current Category/Enabled filter.
- **Filters** — narrow by Category, or "Enabled only."
- **Sort** — click a column header to sort by it.
- Star a report from this list or its detail page to pin it to your
  Favorites.

Click **New report** to create one, or a report's name to open its
detail page.

## Creating and editing a report

A new report needs a name, category, and type. You can attach an
**approved** template (a report can't be generated without one) and
set a default export format. Once created, you can edit its name,
description, default format, parameter values, filters, and
enabled/disabled state — its category, type, and template are fixed at
creation and can't be changed afterward.

## Report detail

Shows a report's identity, its available actions, its most recent
generation result (if you've generated it this session), its schedule,
its standing recipients, and its history.

## Actions

- **Generate** — pick which export format(s) to produce, and whether
  to deliver to standing recipients or archive the result immediately.
  This runs the whole pipeline and waits for a real result — there's
  no "queued" state to watch.
- **Favorite** — star or unstar.
- **Edit** — change the fields listed above.
- **Delete** — a real removal from every list. Already-generated
  exports and archives aren't affected.

## Generation results

After generating, you'll see the real outcome: status, row/section
counts, duration, and — if anything couldn't be resolved — a clear
warning naming which sections were skipped. The rest of the report
still generated normally. Each produced file can be downloaded,
archived, shared, or distributed from here.

This result is only visible right after you generate it — reopening
the report later won't show it again (see Known limitations). Use
**Generated Reports** or a report's own **History** for a durable
record that something ran.

## Exports

Every export can be downloaded directly to your device. Real formats
only: **PDF, XLSX, CSV, JSON, Markdown, HTML, XML**.

## Templates

Open **Templates** from the tab bar, or `/reporting/templates`. A
template is a reusable report structure, made of sections (headings,
text, tables, charts, metrics, or an AI summary). Templates go through
a real approval flow: **Draft → Approved → Archived**. A report can
only be generated against an **approved** template.

Click **New template** to design one from scratch: give it a name,
category, and type, then add sections one at a time — each section's
fields depend on its kind (a table needs a data source and columns; a
chart needs a data source and axis keys; a heading or text section
needs its own text). You can also declare parameters the report can
fill in later.

From a template's detail page you can approve it, archive it, or save
a new draft version (a new version always starts as a draft and needs
its own approval).

## Scheduling

From a report's detail page, create a schedule: how often it runs
(one-time, hourly, daily, weekly, monthly, or a custom cron
expression), its timezone, when it starts (and optionally ends), and
which format to export. **Scheduled Reports** (`/reporting/schedules`)
lists every schedule across the organization. Enable/disable and
delete a schedule from its own report's detail page.

## Distribution

From a report's detail page, add standing **recipients** — real
channels only: Download, Email, Webhook, Shared Link, API, or Object
Storage. When you generate with "Deliver to standing recipients"
checked, every enabled recipient gets a delivery attempt.

From a specific generation result, you can also distribute or share
one export ad hoc, without adding a standing recipient:

- **Distribute** sends it once, immediately, to a channel and target
  you choose.
- **Share** creates a link with an expiry. The link's token is shown
  to you exactly once — copy it right away, since it can't be shown
  again later. There's no way to revoke a link before it expires (see
  Known limitations).

## Archive

Open **Archive** from the tab bar, or `/reporting/archive`. Real
immutable copies of generated reports, independent of the original
export — even if the report is later regenerated or deleted, an
archived copy stays exactly as it was. Search by title or filter by
status (Active, Restored, Purged).

- **Download** an archived copy directly.
- **Restore** creates a brand-new export from the archived bytes.
- **Purge** permanently removes the content (metadata is kept). AI-IOS
  enforces a retention period — if a purge is rejected, you'll see the
  real reason (e.g. "still within its retention window").

## AI narratives

A template can include an AI-generated summary section. When a report
with one generates, you'll see it succeed (as prose in the output
file) or fail (shown honestly as a degraded section, without breaking
the rest of the report) — always labeled as AI-generated, never
presented as human-written fact.

## Refresh

Each Reporting page has a refresh button (top right) that re-fetches
its data, with an "Updated ⟨time⟩" note showing when it last ran.

## Troubleshooting

- **A section says "Access denied."** Your account doesn't have
  permission to view that specific data — contact your administrator.
- **A section shows an error with a Retry button.** That data is
  temporarily unavailable; the rest of the page keeps working
  normally.
- **I don't see Generate/Edit/Delete on a report, or scheduling/
  distribution controls.** Your role doesn't currently allow that
  action.
- **A purge was rejected.** The message tells you why — usually that
  the archived copy is still within its retention period.
- **Generation failed, or some sections are missing.** You'll see the
  real error or the specific section names that couldn't be resolved —
  nothing is silently dropped.

## Known limitations

- **A generation result disappears once you navigate away.** There's
  no way to re-fetch a past run's artifacts later — use History for a
  summary record, or Archive a result you want to keep.
- **No way to revoke a share link early.** It's only good until its
  own expiry.
- **Archive isn't filterable by report.** The Archive page shows every
  archived report in the organization; there's no per-report archive
  view yet.
- **No live preview while designing a template.** Sections render only
  when a report actually generates — save and generate to see the
  real output.
