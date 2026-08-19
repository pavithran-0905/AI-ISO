# Settings

Manage your own preferences, security, and — where your role allows —
your organization, projects, integrations, notifications, and (for
administrators) platform-wide system configuration.

## Opening Settings

Click your account menu (top right) → **Preferences**, or go directly
to `/settings`. The sidebar lists every section you have access to.

## My Preferences

- **Identity** — your display name and contact details, shown
  wherever you're attributed elsewhere in AI-IOS.
- **Profile** — biography, job title, department, employee ID, and
  manager (shown as a raw ID — no directory lookup exists yet).
- **Preferences** — language, timezone, date/time format, and your
  default organization at sign-in.
- **Display** — theme (Light/Dark/System) and table density. These
  apply immediately, on this device only — they don't sync to your
  other devices.

## Security

- **Multi-factor authentication** — enable it to scan a QR code, save
  your recovery codes (shown only once), and confirm with a code from
  your authenticator app. Disabling it requires a current code.
- **API keys** — create a key for a script or integration to call
  AI-IOS as you. The full key is shown exactly once, right after
  creation — copy it immediately, since it can't be retrieved again.
  Revoke a key any time.
- **Trusted devices** — every device that's signed in as you, with the
  option to revoke one.
- **Active sessions** — everywhere you're currently signed in, with
  the option to sign out one session or everywhere at once.
- **Password** — there's no in-app password change yet; use **Send
  password reset email** to get a reset link.

## Organization

Visible to any member; only an organization administrator can save
changes here (others see the current values, read-only).

- **Identity** — name, domain, contact, website, industry, country.
- **Security & operational policy** — whether MFA is required for
  every member, allowed email domains, default language/timezone,
  session timeout, and data retention.
- **Branding** — logo, favicon, and brand colors.
- **Plan & limits** — your current license and usage limits, shown
  read-only (managed by billing, not from this page).

## Projects

Pick a project from the dropdown to see and (if your role allows) edit
its name, description, and operational defaults (default environment,
connector, workflow runtime).

## Integrations

Register a connector to link AI-IOS with another system (a
Kubernetes cluster, a monitoring provider, a messaging platform, and
so on). For each connector you can:

- Edit its configuration (a key/value list — values that look like
  passwords or tokens are masked until you click to reveal them).
- **Test connection** — runs a real check; if the connector has a real
  endpoint/host configured, this makes an actual outbound check; if
  not, it only verifies the configuration and credential are present,
  which the result clearly says.
- Enable or disable it.
- Assign a credential (shown only once when a new key is entered) and
  rotate it later.
- Remove it — a soft removal; it stops appearing in the list but isn't
  permanently deleted.

## Notifications

- **My notification preferences** — which channels you prefer, which
  categories you've muted, quiet hours, and how often you get a
  digest instead of individual notifications. You can also mute
  everything with one switch.
- **Organization notification channels** (administrators only) — where
  this organization's notifications actually get delivered (email,
  Slack, a webhook, and so on). Configuration values here are stored
  and shown as plain text by the backend — never paste a secret you
  can't easily rotate later.

## AI

Not available yet — AI-IOS's AI Assistant doesn't currently expose any
preferences to configure.

## System

Only shown to administrators. Platform-wide settings, feature flags
(with a separate emergency kill switch from the normal enable/disable
toggle), background jobs, and read-only diagnostics/statistics/reports.

## Saving changes

Every save button shows a saving state, is disabled while saving to
prevent duplicate submissions, and only confirms success once the
server has actually confirmed it — if a save fails, your entered
values stay in the form so you don't lose your work.

## Unsaved changes

If you navigate away from a page with unsaved changes and try to close
or refresh the tab, your browser will ask you to confirm first.

## Permissions

Sections you can view but not edit show their current values without
editable controls, along with a short note about why. If your role
changes, refresh the page to see the update reflected.

## Troubleshooting

- **I don't see Organization/Projects editable, only read-only
  values.** Your role doesn't currently allow editing them.
- **I don't see System in the sidebar at all.** It's only shown to
  administrators.
- **A save in System failed with a permission error.** This is a known
  platform limitation, not a bug in this page — see the developer
  guide if you're troubleshooting as an engineer.
- **A connector's config value shows as dots.** That's a key that
  looks like a password/token/API key — click it to reveal and edit.
