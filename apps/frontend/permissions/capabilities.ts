/**
 * A coarse, role-only capability model — deliberately NOT fine-grained
 * resource permissions, since no live source exists for those on the
 * frontend today (see `@/permissions/types`). This is a PRESENTATION
 * heuristic only: hiding a control here saves the user a wasted click
 * and a backend 403; it grants no security whatsoever. The backend
 * remains the sole authority — see docs/frontend/architecture/authorization.md.
 *
 * A `null` role (the documented common case — see `@/auth/types`) is
 * treated as least-privilege: read-only, matching `viewer`.
 */

import type { PermissionAction } from "@/permissions/types";
import type { Role } from "@/auth/types";

const ROLE_ACTIONS: Record<Role, ReadonlySet<PermissionAction>> = {
  super_admin: new Set(["read", "create", "update", "delete", "execute", "approve", "export", "import", "admin"]),
  organization_admin: new Set([
    "read",
    "create",
    "update",
    "delete",
    "execute",
    "approve",
    "export",
    "import",
    "admin",
  ]),
  project_admin: new Set(["read", "create", "update", "delete", "execute", "approve", "export", "import"]),
  operator: new Set(["read", "create", "update", "execute", "export"]),
  auditor: new Set(["read", "export"]),
  viewer: new Set(["read"]),
};

const READ_ONLY: ReadonlySet<PermissionAction> = new Set(["read"]);

export function canPerform(role: Role | null, action: PermissionAction): boolean {
  const actions = role ? ROLE_ACTIONS[role] : READ_ONLY;
  return actions.has(action);
}

export function isReadOnlyRole(role: Role | null): boolean {
  if (!role) return true;
  return ROLE_ACTIONS[role].size === READ_ONLY.size && ROLE_ACTIONS[role].has("read");
}

export function isAdministrativeRole(role: Role | null): boolean {
  return role === "super_admin" || role === "organization_admin";
}
