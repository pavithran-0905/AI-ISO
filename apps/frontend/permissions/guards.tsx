"use client";

import type { Role } from "@/auth/types";
import { usePermissions } from "@/permissions/hooks";
import type { PermissionAction } from "@/permissions/types";

interface RequireRoleProps {
  roles: Role[];
  children: React.ReactNode;
  /** Rendered instead of nothing when the check fails — omit for a silent hide. */
  fallback?: React.ReactNode;
}

/** Component-level gating by role (docs/frontend Prompt 001 §14). UX
 * only — see `@/permissions/capabilities` for why. */
export function RequireRole({ roles, children, fallback = null }: RequireRoleProps): React.ReactNode {
  const { role } = usePermissions();
  if (role === null || !roles.includes(role)) return fallback;
  return children;
}

interface RequirePermissionProps {
  action: PermissionAction;
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

/** Action-level gating (docs/frontend Prompt 001 §14) — e.g. hiding a
 * "Delete" button for a role whose capability set excludes `delete`. */
export function RequirePermission({
  action,
  children,
  fallback = null,
}: RequirePermissionProps): React.ReactNode {
  const { can } = usePermissions();
  if (!can(action)) return fallback;
  return children;
}
