/**
 * `services/project-service` — `GET/POST /projects/{id}/members`,
 * `DELETE /projects/{id}/members/{userId}`,
 * `PUT /projects/{id}/members/{userId}/roles`. **No self-lockout
 * protection exists on the backend** (confirmed: `remove`/`update_role`
 * have no last-owner/last-admin/self-removal guard of any kind) — this
 * frontend adds its own guard in `ProjectMembersSection`, since the
 * backend will accept a request that leaves a project with zero
 * owners/admins.
 */

import { apiClient } from "@/api/client";
import type { AddProjectMemberInput, ProjectMember, UpdateProjectMemberRoleInput } from "@/features/settings/types";

interface ProjectMemberResponseBody {
  id: string;
  project_id: string;
  user_id: string;
  role_id: string;
  role_code: string;
  role_name: string;
  status: string;
  invited_by: string | null;
  created_at: string;
}

function toMember(body: ProjectMemberResponseBody): ProjectMember {
  return {
    id: body.id,
    projectId: body.project_id,
    userId: body.user_id,
    roleId: body.role_id,
    roleCode: body.role_code,
    roleName: body.role_name,
    status: body.status,
    invitedBy: body.invited_by,
    createdAt: body.created_at,
  };
}

export const projectMembersApi = {
  async list(projectId: string): Promise<ProjectMember[]> {
    const body = await apiClient.get<ProjectMemberResponseBody[]>(`/projects/${projectId}/members`);
    return body.map(toMember);
  },

  async add(projectId: string, input: AddProjectMemberInput): Promise<ProjectMember> {
    const body = await apiClient.post<ProjectMemberResponseBody>(`/projects/${projectId}/members`, {
      user_id: input.userId,
      role_code: input.roleCode,
    });
    return toMember(body);
  },

  /** Setting `roleCode: "owner"` triggers a full ownership transfer
   * server-side (confirmed) — the caller is responsible for its own
   * distinct confirmation UX before calling this with that value. */
  async updateRole(projectId: string, userId: string, input: UpdateProjectMemberRoleInput): Promise<void> {
    await apiClient.put(`/projects/${projectId}/members/${userId}/roles`, { role_code: input.roleCode });
  },

  async remove(projectId: string, userId: string): Promise<void> {
    await apiClient.delete(`/projects/${projectId}/members/${userId}`);
  },
};
