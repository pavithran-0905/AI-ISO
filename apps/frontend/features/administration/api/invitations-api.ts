/**
 * `services/organization-service` — `POST /organizations/{id}/invite`.
 * The one real invitation path that carries a role (unlike
 * `user-management-service`'s own separate `/users/invite`, which
 * carries no role/team at all) — see the developer guide's "Why this
 * invitation system" section. **No route lists pending invitations,
 * resends one, or revokes one on this service** (confirmed absent) —
 * this module has exactly one function.
 */

import { apiClient } from "@/api/client";
import type { CreateOrganizationInvitationInput, OrganizationInvitation } from "@/features/administration/types";

interface InvitationResponseBody {
  id: string;
  organization_id: string;
  email: string;
  invited_by: string;
  role: string;
  department_id: string | null;
  team_id: string | null;
  status: string;
  resend_count: number;
  expires_at: string;
  created_at: string;
}

export const invitationsApi = {
  async create(input: CreateOrganizationInvitationInput): Promise<OrganizationInvitation> {
    const body = await apiClient.post<InvitationResponseBody>(`/organizations/${input.organizationId}/invite`, {
      email: input.email,
      role: input.role,
      department_id: input.departmentId,
      team_id: input.teamId,
      message: input.message,
    });
    return {
      id: body.id,
      organizationId: body.organization_id,
      email: body.email,
      invitedBy: body.invited_by,
      role: body.role as OrganizationInvitation["role"],
      departmentId: body.department_id,
      teamId: body.team_id,
      status: body.status,
      resendCount: body.resend_count,
      expiresAt: body.expires_at,
      createdAt: body.created_at,
    };
  },
};
