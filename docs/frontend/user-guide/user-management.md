# User Management & Access Administration

Manage user accounts, teams, and invitations. Roles/Permissions is a
reference catalog only — see below for exactly what that means.

## Opening Administration

Only shown in the sidebar to administrators — go to **Users** under
Administration, or directly to `/administration/users`.

## Users

The full list of user accounts known to AI-IOS.

- **Search** — matches username, email, phone, or display name.
- **Filter** — by status.
- Since this backend doesn't report a total count, paging is
  Previous/Next only — there's no "page 3 of 12" indicator.

Click a user to open their detail page:

- **Identity** — name, contact details, timezone/language/locale.
- **Status** — change a user's account status. An unsupported change
  (for example, reactivating a deleted account) is rejected with a
  clear error — nothing is pre-blocked here that the backend would
  actually allow.
- **Access & membership** — not available. AI-IOS currently has no way
  to show which organization, project, or team a user belongs to, or
  what roles they hold, from this page — the underlying data simply
  isn't connected across services yet.
- **Role assignment** — see "Role assignment" below; read its warning
  before using it.
- **Admin notes** — internal notes about the account, visible to other
  administrators.

### A note on who can do what here

This backend doesn't currently check permissions on any of these user
actions — technically, any signed-in AI-IOS user could call the same
APIs directly. This page's own visibility and controls are there to
keep things safe and organized for you, not as a real security
boundary. A banner on the Users page says this plainly.

### Removing your own account

If you view your own account, a warning appears before any action that
would restrict your own access (suspend, disable, delete, and
similar) — this backend won't stop you from locking yourself out, so
the warning is AI-IOS's own safeguard.

## Teams

Real teams, scoped to an organization: create, rename, and delete.
There's currently no way to view or manage who belongs to a team from
this interface — that capability doesn't exist yet.

## Roles

**A reference catalog, not what actually controls access.** AI-IOS's
role-based access system exists and this page shows its real role
catalog, but no other part of AI-IOS currently checks these roles when
deciding what you can do — every part of the app instead checks your
account's own basic role. A banner explains this on the page itself.

## Permissions

The same reference catalog's fine-grained permission list (what
resource, what action, what scope) — same caveat as Roles.

## Role assignment

From a user's detail page, you can record a role assignment for them.
**Read this carefully: doing so does not currently change what that
user can actually do anywhere in AI-IOS.** It creates a real record in
the role catalog, but nothing else in the platform reads from it yet.
There's also no way to see what's already been assigned to a user from
this page.

## Invitations

Send someone an email invitation to join an organization, at a role
you choose. **There's no way to see invitations you've already sent,
resend one, or cancel one** — sending is the only action available.
If you need a record of who you've invited, keep track of it yourself
for now.

## Project members

Project membership and roles are managed from **Settings → Projects**,
not from here — see the Settings user guide. Pick a project there to
add/remove members and change roles.

## Troubleshooting

- **I don't see Users in the sidebar at all.** It's only shown to
  administrators.
- **I changed a user's status and got an error.** That specific
  transition isn't allowed from their current status (for example, you
  can't reactivate a deleted account) — this is enforced by AI-IOS
  itself, not a bug in this page.
- **I assigned a role but the user's access didn't change.** Expected
  — see "Role assignment" above.
- **I can't see who's on a team, or what organization/project a user
  belongs to.** Not available yet — see the relevant sections above.
