/**
 * Types mirroring real V1 responses this feature consumes, confirmed
 * by direct source inspection across four services with no shared
 * identity model between them (`user-management-service`,
 * `organization-service`, `project-service`, `rbac-service`). See
 * `docs/frontend/developer-guide/user-management.md` for why this
 * fragmentation is a real backend property this feature reflects
 * honestly rather than papers over with an invented unified model.
 */

// ---- Users (user-management-service) --------------------------------------------------

/** `UserStatus` — 9 real values (`app/models/enums.py`). Status
 * changes go through a real, backend-enforced lifecycle state machine
 * (`UserService.transition_status`) — an illegal transition (e.g.
 * `pending` → `suspended`) returns a real 409, shown as a real error
 * rather than pre-validated client-side (the full transition table
 * isn't exposed by any endpoint, so guessing at it client-side would
 * risk inventing a rule that doesn't match the real one). */
export const USER_STATUSES = [
  "pending",
  "invited",
  "active",
  "inactive",
  "locked",
  "disabled",
  "deleted",
  "archived",
  "suspended",
] as const;
export type UserStatusValue = (typeof USER_STATUSES)[number];

/** `UserSummary` (`GET /users`, `POST /users/search`) — the list-row
 * shape. `GET /users`'s own response discards real pagination
 * metadata the service computes internally (confirmed: `total`/
 * `hasNext` are dropped before the route returns) — see
 * `UserSearchResult`'s own docstring. */
export interface UserSummary {
  id: string;
  username: string;
  email: string;
  displayName: string | null;
  avatar: string | null;
  status: UserStatusValue;
  createdAt: string;
}

/** `UserDetail` (`GET /users/{id}`) — strictly richer than
 * `UserSummary`. No `organizationId`/`projectId`/role/team field
 * exists on this response at all — this service's own tenant concept
 * is a single hardcoded default, unrelated to `organization-service`'s
 * real Organizations (see the developer guide). */
export interface UserDetail {
  id: string;
  username: string;
  email: string;
  displayName: string | null;
  firstName: string | null;
  middleName: string | null;
  lastName: string | null;
  phoneNumber: string | null;
  avatar: string | null;
  timezone: string;
  language: string;
  locale: string;
  status: UserStatusValue;
  lastLogin: string | null;
  metadata: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
}

/** No total/hasNext is available (see `UserSummary`'s docstring) —
 * `hasMore` is a heuristic (`items.length === pageSize`), not a real
 * backend signal, and is documented as such everywhere it's used. */
export interface UserSearchResult {
  items: UserSummary[];
  page: number;
  pageSize: number;
  hasMore: boolean;
}

/** `UserSearchRequest` (`POST /users/search`). `department`/`tags`
 * are real fields on the request schema that the backend silently
 * ignores (confirmed: never referenced by the route handler) — not
 * exposed here, to avoid offering a filter that does nothing. */
export interface UserSearchParams {
  query?: string;
  status?: UserStatusValue;
  sort?: string;
  page?: number;
  pageSize?: number;
}

/** `UserPatchRequest` (`PATCH /users/{id}`) — genuinely partial. */
export interface PatchUserInput {
  displayName?: string;
  firstName?: string;
  middleName?: string;
  lastName?: string;
  phoneNumber?: string;
  status?: UserStatusValue;
}

export interface AdminNote {
  id: string;
  authorId: string;
  body: string;
  createdAt: string;
}

// ---- Organization invitations (organization-service) -----------------------------------

/** `MemberRole` (organization-service) — a 3-tier hierarchy
 * (`member` &lt; `admin` &lt; `owner`), entirely distinct from
 * `rbac-service`'s own 10-role catalog and from `project-service`'s
 * own 8-code project role table. Never conflated. */
export const ORGANIZATION_MEMBER_ROLES = ["member", "admin", "owner"] as const;
export type OrganizationMemberRoleValue = (typeof ORGANIZATION_MEMBER_ROLES)[number];

/** `InviteMemberRequest` (`POST /organizations/{id}/invite`) — the
 * one real invitation path that carries a role (unlike
 * user-management-service's own separate, simpler `/users/invite`,
 * which carries no role/team at all — see the developer guide for why
 * this one was chosen as the built path). */
export interface CreateOrganizationInvitationInput {
  organizationId: string;
  email: string;
  role: OrganizationMemberRoleValue;
  departmentId?: string;
  teamId?: string;
  message?: string;
}

/** No route lists pending invitations, resends, or revokes one on
 * this service (confirmed absent — see the developer guide) — this is
 * the complete response shape the create call returns, and the only
 * one this feature ever has. */
export interface OrganizationInvitation {
  id: string;
  organizationId: string;
  email: string;
  invitedBy: string;
  role: OrganizationMemberRoleValue;
  departmentId: string | null;
  teamId: string | null;
  status: string;
  resendCount: number;
  expiresAt: string;
  createdAt: string;
}

// ---- Teams (organization-service) -------------------------------------------------------

export interface Team {
  id: string;
  organizationId: string;
  name: string;
  code: string | null;
  description: string | null;
  departmentId: string | null;
  businessUnitId: string | null;
  teamLeadId: string | null;
  metadata: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
}

export interface CreateTeamInput {
  organizationId: string;
  name: string;
  code?: string;
  description?: string;
  departmentId?: string;
  teamLeadId?: string;
}

export interface UpdateTeamInput {
  name: string;
  code?: string;
  description?: string;
  departmentId?: string;
  teamLeadId?: string;
}

// ---- Roles & Permissions catalog (rbac-service) ------------------------------------------

/** `RoleResponse` (`GET /roles`). This is `rbac-service`'s own real
 * 10-role catalog — confirmed, by direct cross-service inspection,
 * that nothing else in the platform ever reads from it at
 * authorization-decision time (every other service checks the JWT's
 * own `role` claim locally instead). Reference catalog only — see the
 * developer guide's prominent warning, also surfaced in the UI. */
export interface RbacRole {
  id: string;
  name: string;
  code: string;
  description: string | null;
  roleType: string;
  status: string;
  isSystem: boolean;
  priority: number;
  organizationId: string | null;
  projectId: string | null;
}

/** `PermissionResponse` (`GET /permissions`) — the real fine-grained
 * `resource`/`action`/`scope` triple this platform's design allows
 * for, but that (per the same confirmed finding) nothing currently
 * evaluates outside `rbac-service` itself. */
export interface RbacPermission {
  id: string;
  name: string;
  code: string;
  description: string | null;
  category: string | null;
  resource: string;
  action: string;
  scope: string;
  status: string;
}

/** `AssignRoleRequest` (`POST /users/{id}/roles`) — a real, persisted
 * write. **Has zero live effect on what that user can actually do
 * anywhere else in AI-IOS today** (confirmed: no other service reads
 * `user_roles`/`organization_roles`/`project_roles` at
 * authorization-decision time) — surfaced with an unmissable warning
 * everywhere this type is used, not just in code comments. */
export interface AssignRoleInput {
  roleId: string;
  scopeType: "global" | "organization" | "project";
  scopeId?: string;
  expiresAt?: string;
}

export interface RoleAssignmentResult {
  id: string;
  userId: string;
  roleId: string;
  scopeType: string;
  scopeId: string | null;
  status: string;
  assignedBy: string;
  expiresAt: string | null;
  createdAt: string;
}

// ---- Project membership (project-service) — surfaced in Settings, not Administration ----
// See docs/frontend/developer-guide/user-management.md "Why project
// membership lives in Settings, not here" — types live alongside the
// page that uses them, features/settings/types/index.ts, not here.
