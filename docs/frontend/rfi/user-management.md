# User Management & Access Administration

Per Prompt 014 §50, this honestly separates **IMPLEMENTED** from
**PLANNED**/**UNAVAILABLE** for the Enterprise User Management & Access
Administration Experience — the most heavily backend-researched prompt
of this session, across four services with no shared identity model.
See `../rfi/README.md` and `../developer-guide/user-management.md` for
the full technical reasoning.

## Enterprise user administration — IMPLEMENTED (with the session's most severe security finding)

Real list/search/status-lifecycle/edit/delete/admin-notes against
`user-management-service`. **`user-management-service` enforces no
authorization on any of these routes at all** — confirmed by full
source inspection, not any other service's partial gap. This
frontend's own nav gating (administrator-only) is a real UX
convenience, not a security fix, and a permanent on-page banner says
so — see the developer guide.

## RBAC integration — IMPLEMENTED (mechanism; confirmed inert)

`rbac-service`'s real role/permission catalog and role-assignment
endpoints are built against directly — but confirmed, by cross-service
inspection, to have zero live effect on what any user can actually do
elsewhere in AI-IOS today. Every UI surface touching this carries an
explicit, permanent warning, not a footnote.

## Permission-aware UI — IMPLEMENTED (mechanism, four separate real authorization models)

Four services, four different, unsynchronized role vocabularies (JWT
claim, organization-service's 3-tier membership, project-service's
8-code ranked catalog, rbac-service's own 10-role catalog) — none
conflated, each named explicitly wherever it appears. See the
developer guide's comparison table.

## Organization/project access — PARTIALLY IMPLEMENTED (project only, and only in the forward direction)

Project membership/role management is real (list/add/remove/change-
role, including a real ownership-transfer special case) — built into
Settings' existing Projects page rather than here, since it's a
project-configuration concern, not a user-identity one (§47).
**Organization membership has no HTTP surface at all** —
`organization-service`'s own `OrganizationMemberService.list_for_org`/
`.remove` are fully implemented and completely unrouted. Team
membership has no representation at the API level in any service.

## Invitation workflows — IMPLEMENTED (send-only, by necessity)

A real, role-carrying, admin-enforced invitation
(`organization-service`) can be sent. **No service anywhere in this
platform supports listing, resending, or revoking a pending
invitation** — confirmed for both of the two separate invitation
systems that exist. This isn't a phase-one simplification; the
capability doesn't exist to build against.

## Security UX — IMPLEMENTED

No secret-shaped field is ever displayed. Self-lockout warnings are
shown wherever the backend provides no protection of its own (user
status changes on one's own account; project ownership/removal) —
this frontend's own addition in both cases, documented as such.

## Scalability — IMPLEMENTED (real pagination, honestly incomplete)

Server-side paging is real for the Users list, but this backend
discards its own computed total-count metadata before responding — no
endpoint here can report how many pages exist. A real Previous/Next
pager was built instead of a page-count picker that would have to
guess.

## Accessibility — IMPLEMENTED (foundation)

Built entirely on already-accessible primitives (`Dialog`, `Drawer`,
`Alert`, `FormField`, the same responsive table/card pattern from
Infrastructure) — no new bespoke interactive pattern.

## Maintainability — IMPLEMENTED (foundation)

`Page → Hooks → API module → apiClient → real V1 endpoint`, one API
module per backend service (four for Administration, one more for
Settings' project-membership extension), strict TypeScript, no `any`.

## Access & Membership summary (user detail) — UNAVAILABLE (documented, not implemented)

§26 explicitly asks for Organization/Projects/Teams/Roles/Permissions
on a user's detail page. Confirmed unavailable in every dimension: no
route lists an organization's members, no route reverses project
membership from a user's perspective, no route represents team
membership at all, and no route lists a user's existing role
assignments. Shown as an explicit, cited gap on the page itself, never
approximated.

## Team membership — UNAVAILABLE (documented, not implemented)

Teams themselves are real (list/create/update/delete); who's on one is
not representable via any endpoint in this backend today.

## Role/permission catalog editing — UNAVAILABLE by choice (real routes exist, deliberately not built)

`POST/PUT/DELETE /roles`, `/permissions` are real, `settings:manage`-
gated routes. Not built into UI: editing rbac-service's own catalog,
which nothing else in the platform reads from, would imply a
real-world effect that doesn't exist. The read-only catalog view
already satisfies what Prompt 014 itself asks for ("if V1 exposes
roles/permissions, display them").

See `../backend-v1-integration-limitations.md` for the full,
cross-prompt list with source citations.
