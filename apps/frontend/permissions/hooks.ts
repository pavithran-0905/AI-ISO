"use client";

import { useMemo } from "react";

import { useSession } from "@/auth/session";
import type { Role } from "@/auth/types";
import { canPerform, isAdministrativeRole, isReadOnlyRole } from "@/permissions/capabilities";
import type { PermissionAction } from "@/permissions/types";

/** The permission-presentation API components should use — never
 * `useSession().role` directly for a gating decision, so every check
 * flows through one place. */
export function usePermissions() {
  const { role } = useSession();

  return useMemo(
    () => ({
      role,
      can: (action: PermissionAction) => canPerform(role, action),
      isReadOnly: isReadOnlyRole(role),
      isAdministrative: isAdministrativeRole(role),
    }),
    [role],
  );
}

export function useHasRole(...roles: Role[]): boolean {
  const { role } = usePermissions();
  return role !== null && roles.includes(role);
}
