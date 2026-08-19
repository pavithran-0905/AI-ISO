/**
 * `services/rbac-service` — `GET /roles`, `GET /permissions`,
 * `POST/DELETE /users/{id}/roles`. Confirmed, by direct cross-service
 * inspection, that no other AI-IOS service ever reads from this
 * service's tables at authorization-decision time — every mutation
 * here is real and persists, but has no live effect on what a user
 * can actually do anywhere else in the platform today. See
 * `RbacRole`/`AssignRoleInput`'s own docstrings and the developer
 * guide.
 */

import { apiClient } from "@/api/client";
import type { AssignRoleInput, RbacPermission, RbacRole, RoleAssignmentResult } from "@/features/administration/types";

interface RoleResponseBody {
  id: string;
  name: string;
  code: string;
  description: string | null;
  role_type: string;
  status: string;
  is_system: boolean;
  priority: number;
  organization_id: string | null;
  project_id: string | null;
}

function toRole(body: RoleResponseBody): RbacRole {
  return {
    id: body.id,
    name: body.name,
    code: body.code,
    description: body.description,
    roleType: body.role_type,
    status: body.status,
    isSystem: body.is_system,
    priority: body.priority,
    organizationId: body.organization_id,
    projectId: body.project_id,
  };
}

interface PermissionResponseBody {
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

interface RoleAssignmentResponseBody {
  id: string;
  user_id: string;
  role_id: string;
  scope_type: string;
  scope_id: string | null;
  status: string;
  assigned_by: string;
  expires_at: string | null;
  created_at: string;
}

export const rbacApi = {
  /** No route returns a role's granted permissions (write-only
   * grant/revoke exists, no matching read) — this is metadata only. */
  async listRoles(): Promise<RbacRole[]> {
    const body = await apiClient.get<RoleResponseBody[]>("/roles");
    return body.map(toRole);
  },

  async getRole(roleId: string): Promise<RbacRole> {
    const body = await apiClient.get<RoleResponseBody>(`/roles/${roleId}`);
    return toRole(body);
  },

  async listPermissions(): Promise<RbacPermission[]> {
    const body = await apiClient.get<PermissionResponseBody[]>("/permissions");
    return body.map((permission) => ({
      id: permission.id,
      name: permission.name,
      code: permission.code,
      description: permission.description,
      category: permission.category,
      resource: permission.resource,
      action: permission.action,
      scope: permission.scope,
      status: permission.status,
    }));
  },

  /** Real, persisted — and confirmed to have zero live authorization
   * effect anywhere else in the platform today. Every caller of this
   * function must surface that fact in the UI, not just in code. */
  async assignRole(userId: string, input: AssignRoleInput): Promise<RoleAssignmentResult> {
    const body = await apiClient.post<RoleAssignmentResponseBody>(`/users/${userId}/roles`, {
      role_id: input.roleId,
      scope_type: input.scopeType,
      scope_id: input.scopeId,
      expires_at: input.expiresAt,
    });
    return {
      id: body.id,
      userId: body.user_id,
      roleId: body.role_id,
      scopeType: body.scope_type,
      scopeId: body.scope_id,
      status: body.status,
      assignedBy: body.assigned_by,
      expiresAt: body.expires_at,
      createdAt: body.created_at,
    };
  },

  /** No route lists a user's existing assignments (confirmed absent —
   * `RoleAssignmentService.list_for_user` is unrouted) — this module
   * cannot show what's already assigned, only assign/remove blind. */
  async removeRoleAssignment(userId: string, roleId: string): Promise<void> {
    await apiClient.delete(`/users/${userId}/roles/${roleId}`);
  },
};
