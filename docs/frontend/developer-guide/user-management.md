# User Management & Access Administration

The Enterprise User Management & Access Administration Experience
built in Prompt 014, against four services with no shared identity
model: `user-management-service`, `organization-service`,
`project-service`, and `rbac-service`. This is the most heavily
backend-researched prompt of the session (three parallel research
passes) because the fragmentation between these four services'
identity concepts turned out to be the central fact this feature had
to reflect honestly rather than paper over. See
`docs/frontend/rfi/user-management.md` for the implemented-vs-planned
split and `docs/frontend/backend-v1-integration-limitations.md` for
the full gap list with citations.

## The most severe finding this session: `user-management-service` enforces no authorization on any route

Confirmed by full source inspection of every `app/api/*.py` file in
this service: `GET /users`, `POST /users/search`, `GET/PUT/PATCH/DELETE
/users/{id}`, `POST /users/invite` and its siblings, and
`POST/GET/DELETE /users/{id}/notes` all depend only on
`CurrentUserId` — a dependency that decodes the JWT and returns the
subject, nothing more. There is no role, permission, or ownership
check anywhere in this service. Any authenticated user, including one
whose frontend `role` claim is `null` (the documented Prompt 001 gap),
can list every user, edit anyone's profile, transition anyone's status
to `suspended`/`disabled`/`deleted`, and read/write anyone's admin
notes, by calling these APIs directly.

**Frontend behavior**: this page's own primary nav entry is restricted
to `super_admin`/`organization_admin` via `lib/route-registry.ts`'s
`roles` field (real enforcement inside `PrimaryNavigation`, which
filters nav routes by the session's role) — but that only controls
whether the *link* is shown, not whether the underlying API calls
succeed for anyone who navigates there directly or calls the API
themselves. A persistent `Alert` banner on the Users page says this
plainly, not just in a code comment, because the risk of someone
believing this page is more locked-down than it is outweighs the
minor UX cost of a visible warning.

## Four services, four separate role vocabularies, never unified

| System | Vocabulary | Live-enforced? |
|---|---|---|
| Frontend's own JWT claim (`@/auth/types`) | `super_admin, organization_admin, project_admin, operator, viewer, auditor` (6) | Yes — every other service (except rbac-service itself) checks this locally |
| `organization-service`'s `MemberRole` | `member &lt; admin &lt; owner` (3, ranked) | Yes, within that service, against its own `organization_members` table |
| `project-service`'s `project_roles` | 8 seeded system codes, ranked (`owner` 100 → `auditor`/`viewer` 10) | Yes, within that service, against its own `project_members` table |
| `rbac-service`'s role catalog | 10 seeded system roles (`platform_administrator`, `organization_administrator`, ...) | **No** — see below |

None of these four are the same list, none reference each other, and
no service consults another service's role table. This feature never
conflates them — every component and type that touches a role concept
names which of the four it means.

## `rbac-service`'s role/permission-assignment routes are real, and confirmed inert

`GET /roles`, `GET /permissions`, `GET /permission-groups`,
`GET /policies`, and `POST /authorization/evaluate` are all real,
reachable, unauthenticated-beyond-JWT catalog/evaluation endpoints.
`POST/DELETE /users/{id}/roles` genuinely persists a role-assignment
row. But confirmed by grepping every other service in the monorepo for
any client call into `rbac-service`: **nothing does**. Every other
service's own `require_admin`/`require_permission`-shaped guard checks
its own local table or the JWT claim directly (organization-service
against `organization_members`, project-service against
`project_members`, everything else against the JWT `role` claim). The
one place `rbac-service` enforces anything is against *itself* — its
own mutating routes require `settings:manage`, evaluated via its own
`AuthorizationEvaluator`, which is a real, self-consistent system that
nothing outside this one service ever queries.

**Frontend behavior**: `RoleAssignmentSection` builds the real §20
"Select User → Select Role → Confirm → Backend Confirmation" workflow
Prompt 014 asks for — the mutation is real, the persisted row is real
— but ships with a permanent, unmissable `Alert` (not a tooltip, not a
docstring) stating plainly that this has no live effect on the user's
actual access anywhere else in AI-IOS today. `RolesPage`/
`PermissionsPage` carry the same warning. Role/permission catalog
CRUD (`POST/PUT/DELETE /roles`, `/permissions`) was deliberately not
built into UI — editing an inert reference catalog with no other
consumer would imply more real-world effect than exists; the read-only
catalog view satisfies §18/§21's own "if V1 exposes roles/permissions,
display them" without overstating what editing one would do.

## Why "Access & Membership" on User Detail is an honest, explicit gap, not a missing feature

§26 asks for an "Access Summary: Organization / Projects / Teams /
Roles / Permissions" on a user's detail page. Confirmed absent, by
service:

- **Organization membership**: `OrganizationMemberService.list_for_org()`
  and `.remove()` both exist in `organization-service` — **neither has
  a route**. There is no `app/api/member.py` at all in that service.
  There is no way to list an organization's members, and therefore no
  way to show which organization a given user belongs to, from any
  endpoint.
- **Project membership**: real and listable, but only in the *forward*
  direction (`GET /projects/{id}/members` — given a project, list its
  members). There is no *reverse* lookup (given a user, list their
  projects) anywhere in `project-service`.
- **Team membership**: no team-members endpoint exists in
  `organization-service` at all (confirmed — team membership at the
  API level has no representation anywhere; the only place it's even
  recorded is `OrganizationMember.team_id`, itself unreachable per the
  point above).
- **Role assignments**: `RoleAssignmentService.list_for_user()` exists
  in `rbac-service` — unrouted (confirmed: the router only calls
  `.assign`/`.remove`, never `.list_for_user`).

**Frontend behavior**: `AccessMembershipGap` states this outright,
citing that it's a genuine data gap, not a loading state or a
permission restriction. Building a partial, misleading version (e.g.
"here are the user's projects" using only the one project the admin
happens to already be looking at) was rejected as worse than stating
the gap.

## Why project membership lives in Settings, not here

`project-service`'s real `GET/POST /projects/{id}/members`,
`DELETE .../{userId}`, `PUT .../{userId}/roles` were researched under
this prompt but built into `features/settings/pages/projects-page.tsx`
(Prompt 013's existing page), not a new Administration section. §47's
own instruction — "Settings → Organization configuration... Keep
responsibilities clear... Do not duplicate functionality between
Settings and Administration" — is the reason: managing who's on a
project and at what role is fundamentally "configure this project,"
the same category as the project's other settings already on that
page, not "manage this user's identity" (which is what Administration
is for). It also sidesteps a real constraint: since no reverse
user→projects lookup exists (previous section), there was never a way
to reach this from a *user's* detail page anyway — it can only
sensibly be reached by first picking a project, which is exactly
Settings' Projects page's own existing shape.

### Project role assignment: no self-lockout guard, and `"owner"` means ownership transfer

Confirmed by reading `ProjectMemberService.remove`/`.update_role`
directly: **no last-owner, last-admin, or self-removal check exists
anywhere in this service.** A caller can remove the project's only
Owner, or remove themselves, and the backend will comply. Separately,
`PUT /projects/{id}/members/{userId}/roles` with `role_code: "owner"`
is special-cased server-side into a full ownership transfer (the
previous `project.owner_id` holder is automatically demoted to
Administrator) — it is not a plain role edit.

**Frontend behavior**: `ProjectMembersSection` blocks (client-side,
with a clear message, not silently) removing or demoting a project's
sole Owner, and shows a distinct "Transfer project ownership?"
confirmation — never presented as an ordinary role-change dropdown —
whenever `"owner"` is selected. An `Alert` states plainly that this
guard is the frontend's own addition, since the backend has none.
Roles are offered from a hardcoded but real, source-confirmed 8-value
list (`PROJECT_ROLE_CODES`) since no endpoint discovers a project's
available roles dynamically (the model supports per-project custom
roles; no route creates or lists them).

## Users: real pagination without a real total

`GET /users`'s route computes real pagination metadata internally
(`PaginationMetadata`, from `shared_core`) but the route handler
discards it before responding — the response is a bare array. Same for
`POST /users/search`. **No total count, no `hasNext`, is available
anywhere in this service's user-listing surface.** `UserSearchResult.hasMore`
is a heuristic (`items.length === pageSize`), documented as such
everywhere it's used, and `UserTable` renders a real Previous/Next
pager rather than a page-count picker that would have to guess a
total.

Separately, `POST /users/search`'s own request schema accepts
`department`/`tags` fields that the route handler never references —
confirmed dead on the wire. `UserFilters` exposes only `query`
(free-text over username/email/phone/display name) and `status`, the
two fields that actually do something.

## Status transitions: real, validated, not pre-guessed

`PATCH /users/{id}`'s `status` field routes through
`UserService.transition_status`, which checks a real
`_VALID_TRANSITIONS` table (e.g. `pending → suspended` is illegal,
`active → suspended` is legal; `deleted` is terminal). This table
isn't exposed by any endpoint, so `UserStatusActions` does not attempt
to pre-validate which transitions are legal — every one of the 9 real
`UserStatus` values is offered, and an illegal choice is rejected by
the backend's own real 409, shown as-is. Guessing at the transition
table client-side risked encoding a rule that doesn't match the real
one, which would be worse than deferring to the backend.

`DELETE /users/{id}` is a **soft delete via the row's `is_active`
flag**, not a `status` transition to `"deleted"` — confirmed by
reading `BaseRepository.delete`. The user then 404s from every other
route in this service, but its `status` column, if inspected directly,
would still read whatever it was before deletion. Documented, not
worked around.

## Two separate invitation systems; the built one carries a role, the other doesn't

`user-management-service` has its own `/users/invite` (email/message
only, real working `/resend`, no list, no revoke) and
`organization-service` has a separate `/organizations/{id}/invite`
(email/role/department/team, `require_admin`-enforced, real, but no
resend and no revoke exist even as unrouted service methods — the
capability genuinely doesn't exist). This feature builds against the
organization-service one, since a role-carrying, admin-enforced
invitation is what an access-administration page should offer;
`user-management-service`'s own separate flow (with its working
resend) is documented as real but not used here, to avoid combining
two different objects into one dishonest form.

**Neither system supports listing pending invitations.**
`organization-service`'s `InvitationService.resend()` is fully
implemented and unrouted; `UserInvitationRepository.list_pending()` is
implemented and unrouted; no revoke/cancel method exists in either
service at all (`InvitationStatus.REVOKED` is a defined enum value
with zero code path that ever assigns it). `InvitationsPage` is
therefore a send-only form with a permanent banner explaining there's
nothing to list afterward — not a placeholder for a table that will
"come later," an accurate description of what exists today.

## Query/API architecture

`Administration Page → User/RBAC Hooks (features/administration/hooks/*.ts)
→ Administration API Module (features/administration/api/*.ts) →
apiClient → Backend V1` — four API modules, one per backend service,
matching the layering every prior feature this session established.
Project membership follows the same shape inside `features/settings/`
instead (see above).

## Cache invalidation

Status/identity mutations invalidate `["administration", "users"]`
broadly (list + detail), matching the coarse-but-correct pattern
established for other features when a mutation's exact blast radius
isn't cheaply known. Notes invalidate their own per-user key. Project
member mutations invalidate `["settings", "projects", projectId,
"members"]`.

## Concurrency

No optimistic-locking signal is exposed by any route in any of the
four services touched by this prompt (same pattern already documented
for Settings in Prompt 013) — no new instance of §37's suggested
"changed elsewhere" UX was attempted here either, for the same reason:
no `version` field exists on the wire to detect a conflict with.

## Security review

- No password, token, session secret, or API key is ever displayed by
  this feature (none of the four services' responses used here carry
  one).
- `UserDetail.metadata` (a free-form `dict`) is displayed nowhere in
  this feature's UI — it exists on the wire but isn't rendered, since
  no defined shape exists to safely present it.
- Admin notes (`/users/{id}/notes`) are genuinely non-self-scoped by
  design (`author_id` is the calling admin, `{user_id}` is the
  subject) — the one router in `user-management-service` that's
  correctly shaped for an admin surface, in contrast to everything
  else in that service having no ownership check where one would
  matter.

## Accessibility

`UserTable` reuses the exact responsive table/card pattern established
in Infrastructure (Prompt 011); every dialog/drawer/alert reuses the
existing primitives (`Dialog`, `Drawer`, `Alert`) rather than
hand-rolled markup. The one new pattern — a per-row role `<Select>` in
`ProjectMembersSection` — uses a real, labeled native select (`aria-label`
per row), not a custom dropdown.
